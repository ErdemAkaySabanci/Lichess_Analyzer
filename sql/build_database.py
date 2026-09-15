"""Loads the cleaned Lichess dataset into a SQLite database.

Run from the repo root:
    python sql/build_database.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "data" / "processed" / "lichess_games_clean.csv"
DB_PATH = REPO_ROOT / "sql" / "lichess.db"


def main() -> None:
    df = pd.read_csv(CSV_PATH)

    DB_PATH.unlink(missing_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        df.to_sql("games", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_event ON games(Event)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_opening ON games(Opening)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_date ON games(Date)")
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()

    print(f"Loaded {len(df)} games into {DB_PATH}")


if __name__ == "__main__":
    main()
