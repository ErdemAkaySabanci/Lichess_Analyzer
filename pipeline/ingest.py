"""Incremental ingestion of Lichess games from the REST API into DuckDB.

Writes each game as a JSON payload into `raw.games` (one row per game id), so
the dbt project owns every transformation. Re-running is safe: games are
upserted by id, and the default run only asks the API for games newer than the
latest one already stored.

    python pipeline/ingest.py                      # new games since the last run
    python pipeline/ingest.py --backfill           # older games than the oldest stored
    python pipeline/ingest.py --max 200            # cap the number of games
    python pipeline/ingest.py --from-file f.ndjson # load a saved export (CI, offline)

Lichess requires an API token to export games. Create one without any scopes at
https://lichess.org/account/oauth/token and export it as LICHESS_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import duckdb
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
from data_pipeline import NICKNAME  # noqa: E402  (single source of truth for the player)

DEFAULT_DB = REPO_ROOT / "pipeline" / "warehouse" / "lichess.duckdb"
API_URL = "https://lichess.org/api/games/user/{username}"
BATCH_SIZE = 1000
RATE_LIMIT_WAIT_SECONDS = 60


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.games (
            id          VARCHAR PRIMARY KEY,
            created_at  BIGINT NOT NULL,      -- Lichess createdAt, epoch milliseconds
            fetched_at  TIMESTAMP NOT NULL,
            payload     JSON NOT NULL
        )
        """
    )
    return con


def stored_bounds(con) -> tuple[int | None, int | None]:
    return con.execute("SELECT MIN(created_at), MAX(created_at) FROM raw.games").fetchone()


def fetch_games(username: str, since: int | None, until: int | None, max_games: int | None,
                token: str | None) -> Iterator[dict]:
    """Stream games (newest first) from the Lichess export endpoint as dicts."""
    params = {"opening": "true", "moves": "false", "clocks": "false", "evals": "false"}
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    if max_games:
        params["max"] = max_games
    headers = {"Accept": "application/x-ndjson"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while True:
        response = requests.get(API_URL.format(username=username), params=params,
                                headers=headers, stream=True, timeout=60)
        if response.status_code == 429:
            print(f"Rate limited, waiting {RATE_LIMIT_WAIT_SECONDS}s", file=sys.stderr)
            time.sleep(RATE_LIMIT_WAIT_SECONDS)
            continue
        if response.status_code in (401, 403, 404) and not token:
            raise SystemExit(
                f"Lichess answered {response.status_code} to an anonymous export. Game export "
                "needs an API token: create one (no scopes) at "
                "https://lichess.org/account/oauth/token and set LICHESS_TOKEN."
            )
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                yield json.loads(line)
        return


def read_ndjson(path: Path) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def upsert(con, games: Iterator[dict]) -> int:
    """Insert games not stored yet (by id); returns how many were new."""
    before = con.execute("SELECT COUNT(*) FROM raw.games").fetchone()[0]
    fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
    batch: list[tuple] = []

    def flush() -> None:
        if batch:
            con.executemany(
                "INSERT INTO raw.games VALUES (?, ?, ?, ?) ON CONFLICT (id) DO NOTHING", batch
            )
            batch.clear()

    for game in games:
        batch.append((game["id"], game["createdAt"], fetched_at, json.dumps(game)))
        if len(batch) >= BATCH_SIZE:
            flush()
    flush()
    return con.execute("SELECT COUNT(*) FROM raw.games").fetchone()[0] - before


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DB)))
    parser.add_argument("--username", default=NICKNAME)
    parser.add_argument("--max", type=int, dest="max_games", help="cap the number of games fetched")
    parser.add_argument("--backfill", action="store_true", help="fetch games older than the oldest stored")
    parser.add_argument("--from-file", type=Path, help="load an ndjson export instead of calling the API")
    args = parser.parse_args()

    con = connect(args.db)
    oldest, newest = stored_bounds(con)

    if args.from_file:
        games = read_ndjson(args.from_file)
    else:
        since = None if args.backfill or newest is None else newest + 1
        until = oldest - 1 if args.backfill and oldest is not None else None
        games = fetch_games(args.username, since, until, args.max_games, os.environ.get("LICHESS_TOKEN"))

    inserted = upsert(con, games)
    total = con.execute("SELECT COUNT(*) FROM raw.games").fetchone()[0]
    print(f"Inserted {inserted} new games; raw.games now holds {total}.")


if __name__ == "__main__":
    main()
