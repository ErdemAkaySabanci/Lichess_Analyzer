# Lichess Chess Performance Analytics

An end-to-end data analytics project built on 28,800+ games played on
[Lichess.org](https://lichess.org) by **Kağan Aydınçelebi**, a Turkish
national chess player, under the account
[legend2014](https://lichess.org/@/legend2014) — covering the full path
from a raw PGN export to a deployed interactive dashboard.
The project reimplements and extends an original university report — data
extraction, cleaning, exploratory analysis, hypothesis testing, and a
logistic regression model — and adds a SQL analytics layer and a Streamlit +
Plotly dashboard on top.

## Project Overview

The analysis is organized around a set of concrete, testable questions
about Kağan's game history:

- Does win rate hold up against much higher-rated opponents?
- Does the White-piece advantage show up in practice, and does it hold at
  every opponent-strength level?
- Which time control (bullet, blitz, classical) is played most effectively?
- Does time of day (UTC) correlate with performance?
- Which openings produce the best results, at a defensible sample size?
- Are games more often won on the clock ("Time forfeit") or over the board
  ("Normal")?
- Of rating gap, piece color, time pressure, and hour of day, which factor
  is most associated with winning?

## Data Source

The raw data is a PGN (Portable Game Notation) export of Kağan's full
Lichess game history (`legend2014`) — one metadata block plus move list
per game. See
[`data/raw/my_lichess_history.txt`](data/raw/my_lichess_history.txt).

Fields used by the analysis include `Event` (time control), `White` /
`Black` (usernames), `Result`, `WhiteElo` / `BlackElo`, `WhiteTitle` /
`BlackTitle`, `ECO` (opening code), `Termination`, and `UTCDate` / `UTCTime`.
The move list itself (`Moves`) is parsed but dropped during cleaning — no
analysis in this project operates at the move level, and it accounts for
most of the raw file's size.

## Tech Stack

- **Python / pandas / numpy** — PGN parsing, cleaning, feature engineering ([`notebooks/data_pipeline.py`](notebooks/data_pipeline.py))
- **Jupyter Notebook** — EDA, hypothesis testing, modeling ([`notebooks/lichess_analysis.ipynb`](notebooks/lichess_analysis.ipynb))
- **matplotlib / seaborn** — static charts in the notebook's EDA and hypothesis-testing sections
- **SQL / SQLite** — `GROUP BY`, `CASE WHEN`, CTEs, and window functions ([`/sql`](sql))
- **scipy** — hypothesis testing (Welch's t-test)
- **scikit-learn** — Logistic Regression, `StandardScaler`, `train_test_split`, evaluation metrics
- **imbalanced-learn** — SMOTE oversampling for class imbalance
- **Streamlit / Plotly** — interactive dashboard ([`/dashboard`](dashboard))

## Data Pipeline

```
Raw PGN Data
  → Data Cleaning
    → Feature Engineering
      → Exploratory Data Analysis
        → SQL Analysis
          → Statistical Testing
            → Machine Learning
              → Interactive Dashboard
```

`notebooks/data_pipeline.py` is the single source of truth for the cleaning
and feature-engineering stages — its output feeds the notebook, the SQLite
build script, and the dashboard identically, so all three stay in sync.

## Data Cleaning and Feature Engineering

Cleaning (`clean_games`) drops columns not used anywhere downstream (`FEN`,
`SetUp`, `Site`, `Date`, `Moves`) and derives `ResultStatus`
(win / loss / draw) from `Result` relative to the player's color.

Feature enrichment (`enrich_games`) then derives:

- `Date` and `Hour` — parsed from `UTCDate` / `UTCTime`
- `Opening` — mapped from the `ECO` code via a lookup table ([`notebooks/eco_codes.py`](notebooks/eco_codes.py))
- `OpponentElo` / `OpponentEloRange` — the non-player side's rating, binned into 200-point ranges
- `PlayerColor` — White or Black, based on which side the player was on
- `IsRanked` — whether the game was a rated bullet/blitz/classical game

Sections of the pipeline and notebook marked **[RECONSTRUCTED]** reproduce
logic that existed in the original notebook but whose source cells were
lost (only cached outputs survived); each is re-implemented with the most
defensible interpretation of the original approach, stated inline.

## Exploratory Data Analysis

- **Win rate by time control** — bullet vs. blitz vs. classical, the three
  rated Lichess pools (kept as separate series throughout; never averaged
  together).
- **White vs. Black** — overall win rate split by piece color.
- **Activity over time** — monthly game volume.
- **Win rate by opponent Elo range** — performance across 200-point rating
  bands.
- **Win rate by hour of day (UTC)**.
- **Opening performance** — White-side and Black-side results per opening,
  combined into a single per-opening win rate, filtered to a minimum game
  count.

## SQL Analysis

Five standalone queries in [`/sql`](sql) answer the project's core
questions directly against the SQLite database, each demonstrating a
distinct SQL technique:

| Query | Technique |
|---|---|
| [`01_winrate_by_mode.sql`](sql/01_winrate_by_mode.sql) | `GROUP BY` + `CASE WHEN` aggregation |
| [`02_winrate_by_opening.sql`](sql/02_winrate_by_opening.sql) | CTE (`WITH`) + `RANK() OVER` window function |
| [`03_winrate_by_elo_range.sql`](sql/03_winrate_by_elo_range.sql) | `CASE WHEN` bucketing into Elo bands |
| [`04_winrate_by_hour.sql`](sql/04_winrate_by_hour.sql) | `GROUP BY` with a part-of-day `CASE WHEN` label |
| [`05_activity_trend.sql`](sql/05_activity_trend.sql) | `AVG() OVER` (moving average), `SUM() OVER` (running total), `LAG()` (month-over-month change) |

[`dashboard/queries.py`](dashboard/queries.py) reimplements the same
analyses — plus opponent title, color-by-Elo-band, and termination-type
breakdowns — as parametrized functions filtered by time control, opening,
and date range, behind a shared `_where_clause` helper.

## Statistical Analysis

Two hypothesis tests, both Welch's two-sample t-tests (`scipy.stats.
ttest_ind`, unequal variance), in section 7 of the notebook:

- **Opponent strength.** H0: win rate against opponents rated above 2900 is
  the same as against everyone else. The test rejects H0 (p < 0.001) —
  performance measurably declines against that cohort.
- **Termination type.** Compares outcomes in games decided normally
  (checkmate/resignation) against games decided on the clock (time
  forfeit), to test whether one is associated with better results than the
  other.

## Machine Learning

A secondary, exploratory piece of the analysis: a multi-class **Logistic
Regression** model (`scikit-learn`) predicts game outcome (win / draw /
loss) from four candidate factors — `EloDiff` (rating gap), `IsWhite`
(piece color), `IsTimeForfeit` (termination type), and `Hour` (time of
day). Features are scaled with `StandardScaler`; because outcome classes
are imbalanced, the training set is oversampled with **SMOTE**
(`imbalanced-learn`) before fitting. The model is evaluated with accuracy
and a full classification report on a held-out test split, and feature
importance is read off the mean absolute coefficient across the three
outcome classes.

## Interactive Dashboard

**Live demo:** [lichess-data-analytics.streamlit.app](https://lichess-data-analytics.streamlit.app/)
_(free-tier hosting — first load after idle can take ~15-20s to wake up; a
GitHub Actions cron job in [`.github/workflows/keepalive.yml`](.github/workflows/keepalive.yml)
pings it periodically to reduce this)_

Built with Streamlit and Plotly ([`dashboard/app.py`](dashboard/app.py)),
every chart is a live SQL query against `sql/lichess.db`, responsive to
sidebar filters for time control, opening, and date range. A KPI row up
top summarizes games analyzed, overall win rate, peak rating, and best
opening for the current filter selection.

Each chart's form was chosen to match the shape of its data rather than
defaulting to a bar chart:

| Chart | Why this form |
|---|---|
| Calendar heatmap | Daily counts over a calendar structure; a fixed colour scale across years makes growth comparable |
| Line per rating pool | Bullet and blitz are separate Lichess pools, so they are plotted as separate series and never averaged |
| Single-row heatmap strip | An ordered scale where only the gradient matters — no bar heights to compare |
| Bubble chart (size = games) | Encodes sample size alongside win rate, so a thin-sample result can't masquerade as a strong one |
| Cleveland paired dot plot | Two series across ordered bands; the gap between dots *is* the finding |
| Marimekko / mosaic | Two dimensions at once — column width is volume, column height is composition |
| Treemap | Many categories where relative volume matters; a diverging scale with a grey midpoint pinned to 50% |
| Polar rose | Hours are cyclical, so a circular axis avoids cutting midnight in half |

Two comparisons — win rate by time control, and White vs. Black overall —
were retired as standalone charts: each was two numbers, and no chart form
fixes that. The first moved into the KPI row; the second was rebuilt as
the paired dot plot, split across opponent strength, where it has
something to say.

![Dashboard overview](dashboard/screenshots/overview.png)
![Rating trajectory and opponent-strength heatmap strip](dashboard/screenshots/strength.png)
![Opponent-title bubble chart and Cleveland paired dot plot](dashboard/screenshots/opponents.png)
![Marimekko mosaic of termination type vs. outcome](dashboard/screenshots/terminations.png)

## A/B Testing

The White-vs-Black comparison is a genuine A/B test: the treatment is piece
colour, and Lichess assigns it at random. The streak comparison is a
quasi-experiment, because games were not randomly assigned to groups. Both use
the standard A/B toolkit (two-proportion z-test, confidence intervals, odds
ratio, sample-ratio check, A/A test, power analysis) and the write-up says
where causal claims stop. Implemented in
[`dashboard/stats.py`](dashboard/stats.py) (standard library + numpy only),
shown in the dashboard's *Experiments* section and in section 9 of the
notebook; the underlying counts come from
[`06_color_ab_test.sql`](sql/06_color_ab_test.sql) and
[`07_tilt_effect.sql`](sql/07_tilt_effect.sql).

- **White vs Black** is the closest thing to a controlled experiment, because
  Lichess pairs colours at random (a sample-ratio check confirms the 50/50
  split). White wins **+5.1 percentage points** more often (95% CI +3.9 to
  +6.4, p < 0.001, odds ratio 1.23).
- **Does the previous result carry over?** Within a session (games less than
  30 minutes apart), the next game is won **55.1%** of the time after a win
  and **46.0%** after a loss (+9.0 pp). The next opponent is ~55 rating
  points weaker after a win, so the comparison is repeated inside
  opponent-rating bands: **+6.8 pp** (95% CI +5.3 to +8.2). That is an
  association — the data cannot separate form or focus from matchmaking.
- **Method checks.** An A/A test (splitting the same games at random) flags a
  difference about 5% of the time, as it should, and the power analysis shows
  ~9,800 games per group are needed to detect a 2-point gap.

## Design Implications

Read as player-behaviour data from a competitive game, each result raises a
design question and the A/B test that would answer it. These are hypotheses to
test, not conclusions this dataset can prove:

| Finding | Design question | Test to run |
|---|---|---|
| White wins ~5 pp more often, across time controls | Does first-move advantage make matchmaking feel unfair? | Randomize a small compensation for the second player; metric: win-rate gap and games per day; guardrail: overall win rate |
| The next game is won more often after a win than a loss, even within an opponent-strength band | Is momentum a retention lever, and does a loss need a softer landing? | Randomize next-opponent difficulty after a loss; metric: share of players starting another game within 30 minutes |
| Games decided on the clock are won far more often than games decided over the board | Is time pressure rewarded skill or created frustration? | Randomize the time increment between equally rated players; metric: share of games ending on time, completion rate |

Each would need a pre-test power analysis like the one above and a
sample-ratio check after launch.

## Key Findings

- **Games decided on the clock are won far more often than games decided
  over the board.** Time-forfeit games show a **79.3%** win rate, versus
  **45.2%** for games decided normally.
- **The White-piece advantage holds at every level of opposition.**
  Splitting win rate by piece color *within* each opponent-rating band
  shows White ahead in all five bands, averaging **+4.8 percentage
  points**.
- **Performance degrades sharply with opponent strength.** Win rate falls
  to **36.4% across 3,613 games against Grandmasters**; a two-sample
  t-test against the 2900+ Elo cohort rejects the hypothesis of equal
  performance (p < 0.001).
- **Best-performing opening: Ruy Lopez (Berlin Defense)** — **70.7%** over
  58 rated games, the strongest result among openings with a defensible
  sample size.

> Some intermediate notebook cells (feature engineering for the model, the
> ECO→opening name mapping, the combined opening win-rate table) were
> missing from the original saved notebook and have been reconstructed;
> each is marked **[RECONSTRUCTED]** in the notebook with the assumption it
> makes stated explicitly.

## Data Platform

Besides the analysis, the repo contains a small data-engineering layer that
rebuilds the same dataset from the Lichess REST API instead of a manual PGN
export:

```
Lichess REST API ──► raw.games (DuckDB, JSON payloads)
                          │  dbt: staging ─► intermediate ─► marts (+ tests)
                          ▼
             games · fct_games · dim_opening · dim_date
                          │  pipeline/export_to_sqlite.py
                          ▼
                 SQLite ─► Streamlit dashboard
```

- **Ingestion** ([`pipeline/ingest.py`](pipeline/ingest.py)): incremental
  (`since` = newest stored game) and idempotent (upsert by game id), with
  rate-limit handling. `--backfill` fetches older games, `--from-file` loads a
  saved export.
- **dbt** ([`dbt/lichess`](dbt/lichess)): the pandas feature engineering
  (colour, opponent rating band, opening lookup, sessions via window
  functions) re-expressed as SQL models, with 25 data tests (uniqueness,
  not-null, accepted values, referential integrity, a session-logic test) and
  a source-freshness check. Adapter-specific SQL is isolated in one macro file.
- **Parity check** ([`pipeline/check_parity.py`](pipeline/check_parity.py)):
  compares the dbt output with the legacy pandas pipeline column by column. On
  all 28,838 games the only differences are 2 cells from two games that start
  in the same second (the PGN export has no sub-second timestamps, the API does).
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): runs
  ingestion, `dbt build`, the parity check, the export and a headless render of
  the dashboard on a committed fixture, with no network access.
- **Orchestration** ([`pipeline/airflow`](pipeline/airflow)): a daily Airflow
  DAG (`ingest → dbt_build → parity_check → export_to_sqlite`) in a local
  Docker container.

**What was and was not run.** The pipeline, parity check, dashboard smoke test
and the Airflow DAG were run locally (all green). Two limits: Lichess now
requires an API token for game export, so the live-API path is covered by a
mocked-server test and has not yet pulled the real history, and the CI fixture
is *synthetic* (converted from the PGN-derived CSV into the API's JSON shape).
The warehouse is DuckDB, not Snowflake; the models are plain SQL apart from a
handful of DuckDB functions in `dbt/lichess/macros/adapter_helpers.sql`, and the
workflow has not been run on GitHub Actions yet.

```bash
python -m venv .venv-pipeline && source .venv-pipeline/bin/activate   # Windows: .venv-pipeline/Scripts/activate
pip install -r pipeline/requirements.txt
export LICHESS_TOKEN=...            # create at lichess.org/account/oauth/token, no scopes
python pipeline/ingest.py           # or: --from-file pipeline/fixtures/games_sample.ndjson
cd dbt/lichess && dbt build --profiles-dir . && cd ../..
python pipeline/check_parity.py
python pipeline/export_to_sqlite.py # writes sql/lichess_platform.db (does not touch sql/lichess.db)
```

## Repository Structure

```
data/
  raw/            original PGN export
  processed/      cleaned, feature-enriched CSV
notebooks/
  data_pipeline.py       shared cleaning/feature-engineering logic
  eco_codes.py            ECO code -> opening name lookup table
  lichess_analysis.ipynb  the full analysis notebook (EDA, hypothesis tests, ML)
sql/
  build_database.py       loads the processed CSV into SQLite
  lichess.db               generated SQLite database
  01-05_*.sql              five standalone analysis queries
  06-07_*.sql              counts behind the colour and streak experiments
dashboard/
  queries.py               parametrized SQL used by the dashboard
  stats.py                 z-test, confidence intervals, power analysis, A/A test
  app.py                   Streamlit app
  requirements.txt         lean dependency list for Streamlit Cloud
  screenshots/             local-run screenshots used in this README
pipeline/
  ingest.py                Lichess API -> DuckDB raw layer
  check_parity.py          dbt output vs legacy pandas pipeline
  export_to_sqlite.py      dbt mart -> SQLite for the dashboard
  airflow/                 Dockerfile, compose file and the daily DAG
dbt/lichess/               dbt project (models, seeds, tests)
.github/workflows/
  ci.yml                   pipeline CI on a fixture
  keepalive.yml            cron job that pings the live demo to reduce cold starts
requirements.txt            full environment (notebook + dashboard + ML)
```

## Running the Project

### 1. Set up the environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Regenerate the processed data (optional — already included)

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/lichess_analysis.ipynb
```

### 3. Build the SQLite database

```bash
python sql/build_database.py
```

### 4. Run the dashboard

```bash
streamlit run dashboard/app.py
```

Then open the local URL Streamlit prints (defaults to `http://localhost:8501`).

### Deploying the dashboard (Streamlit Community Cloud, free)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.
2. Click **New app** → select the `Lichess_Analyzer` repo, branch `main`.
3. Set **Main file path** to `dashboard/app.py`.
4. Deploy. Streamlit Cloud automatically picks up [`dashboard/requirements.txt`](dashboard/requirements.txt) (a lean dependency list scoped to just the dashboard) instead of the full project `requirements.txt`.

## What This Project Demonstrates

- Cleaning and structuring messy, real-world semi-structured data (PGN) into an analysis-ready dataset
- Feature engineering and data manipulation with Python / pandas
- Writing analytical SQL — aggregations, `CASE WHEN` segmentation, CTEs, and window functions
- Exploratory data analysis and clear, evidence-based communication of findings
- Statistical hypothesis testing to validate (or reject) intuitive claims about the data
- Data visualization — choosing a chart form deliberately based on the shape of the data, not by default
- Building and deploying an interactive analytics dashboard
- Maintaining a single, consistent data pipeline across a notebook, a SQL layer, and a web app

## Author

**Erdem Akay** — Computer Science & Engineering, Sabancı University

Analysis, SQL layer and dashboard by Erdem Akay. The game data belongs to
[Kağan Aydınçelebi](https://lichess.org/@/legend2014), a Turkish national
chess player, shared with his permission.
