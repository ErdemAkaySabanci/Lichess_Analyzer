"""Writes the ECO code -> opening name lookup as a dbt seed.

`notebooks/eco_codes.py` stays the source of truth; the seed is generated from
it so the dbt models and the legacy pandas pipeline agree.

    python pipeline/make_eco_seed.py
"""
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
from eco_codes import ECO_DICT  # noqa: E402

OUT = REPO_ROOT / "dbt" / "lichess" / "seeds" / "eco_openings.csv"

with open(OUT, "w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["eco", "opening_name"])
    for eco, name in sorted(ECO_DICT.items()):
        writer.writerow([eco, name])
print(f"Wrote {len(ECO_DICT)} openings to {OUT}")
