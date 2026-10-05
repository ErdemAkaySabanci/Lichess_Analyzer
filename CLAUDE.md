# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A data-analyst portfolio project: ~28,800 personal Lichess bullet/blitz/classical
games, exported as PGN, cleaned into a single dataset, loaded into SQLite, and
served through a Streamlit + Plotly dashboard. There's also a Jupyter notebook
with the original EDA/hypothesis-testing/logistic-regression analysis.

The player being analyzed is hardcoded as `NICKNAME = "legend2014"` in both
`notebooks/data_pipeline.py` and `dashboard/queries.py` — keep these two
values in sync if either changes.

The analyzed account belongs to a friend of the repo owner (Erdem), not to
Erdem. Write README/dashboard copy in an analyst voice ("this analysis
found…"), never first-person chess-player voice ("my games", "I win"), and
never attribute chess titles to Erdem.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # full env (notebook + dashboard + ML)
pip install -r dashboard/requirements.txt   # lean env, dashboard only (used by Streamlit Cloud)

# Rebuild data/processed/lichess_games_clean.csv from the raw PGN (optional, already committed)
jupyter nbconvert --to notebook --execute --inplace notebooks/lichess_analysis.ipynb

# Rebuild sql/lichess.db from the processed CSV (run after the CSV changes)
python sql/build_database.py

# Run the dashboard
streamlit run dashboard/app.py
```

There is no test suite and no linter configured in this repo.

## Architecture: one pipeline, three consumers

`notebooks/data_pipeline.py` is the single source of truth for turning raw
PGN into the cleaned/enriched dataset. Its stages — `parse_pgn` →
`clean_games` → `enrich_games` (composed as `load_clean_dataset`) — are used
by the notebook, and its output (`data/processed/lichess_games_clean.csv`) is
what `sql/build_database.py` loads into SQLite and what the dashboard
ultimately queries. If you change a derived column's logic (e.g. `Opening`,
`OpponentElo`, `Hour`, `PlayerColor`), change it in `data_pipeline.py`, then
re-run the notebook export and `sql/build_database.py` so the CSV and DB stay
consistent with it.

`notebooks/eco_codes.py` provides the `ECO_DICT` lookup (ECO code → opening
name) that `enrich_games` uses to build the `Opening` column.

Sections in `data_pipeline.py` and the notebook marked **[RECONSTRUCTED]**
reproduce logic that existed in the original notebook but whose source cells
were lost (only cached outputs survived) — they're re-implemented with the
most natural interpretation of the original approach, and that assumption is
stated inline. Treat these as slightly more negotiable than the rest of the
pipeline if a change requires revisiting the assumption.

The SQL layer has two parallel forms of the same analyses:
- `/sql/01-07_*.sql` — fixed, standalone queries answering the project's five
  core questions (01-05) plus the two experiment count queries (06-07).
- `dashboard/queries.py` — the same analyses reimplemented as parametrized
  functions (mode / opening / date-range filters via `_where_clause`), used
  interactively by the dashboard. Every dashboard chart maps to one function
  here; if a `.sql` file's question changes, update its `queries.py`
  counterpart too.

`dashboard/stats.py` holds the A/B-style statistics (two-proportion z-test,
Wilson/Wald CIs, power analysis, A/A test, stratified difference) behind the
dashboard's *Experiments* section and notebook section 9; it deliberately
uses only the standard library + numpy so the lean Streamlit Cloud
environment needs nothing extra. The data is observational — only the
White-vs-Black comparison is close to randomized, so keep streak/tilt
results framed as association. `SessionId`, `GameInSession` and `PrevResult`
(derived in `add_session_columns`, 30-minute start-to-start session gap) feed
`sql/07_tilt_effect.sql` and `queries.tilt_experiment`.

`dashboard/app.py` is a single top-to-bottom Streamlit script (no
multi-page/component split): sidebar filters → KPI row → one section per
theme (activity, strength, opponents, terminations, openings/timing) → raw
data tables in an expander. Each chart's Plotly form was deliberately chosen
to match the shape of its data (see the "On the chart choices" table in
README.md) — when adding a new chart, pick the form the same way rather than
defaulting to a bar chart.

## Data platform layer (pipeline/ and dbt/)

A second, newer path builds the same `games` table from the Lichess API:
`pipeline/ingest.py` → DuckDB `raw.games` → `dbt/lichess` (staging →
intermediate → marts, 25 tests) → `pipeline/export_to_sqlite.py`. It does
**not** replace the committed `sql/lichess.db` (the README and dashboard text
quote its 28,838 games); the export writes `sql/lichess_platform.db` unless
`--out` says otherwise. `dbt/lichess/models/intermediate/int_games_enriched.sql`
re-implements `enrich_games` / `add_session_columns`, so a change to a derived
column must be made in both and verified with `python pipeline/check_parity.py`.

```bash
.venv-pipeline/Scripts/python pipeline/ingest.py --from-file pipeline/fixtures/games_sample.ndjson
cd dbt/lichess && dbt build --profiles-dir .      # DUCKDB_PATH overrides the warehouse file
python pipeline/check_parity.py --strict          # needs the DuckDB built above
python pipeline/smoke_test_dashboard.py sql/lichess_platform.db
```

- Lichess game export needs `LICHESS_TOKEN` (anonymous requests return 404).
- `pipeline/fixtures/games_sample.ndjson` is synthetic (converted from the CSV
  by `pipeline/make_fixture.py`), not a capture of the live API.
- `player_name` in `dbt/lichess/dbt_project.yml` is a third copy of the
  `NICKNAME` that must stay in sync.
- The Airflow stack (`pipeline/airflow`, `docker compose up --build`) copies
  `.env.example` to `.env`; `INGEST_MODE=fixture` runs without a token.

## Data notes

- `data/raw/my_lichess_history.txt` is the raw PGN export (one metadata-tag
  block + move list per game). `Moves` is dropped during cleaning — nothing
  downstream does move-by-move parsing, and it's most of the raw file's size.
- Bullet, blitz, and classical are separate Lichess rating pools and are
  never averaged together — anywhere ratings are aggregated across modes
  (e.g. `elo_trajectory`, `peak_rating`), each mode is kept as its own
  series/row.
- `.github/workflows/keepalive.yml` is a cron that pings the deployed
  Streamlit Cloud app every 10 hours so it doesn't sleep; it isn't CI and
  runs no tests.
- `sql/lichess.db` is a generated artifact (rebuilt by `sql/build_database.py`
  from the CSV) — treat the CSV as the source of truth, not the `.db` file.
