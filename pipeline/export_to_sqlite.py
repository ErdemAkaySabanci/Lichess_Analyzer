"""Exports the dbt `games` mart from DuckDB into a SQLite database the dashboard can read.

The dashboard keeps reading SQLite so the Streamlit Cloud environment needs no
DuckDB. By default this writes sql/lichess_platform.db and leaves the committed
sql/lichess.db (built from the PGN export, and quoted in the README and the
dashboard text) untouched. Pass --out sql/lichess.db to replace it on purpose.

    python pipeline/export_to_sqlite.py [--db pipeline/warehouse/lichess.duckdb] [--out sql/lichess_platform.db]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sql"))
from build_database import write_database  # noqa: E402

DEFAULT_DB = REPO_ROOT / "pipeline" / "warehouse" / "lichess.duckdb"
DEFAULT_OUT = REPO_ROOT / "sql" / "lichess_platform.db"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DB)))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    df = con.execute('SELECT * FROM main.games ORDER BY "Date" DESC, "UTCTime" DESC').df()
    write_database(df, args.out)
    print(f"Exported {len(df)} games from {args.db.name} to {args.out}")


if __name__ == "__main__":
    main()
