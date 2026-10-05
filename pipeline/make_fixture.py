"""Builds a small API-shaped ndjson fixture for CI and offline development.

SYNTHETIC: the records are converted from rows of the processed PGN-derived CSV
into the JSON shape the Lichess export endpoint returns. They exercise the dbt
transformations and tests without network access or a token. They are not a
capture of the live API; real API output comes from `pipeline/ingest.py`.

    python pipeline/make_fixture.py [--rows 400] [--start 3000]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "data" / "processed" / "lichess_games_clean.csv"
OUT = REPO_ROOT / "pipeline" / "fixtures" / "games_sample.ndjson"

VARIANT_KEYS = {
    "Standard": "standard", "Crazyhouse": "crazyhouse", "Atomic": "atomic", "Antichess": "antichess",
    "King of the Hill": "kingOfTheHill", "Three-check": "threeCheck", "Racing Kings": "racingKings",
    "Horde": "horde", "Chess960": "chess960", "From Position": "fromPosition",
}


def speed_for(initial: int, increment: int) -> str:
    estimate = initial + 40 * increment
    if estimate < 30:
        return "ultraBullet"
    if estimate < 180:
        return "bullet"
    if estimate < 480:
        return "blitz"
    if estimate < 1500:
        return "rapid"
    return "classical"


def to_record(row: pd.Series, index: int) -> dict:
    created = datetime.strptime(f"{row.UTCDate} {row.UTCTime}", "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
    if row.TimeControl and row.TimeControl != "-":
        initial, increment = (int(x) for x in row.TimeControl.split("+"))
    else:
        initial = increment = None

    event = row.Event
    in_tournament = not event.startswith(("Rated ", "Casual "))
    speed = speed_for(initial, increment) if initial is not None else "correspondence"

    def player(side: str) -> dict:
        data = {"user": {"name": row[side], "id": row[side].lower()},
                "rating": None if pd.isna(row[f"{side}Elo"]) else int(row[f"{side}Elo"])}
        if isinstance(row[f"{side}Title"], str):
            data["user"]["title"] = row[f"{side}Title"]
        if not pd.isna(row[f"{side}RatingDiff"]):
            data["ratingDiff"] = int(row[f"{side}RatingDiff"])
        return data

    # the real API keeps status "outoftime" for a drawn flag fall; only normal draws are "draw"
    status = {"Time forfeit": "outoftime", "Abandoned": "timeout"}.get(
        row.Termination, "draw" if row.Result == "1/2-1/2" else "resign"
    )
    record = {
        "id": f"fx{index:06d}",
        "rated": event.startswith("Rated ") or (in_tournament and not pd.isna(row.WhiteRatingDiff)),
        "variant": VARIANT_KEYS[row.Variant], "speed": speed, "perf": speed,
        "createdAt": int(created.timestamp() * 1000), "status": status,
        "players": {"white": player("White"), "black": player("Black")},
        "opening": {"eco": row.ECO, "name": "unused"},
    }
    if row.Result != "1/2-1/2":
        record["winner"] = "white" if row.Result == "1-0" else "black"
    if initial is not None:
        record["clock"] = {"initial": initial, "increment": increment, "totalTime": initial + 40 * increment}
    if in_tournament:
        record["arenaTour"] = {"id": f"t{index:05d}", "name": event}
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--start", type=int, default=3000)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    df = pd.read_csv(CSV_PATH, keep_default_na=False, na_values=[""])
    sample = df.iloc[args.start:args.start + args.rows]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        for index, row in sample.iterrows():
            handle.write(json.dumps(to_record(row, index)) + "\n")
    print(f"Wrote {len(sample)} synthetic API-shaped games to {args.out}")


if __name__ == "__main__":
    main()
