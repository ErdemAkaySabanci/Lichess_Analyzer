"""Compares the dbt `games` mart with the legacy pandas pipeline's CSV.

Games are matched on (UTCDate, UTCTime, White, Black). For every shared game each
column is compared; the session columns are checked against `add_session_columns`
run on exactly the matched rows, so a partial load is judged fairly. The report
lists real differences instead of hiding them.

    python pipeline/check_parity.py [--strict]

--strict exits non-zero when any compared column differs (used by CI on the fixture).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
from data_pipeline import add_session_columns  # noqa: E402

DEFAULT_DB = REPO_ROOT / "pipeline" / "warehouse" / "lichess.duckdb"
CSV_PATH = REPO_ROOT / "data" / "processed" / "lichess_games_clean.csv"
KEY = ["UTCDate", "UTCTime", "White", "Black"]
COMPARED = [
    "Event", "Result", "WhiteElo", "BlackElo", "WhiteRatingDiff", "BlackRatingDiff", "WhiteTitle",
    "BlackTitle", "Variant", "TimeControl", "ECO", "Termination", "ResultStatus", "Date", "Hour",
    "Opening", "IsRanked", "OpponentElo", "OpponentEloRange", "PlayerColor", "GameInSession", "PrevResult",
]


def normalise(series: pd.Series) -> pd.Series:
    """Make mart and CSV values comparable: numbers as floats, everything else as text, NaN as <NA>."""
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() == series.notna().sum() and series.notna().any() and series.dtype != bool:
        return numeric.astype("float64").astype("string")
    return series.astype("string")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("DUCKDB_PATH", DEFAULT_DB)))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    mart = duckdb.connect(str(args.db), read_only=True).execute("SELECT * FROM main.games").df()
    legacy = pd.read_csv(CSV_PATH)

    matched = legacy.merge(mart[KEY].drop_duplicates(), on=KEY, how="inner")
    expected = add_session_columns(matched.drop(columns=["SessionId", "GameInSession", "PrevResult"]))
    merged = expected.merge(mart, on=KEY, how="inner", suffixes=("_legacy", "_mart"))

    print(f"mart rows: {len(mart):,} · legacy CSV rows: {len(legacy):,} · matched on {KEY}: {len(merged):,}")
    print(f"mart only (e.g. games newer than the PGN export): {len(mart) - len(merged):,}")
    if merged.empty:
        print("No overlapping games; nothing to compare.")
        return 1 if args.strict else 0

    failures = 0
    print(f"\n{'column':<18}{'differences':>12}")
    for column in COMPARED:
        left, right = normalise(merged[f"{column}_legacy"]), normalise(merged[f"{column}_mart"])
        differs = ~((left == right) | (left.isna() & right.isna()))
        count = int(differs.sum())
        failures += count
        print(f"{column:<18}{count:>12}")
        if count:
            sample = merged.loc[differs, KEY].head(3).assign(legacy=left[differs].head(3), mart=right[differs].head(3))
            print(sample.to_string(index=False, header=True))

    print(f"\nTotal differing cells: {failures}")
    return 1 if (args.strict and failures) else 0


if __name__ == "__main__":
    sys.exit(main())
