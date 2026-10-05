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


def write_database(df: pd.DataFrame, db_path: Path) -> None:
    """Replace `db_path` with a SQLite database holding df as the `games` table."""
    db_path.unlink(missing_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        df.to_sql("games", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_event ON games(Event)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_opening ON games(Opening)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_date ON games(Date)")
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    write_database(df, DB_PATH)
    print(f"Loaded {len(df)} games into {DB_PATH}")


if __name__ == "__main__":
    main()
