# Lichess Bullet Chess Performance Analysis

A data analyst portfolio project analyzing ~28,800 chess games played on
[Lichess.org](https://lichess.org), covering data cleaning, exploratory
analysis, a SQL analytics layer, hypothesis testing, a Logistic Regression
model, and an interactive dashboard.

## Project Goal

Answer a set of concrete performance questions from raw game history: which
time control is played best, whether the white-piece advantage shows up in
practice, whether performance holds up against much stronger opponents,
which openings work best, and which single factor (rating gap, piece
color, time pressure, or hour of day) best predicts a game's outcome.

## Data Source

Raw data is a PGN (Portable Game Notation) export downloaded directly from
a Lichess account's game history — one text block per game, with metadata
tags (`Event`, `White`, `Black`, `Result`, `WhiteElo`, `ECO`, ...) followed
by the move list. See [`data/raw/my_lichess_history.txt`](data/raw/my_lichess_history.txt).

## Tech Stack

- **Python / pandas** — PGN parsing and data cleaning ([`notebooks/data_pipeline.py`](notebooks/data_pipeline.py))
- **Jupyter Notebook** — exploratory analysis, hypothesis testing, modeling ([`notebooks/lichess_analysis.ipynb`](notebooks/lichess_analysis.ipynb))
- **SQL / SQLite** — GROUP BY, CASE WHEN and window-function analyses ([`/sql`](sql))
- **scikit-learn / imbalanced-learn** — Logistic Regression with SMOTE oversampling
- **Streamlit / Plotly** — interactive dashboard ([`/dashboard`](dashboard))

## Repository Structure

```
data/
  raw/            original PGN export
  processed/      cleaned, feature-enriched CSV
notebooks/
  data_pipeline.py      shared cleaning/feature-engineering logic
  eco_codes.py           ECO code -> opening name lookup table
  lichess_analysis.ipynb the full analysis notebook
sql/
  build_database.py      loads the processed CSV into SQLite
  lichess.db              generated SQLite database
  01-05_*.sql             five standalone analysis queries
dashboard/
  queries.py              parametrized SQL used by the dashboard
  app.py                  Streamlit app
  screenshots/            local-run screenshots used in this README
requirements.txt
```

## Key Findings

- **The clock is a weapon, not a weakness.** Games decided on time are a **79.3%** win rate; games decided over the board are **45.2%**. The first draft of this project's write-up claimed the opposite — the mosaic plot in the dashboard is what caught the error.
- **The white-piece advantage holds at every level of opposition.** Splitting win rate by piece colour *within* each opponent-rating band shows White ahead in all five bands, averaging **+4.8 percentage points** — the edge doesn't evaporate against stronger players.
- **Performance degrades sharply with opponent strength.** Win rate falls from 59% against CMs to **36.4% across 3,613 games against Grandmasters**; a two-sample t-test against the 2900+ cohort rejects equal performance (p < 0.001).
- **Best opening: Ruy Lopez (Berlin Defense)** — **70.7%** over 58 rated games, the strongest result among openings with a defensible sample size.

> Some intermediate notebook cells (feature engineering for the model, the
> ECO→opening name mapping, the combined opening win-rate table) were
> missing from the original saved notebook and have been reconstructed;
> each is marked **[RECONSTRUCTED]** in the notebook with the assumption it
> makes stated explicitly.

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

## Live Demo / Screenshots

**Live demo:** [lichessanalyzer-kunhdct4haer6ezadhndcf.streamlit.app](https://lichessanalyzer-kunhdct4haer6ezadhndcf.streamlit.app/)
_(free-tier hosting — first load after idle can take ~15-20s to wake up)_

Screenshots from a local run:

![Dashboard overview](dashboard/screenshots/overview.png)
![Rating trajectory and opponent-strength heatmap strip](dashboard/screenshots/strength.png)
![Opponent-title bubble chart and Cleveland paired dot plot](dashboard/screenshots/opponents.png)
![Marimekko mosaic of termination type vs. outcome](dashboard/screenshots/terminations.png)

### On the chart choices

The dashboard deliberately avoids defaulting to bar charts. Each form was picked
from the shape of the data it displays:

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

Two comparisons — win rate by time control, and White vs. Black overall — were
retired as standalone charts: each was two numbers, and no chart form fixes that.
The first moved into the KPI row; the second was rebuilt as the paired dot plot,
split across opponent strength, where it finally had something to say.

### Deploying the dashboard (Streamlit Community Cloud, free)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.
2. Click **New app** → select the `Lichess_Analyzer` repo, branch `main`.
3. Set **Main file path** to `dashboard/app.py`.
4. Deploy. Streamlit Cloud automatically picks up [`dashboard/requirements.txt`](dashboard/requirements.txt) (a lean dependency list scoped to just the dashboard) instead of the full project `requirements.txt`.
5. Once live, copy the app URL back into this README's "Live demo" line above.
