"""Streamlit dashboard for the Lichess game history portfolio project.

Run from the repo root:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queries as q
import stats

WIN, DRAW, LOSS = "#1a9850", "#bdbdbd", "#d73027"
WHITE_PIECE, BLACK_PIECE = "#e8eced", "#2d3436"
MODE_COLORS = {"Bullet": "#4C78A8", "Blitz": "#F58518", "Classical": "#54A24B"}
CALENDAR_ZMAX = 20
REPO_URL = "https://github.com/ErdemAkaySabanci/Lichess_Analyzer"
PLAYER_USERNAME = q.NICKNAME
PLAYER_FULL_NAME = "Kağan Aydınçelebi"
PLAYER = "Kağan"
PLAYER_LINK = f"[{PLAYER_USERNAME}](https://lichess.org/@/{PLAYER_USERNAME})"
ANALYST = "Erdem Akay"

st.set_page_config(page_title="Lichess Performance Analytics", page_icon="♟️", layout="wide")


def pct(x: float) -> str:
    return f"{x:.1%}"


conn = q.get_connection()
min_date, max_date = q.get_date_bounds(conn)
opening_options = q.get_opening_options(conn, min_games=10)

st.title("♟️ Lichess Performance Analytics")
st.markdown(
    f"An end-to-end data analysis of **28,838 games** played on [Lichess.org](https://lichess.org) "
    f"by **{PLAYER_FULL_NAME}**, a Turkish national chess player, under the account "
    f"{PLAYER_LINK}, between {min_date[:4]} and {max_date[:4]}. "
    f"The raw PGN export was cleaned in pandas, loaded into SQLite, and every chart below is a "
    f"SQL query rendered with Plotly. Analysis and dashboard by **{ANALYST}** · "
    f"[code on GitHub]({REPO_URL})"
)

with st.expander("About this analysis — data, pipeline and method"):
    st.markdown(
        f"""
**Data.** The complete game history of {PLAYER_FULL_NAME} ({PLAYER_LINK} on Lichess),
a Turkish national chess player, exported as PGN: one block of metadata tags per game —
players, ratings, titles, time control, ECO opening code, result, termination and UTC timestamp.

**Pipeline.** Raw PGN → parsed and cleaned with pandas → feature engineering (opponent rating
and rating band, piece colour, hour of day, ECO code → opening name) → loaded into SQLite →
parametrized SQL queries (`GROUP BY`, `CASE WHEN`, CTEs, window functions) → Plotly charts.

**Questions this dashboard answers.**
- How active is {PLAYER}, and how has that changed over time?
- How does win rate change as opponents get stronger, and does the White-piece advantage hold at every level?
- Which titled opponents does {PLAYER} beat, and which not?
- Are games won on the clock or over the board?
- Which openings and which hours of the day produce the best results?

**Beyond the dashboard.** The [analysis notebook]({REPO_URL}/blob/main/notebooks/lichess_analysis.ipynb)
adds hypothesis testing (Welch's t-tests) and a logistic regression model on which factors are
associated with winning.

**Reading the numbers.** Win rate is wins ÷ all games, so draws count as non-wins. Bullet,
blitz and classical are separate Lichess rating pools and are never averaged together. All times
are UTC. Charts show sample sizes on hover — small bands and thin wedges are noisy.
"""
    )

with st.sidebar:
    st.header("Filters")
    st.caption("Every chart on the page responds to these.")

    selected_modes = st.multiselect("Time control", options=q.RATED_MODES, default=q.RATED_MODES)
    selected_openings = st.multiselect("Opening (empty = all)", options=opening_options, default=[])
    date_range = st.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
    date_from, date_to = (
        (str(date_range[0]), str(date_range[1])) if len(date_range) == 2 else (min_date, max_date)
    )

    st.divider()
    st.caption(
        f"Data: Lichess PGN export of {PLAYER_FULL_NAME} ({PLAYER_USERNAME}) · "
        f"Analysis: {ANALYST} · Built with pandas, SQLite, Plotly & Streamlit · "
        f"[Repo]({REPO_URL})"
    )

modes = selected_modes or q.RATED_MODES

metrics = q.summary_metrics(conn, modes, selected_openings, date_from, date_to)
mode_df = q.mode_summary(conn, modes, selected_openings, date_from, date_to)
peak, peak_mode = q.peak_rating(conn, modes, selected_openings, date_from, date_to)

if metrics["total_games"] == 0:
    st.warning("No games match the current filters. Widen the date range or clear the opening filter.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Games analysed", f"{metrics['total_games']:,}")
k2.metric("Overall win rate", pct(metrics["win_rate"]))
k3.metric("Peak rating", f"{peak:,}" if peak else "—", peak_mode or None, delta_color="off")
k4.metric(
    "Best opening",
    metrics["best_opening"] if len(metrics["best_opening"]) < 28 else metrics["best_opening"][:26] + "…",
    f"{pct(metrics['best_opening_win_rate'])} over {metrics['best_opening_games']} games",
    delta_color="off",
)

if not mode_df.empty:
    mode_bits = [
        f"**{r.time_control.replace('Rated ', '').replace(' game', '').capitalize()}** "
        f"{pct(r.win_rate)} ({r.games_played:,} games)"
        for r in mode_df.itertuples()
    ]
    st.caption("By time control — " + " · ".join(mode_bits))

st.divider()

# ---------------------------------------------------------------- activity ---
st.header(f"Activity: how much does {PLAYER} play?")

daily_df = q.daily_activity(conn, modes, selected_openings, date_from, date_to)
if not daily_df.empty:
    daily_df["Date"] = pd.to_datetime(daily_df["Date"])
    years = sorted(daily_df["Date"].dt.year.unique(), reverse=True)
    year = st.selectbox("Year", years, index=0)

    year_start, year_end = pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31)
    full = pd.DataFrame({"Date": pd.date_range(year_start, year_end, freq="D")}).merge(
        daily_df, on="Date", how="left"
    )
    full["weekday"] = full["Date"].dt.weekday
    first_monday = year_start - pd.Timedelta(days=year_start.weekday())
    full["week"] = (full["Date"] - first_monday).dt.days // 7

    grid = full.pivot(index="weekday", columns="week", values="games_played").reindex(index=range(7))
    month_ticks = full[full["Date"].dt.day == 1].groupby("week")["Date"].first().dt.strftime("%b")

    fig = go.Figure(
        go.Heatmap(
            z=grid.values,
            x=grid.columns,
            y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            colorscale="Greens",
            zmin=0,
            zmax=CALENDAR_ZMAX,
            xgap=2,
            ygap=2,
            hoverongaps=False,
            hovertemplate="%{y}, week %{x}<br>%{z} games<extra></extra>",
            colorbar=dict(title="Games"),
        )
    )
    fig.update_xaxes(tickmode="array", tickvals=month_ticks.index, ticktext=month_ticks.values)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=260, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    active_days = int(daily_df[daily_df["Date"].dt.year == year].shape[0])
    year_games = int(daily_df[daily_df["Date"].dt.year == year]["games_played"].sum())
    st.caption(
        f"**Calendar heatmap.** {year}: {year_games:,} games across {active_days} active days — "
        f"the colour scale is fixed across every year, so switching years shows real growth, "
        f"not a rescaled version of the same picture."
    )

trend_df = q.activity_trend(conn, modes, selected_openings, date_from, date_to)
if not trend_df.empty:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=trend_df["month"], y=trend_df["games_played"], name="Games played",
               marker_color="#c6dbef")
    )
    fig.add_trace(
        go.Scatter(x=trend_df["month"], y=trend_df["games_3mo_moving_avg"], name="3-month average",
                   mode="lines", line=dict(color="#08519c", width=2.5))
    )
    fig.update_layout(
        height=300, margin=dict(t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis_title="Games per month",
    )
    st.plotly_chart(fig, use_container_width=True)
    busiest = trend_df.loc[trend_df["games_played"].idxmax()]
    st.caption(
        f"**Monthly volume with a 3-month rolling average.** Busiest month: "
        f"{busiest['month']} with {int(busiest['games_played']):,} games."
    )

st.divider()

# ----------------------------------------------------------------- strength ---
st.header("Strength: how does performance change against stronger opponents?")

elo_traj = q.elo_trajectory(conn, modes, selected_openings, date_from, date_to)
if not elo_traj.empty:
    fig = go.Figure()
    for mode_label, sub in elo_traj.groupby("mode"):
        if len(sub) < 20:  # a two-point "trajectory" is noise, not a trend
            continue
        sub = sub.sort_values("Date")
        color = MODE_COLORS.get(mode_label, "#4C78A8")
        fig.add_trace(
            go.Scatter(x=pd.to_datetime(sub["Date"]), y=sub["player_elo"], mode="lines",
                       name=mode_label, line=dict(color=color, width=1.5))
        )
        peak_row = sub.loc[sub["player_elo"].idxmax()]
        fig.add_trace(
            go.Scatter(
                x=[pd.to_datetime(peak_row["Date"])], y=[peak_row["player_elo"]],
                mode="markers+text", marker=dict(color=color, size=11, symbol="star"),
                text=[f" peak {int(peak_row['player_elo']):,}"], textposition="middle right",
                showlegend=False, hoverinfo="skip",
            )
        )
    fig.update_layout(
        height=380, margin=dict(t=10, b=10), yaxis_title="Rating",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Rating trajectory (end-of-day rating, one line per pool).** Bullet and blitz are "
        "separate Lichess rating pools, so they are never averaged together."
    )

elo_df = q.winrate_by_elo_range(conn, modes, selected_openings, date_from, date_to)
if not elo_df.empty:
    z = [elo_df["win_rate"].tolist()]
    fig = go.Figure(
        go.Heatmap(
            z=z, x=elo_df["opponent_elo_range"], y=["Win rate"],
            colorscale="YlGnBu", zmin=0, zmax=1,
            text=z, texttemplate="%{text:.0%}", textfont=dict(size=13),
            customdata=[elo_df["games_played"].tolist()],
            hovertemplate="%{x}<br>Win rate %{z:.1%}<br>%{customdata} games<extra></extra>",
            colorbar=dict(title="Win rate", tickformat=".0%"),
        )
    )
    fig.update_layout(height=180, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Single-row heatmap strip.** One ordered scale, no bar-height comparison needed — "
        "the drop-off as opponents get stronger reads instantly. Hover for sample sizes; "
        "the left-hand bands are small and noisy."
    )

st.divider()

# ------------------------------------------------------------ opponents ---
st.header(f"Opponents: who does {PLAYER} beat?")

title_df = q.winrate_by_opponent_title(conn, modes, selected_openings, date_from, date_to)
if title_df.empty:
    st.info("No titled opponents in the current filter.")
else:
    fig = go.Figure()
    for _, row in title_df.iterrows():
        fig.add_trace(
            go.Scatter(x=[row["opp_title"]] * 2, y=[0, row["win_rate"]], mode="lines",
                       line=dict(color="#d9d9d9", width=2), showlegend=False, hoverinfo="skip")
        )
    fig.add_trace(
        go.Scatter(
            x=title_df["opp_title"], y=title_df["win_rate"], mode="markers+text",
            marker=dict(
                size=np.sqrt(title_df["games_played"]) * 2.6,
                color=title_df["win_rate"], colorscale="RdYlGn", cmin=0.2, cmax=0.7,
                line=dict(color="black", width=1), showscale=False,
            ),
            text=[f"{r:.0%}<br>n={n:,}" for r, n in
                  zip(title_df["win_rate"], title_df["games_played"])],
            textposition="top center", showlegend=False,
            hovertemplate="%{x}<br>Win rate %{y:.1%}<extra></extra>",
        )
    )
    fig.add_hline(y=0.5, line_dash="dash", line_color="gray",
                  annotation_text="50%", annotation_position="top left")
    fig.update_yaxes(tickformat=".0%", range=[0, 0.9], title="Win rate")
    fig.update_xaxes(title="Opponent title (ordered by their average rating)")
    fig.update_layout(height=480, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    gm = title_df[title_df["opp_title"] == "GM"]
    gm_bit = (
        f" Against Grandmasters specifically: {pct(gm.iloc[0]['win_rate'])} "
        f"over {int(gm.iloc[0]['games_played']):,} games."
        if not gm.empty else ""
    )
    st.caption(
        "**Bubble chart with sample size encoded.** Bubble area is the number of games, so a "
        "flattering win rate built on a thin sample can't hide behind a tall bar." + gm_bit
    )

ce_df = q.winrate_by_color_and_elo(conn, modes, selected_openings, date_from, date_to)
if ce_df.empty:
    st.info("Not enough data for the colour comparison in the current filter.")
else:
    wide = ce_df.pivot_table(
        index=["elo_band", "sort_key"], columns="PlayerColor", values="win_rate"
    ).reset_index().sort_values("sort_key")

    if {"White", "Black"}.issubset(wide.columns):
        band_order = wide["elo_band"].tolist()
        line_x, line_y = [], []
        for _, r in wide.iterrows():
            line_x += [r["Black"], r["White"], None]
            line_y += [r["elo_band"], r["elo_band"], None]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=line_x, y=line_y, mode="lines",
                                 line=dict(color="#d9d9d9", width=3), hoverinfo="skip",
                                 showlegend=False))
        fig.add_trace(go.Scatter(
            x=wide["Black"], y=wide["elo_band"], mode="markers", name="as Black",
            marker=dict(color=BLACK_PIECE, size=15, line=dict(color="black", width=1)),
            hovertemplate="as Black · %{y}<br>Win rate %{x:.1%}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=wide["White"], y=wide["elo_band"], mode="markers", name="as White",
            marker=dict(color=WHITE_PIECE, size=15, line=dict(color="black", width=1.5)),
            hovertemplate="as White · %{y}<br>Win rate %{x:.1%}<extra></extra>",
        ))
        for _, r in wide.iterrows():
            gap = (r["White"] - r["Black"]) * 100
            fig.add_annotation(
                x=max(r["White"], r["Black"]), y=r["elo_band"], text=f"  +{gap:.1f}pp",
                showarrow=False, xanchor="left", font=dict(size=12, color="#444"),
            )
        fig.update_yaxes(categoryorder="array", categoryarray=band_order,
                         title="Opponent rating band")
        fig.update_xaxes(tickformat=".0%", title="Win rate",
                         range=[0, max(wide[["White", "Black"]].max()) + 0.15])
        fig.update_layout(height=430, margin=dict(t=30, b=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

        avg_gap = (wide["White"] - wide["Black"]).mean() * 100
        st.caption(
            f"**Cleveland paired dot plot.** As a single pair of bars this was two numbers and "
            f"nothing to see. Split across opponent strength it becomes a finding: the "
            f"first-move advantage holds in every band, averaging **+{avg_gap:.1f} points**."
        )
    else:
        st.info("Both colours are needed for this comparison.")

st.divider()

# ---------------------------------------------------------- how games end ---
st.header("Terminations: are games won on the clock or over the board?")

term_df = q.termination_composition(conn, modes, selected_openings, date_from, date_to)
if not term_df.empty:
    total = term_df["games_played"].sum()
    term_df = term_df.copy()
    term_df["width"] = term_df["games_played"] / total
    term_df["center"] = term_df["width"].cumsum() - term_df["width"] / 2
    for part in ("wins", "draws", "losses"):
        term_df[f"{part}_share"] = term_df[part] / term_df["games_played"]

    # a small gutter between columns so the mosaic reads as separate blocks
    gutter = 0.012
    term_df["draw_width"] = (term_df["width"] - gutter).clip(lower=0.01)

    fig = go.Figure()
    for part, color, label, text_color in (
        ("wins", WIN, "Win", "white"),
        ("draws", DRAW, "Draw", "#333"),
        ("losses", LOSS, "Loss", "white"),
    ):
        share = term_df[f"{part}_share"]
        # only label a block that is tall enough to hold the text
        labels = [f"{s:.0%}" if s >= 0.08 else "" for s in share]
        fig.add_trace(
            go.Bar(
                x=term_df["center"], y=share, width=term_df["draw_width"],
                name=label, marker_color=color,
                text=labels, textposition="inside", insidetextanchor="middle",
                textfont=dict(color=text_color, size=15),
                customdata=np.stack([term_df["termination"], term_df[part]], axis=-1),
                hovertemplate="%{customdata[0]} · " + label
                              + "<br>%{y:.1%} (%{customdata[1]:,} games)<extra></extra>",
            )
        )
    for _, r in term_df.iterrows():
        # yref="paper" keeps the label above the plot instead of clipping it at y=1
        fig.add_annotation(
            x=r["center"], y=1.16, yref="paper", showarrow=False,
            text=f"<b>{r['termination']}</b><br>{r['width']:.0%} of games ({int(r['games_played']):,})",
            font=dict(size=12),
        )
    fig.update_layout(
        barmode="stack", height=460, margin=dict(t=115, b=10), bargap=0,
        legend=dict(orientation="h", yanchor="bottom", y=-0.18),
    )
    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(tickformat=".0%", title="Share of that column's games", range=[0, 1])
    st.plotly_chart(fig, use_container_width=True)

    normal = term_df[term_df["termination"] == "Normal"]
    forfeit = term_df[term_df["termination"] == "Time forfeit"]
    if not normal.empty and not forfeit.empty:
        st.caption(
            f"**Marimekko / mosaic plot — column width is volume, column height is composition.** "
            f"This chart overturned an early hypothesis of this analysis, that time pressure was "
            f"{PLAYER}'s weakness. Games decided on the clock are a "
            f"**{pct(forfeit.iloc[0]['wins_share'])} win rate**, against "
            f"**{pct(normal.iloc[0]['wins_share'])}** when a game is decided over the board: "
            f"the clock is where {PLAYER} wins, and being outplayed is where the losses come from."
        )
    else:
        st.caption(
            "**Marimekko / mosaic plot.** Column width is each termination type's share of all "
            "games; column height is its win/draw/loss composition."
        )

st.divider()

# ------------------------------------------------------- what and when ---
st.header(f"Openings and timing: what and when does {PLAYER} win?")

opening_df = q.winrate_by_opening(conn, modes, selected_openings, date_from, date_to, top_n=25)
if opening_df.empty:
    st.info("No openings pass the 10-game threshold in the current filter.")
else:
    fig = px.treemap(
        opening_df, path=["Opening"], values="games_played", color="win_rate",
        # 0.3-0.7 keeps 50% exactly on the grey midpoint while giving the
        # near-breakeven majority of openings visible colour separation
        color_continuous_scale=[[0, LOSS], [0.5, "#d9d9d9"], [1, WIN]], range_color=[0.3, 0.7],
        hover_data=["games_played", "win_rate"],
    )
    fig.update_traces(textinfo="label+percent entry")
    fig.update_layout(height=520, margin=dict(t=10, b=10, l=0, r=0),
                      coloraxis_colorbar=dict(title="Win rate", tickformat=".0%"))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Treemap.** Tile size is how often an opening is played, colour is how well it does — "
        "grey sits at exactly 50%, so the colour midpoint means 'break even' rather than "
        "'middling'."
    )

hour_df = q.winrate_by_hour(conn, modes, selected_openings, date_from, date_to)
if hour_df.empty:
    st.info("No games in the current filter.")
else:
    hour_df = pd.merge(pd.DataFrame({"Hour": range(24)}), hour_df, on="Hour", how="left").fillna(0)
    hour_df["HourLabel"] = hour_df["Hour"].apply(lambda h: f"{int(h):02d}:00")
    fig = px.bar_polar(
        hour_df, r="win_rate", theta="HourLabel", color="win_rate",
        color_continuous_scale="Purples", hover_data=["games_played"],
        labels={"win_rate": "Win rate", "HourLabel": "Hour (UTC)"},
    )
    fig.update_layout(
        height=560, margin=dict(t=20, b=20),
        polar=dict(radialaxis=dict(tickformat=".0%")),
        coloraxis_colorbar=dict(title="Win rate", tickformat=".0%"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Polar rose.** Hours wrap around a circle, so a circular axis fits the data better "
        "than a bar chart that cuts midnight in half. Thin wedges are thin samples."
    )

st.divider()

# ------------------------------------------------------------- experiments ---
st.header("A/B Testing: is it skill, or could it be chance?")
st.markdown(
    "**How an A/B test maps onto this data.** Group A and group B are two sets of games, the "
    "metric is win rate, and the question is whether the gap between them is real or just noise. "
    "Test 1 is a genuine A/B test: the \"treatment\" is the piece colour, and Lichess assigns it "
    "at random, so the groups are comparable by design. Test 2 has no randomization, so it is a "
    "quasi-experiment and is read as association, not cause. Both use the standard A/B toolkit: "
    "two-proportion z-test, confidence intervals, odds ratio, sample-ratio check, A/A test and "
    "power analysis."
)

MIN_ARM = 30  # games per group below which a test is not worth reporting
MODE_SHORT = {"Rated bullet game": "Bullet", "Rated blitz game": "Blitz", "Rated classical game": "Classical"}


def fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


# ---- test 1: White vs Black ------------------------------------------------
st.subheader("A/B test 1 · White (A) vs Black (B)")
color_df = q.color_experiment(conn, modes, selected_openings, date_from, date_to)

arms = []
for label, sub in [(MODE_SHORT.get(m, m), g) for m, g in color_df.groupby("time_control")] + [
    ("All selected", color_df.groupby("PlayerColor")[["games_played", "wins"]].sum().reset_index())
]:
    by_color = sub.set_index("PlayerColor")
    if {"White", "Black"} <= set(by_color.index) and by_color["games_played"].min() >= MIN_ARM:
        arms.append((label, stats.two_proportion_test(
            by_color.loc["White", "wins"], by_color.loc["White", "games_played"],
            by_color.loc["Black", "wins"], by_color.loc["Black", "games_played"],
        ), by_color["games_played"].sum(), by_color.loc["White", "games_played"]))

if not arms:
    st.info(f"Each colour needs at least {MIN_ARM} games in the current filter for this test.")
else:
    label, overall, total_n, white_n = arms[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("White minus Black win rate", f"{overall.diff * 100:+.1f} pp")
    c2.metric("95% confidence interval", f"{overall.ci_low * 100:+.1f} to {overall.ci_high * 100:+.1f} pp")
    c3.metric("p-value", fmt_p(overall.p_value))
    c4.metric(f"Odds ratio (95% CI {overall.or_ci_low:.2f}–{overall.or_ci_high:.2f})",
              f"{overall.odds_ratio:.2f}")

    fig = go.Figure()
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    fig.add_trace(go.Scatter(
        x=[a[1].diff * 100 for a in arms], y=[a[0] for a in arms], mode="markers",
        marker=dict(size=13, color=[MODE_COLORS.get(a[0], "#444") for a in arms],
                    line=dict(color="black", width=1)),
        error_x=dict(type="data", symmetric=False, thickness=2.5, color="#777",
                     array=[(a[1].ci_high - a[1].diff) * 100 for a in arms],
                     arrayminus=[(a[1].diff - a[1].ci_low) * 100 for a in arms]),
        customdata=np.array([[a[1].n_a, a[1].n_b, a[1].p_value] for a in arms]),
        hovertemplate="%{y}<br>White − Black: %{x:+.1f} pp<br>"
                      "%{customdata[0]:,} White vs %{customdata[1]:,} Black games<extra></extra>",
        showlegend=False,
    ))
    fig.update_xaxes(title="White-piece advantage, win-rate difference (percentage points)",
                     zeroline=False)
    fig.update_layout(height=120 + 70 * len(arms), margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    srm_p = stats.share_vs_half_pvalue(int(white_n), int(total_n))
    st.caption(
        f"**Forest plot: point estimate with 95% interval per time control.** An interval that "
        f"stays clear of the zero line means the White advantage is unlikely to be chance. "
        f"Sample-ratio check: {white_n / total_n:.1%} of the {int(total_n):,} games were as White "
        f"(p = {srm_p:.2f} against a 50/50 split), so colour assignment looks random as expected."
    )

# ---- test 2: streaks -------------------------------------------------------
st.subheader("Quasi-experiment 2 · After a win (A) vs after a loss (B)")
tilt_df = q.tilt_experiment(conn, modes, selected_openings, date_from, date_to)

tilt_total = tilt_df.groupby("PrevResult").agg(
    games_played=("games_played", "sum"), wins=("wins", "sum")
)
tilt_total["avg_opponent_elo"] = (
    (tilt_df["avg_opponent_elo"] * tilt_df["games_played"]).groupby(tilt_df["PrevResult"]).sum()
    / tilt_total["games_played"]
)

if not {"win", "loss"} <= set(tilt_total.index) or tilt_total.loc[["win", "loss"], "games_played"].min() < MIN_ARM:
    st.info(f"Streak analysis needs at least {MIN_ARM} games after a win and after a loss.")
else:
    crude = stats.two_proportion_test(
        tilt_total.loc["win", "wins"], tilt_total.loc["win", "games_played"],
        tilt_total.loc["loss", "wins"], tilt_total.loc["loss", "games_played"],
    )
    strata = []
    for _, band in tilt_df.groupby("elo_band"):
        b = band.set_index("PrevResult")
        if {"win", "loss"} <= set(b.index):
            strata.append((b.loc["win", "wins"], b.loc["win", "games_played"],
                           b.loc["loss", "wins"], b.loc["loss", "games_played"]))
    adjusted = stats.stratified_diff(strata)

    t1, t2, t3 = st.columns(3)
    t1.metric(f"After a win vs a loss (95% CI {crude.ci_low * 100:+.1f} to {crude.ci_high * 100:+.1f})",
              f"{crude.diff * 100:+.1f} pp")
    if adjusted:
        t2.metric(f"Within opponent-rating bands (95% CI {adjusted[1] * 100:+.1f} to {adjusted[2] * 100:+.1f})",
                  f"{adjusted[0] * 100:+.1f} pp")
    t3.metric("p-value (raw gap)", fmt_p(crude.p_value))

    order = [r for r in ("loss", "draw", "win") if r in tilt_total.index]
    rows = tilt_total.loc[order]
    cis = [stats.wilson_ci(int(r.wins), int(r.games_played)) for r in rows.itertuples()]
    rates = rows["wins"] / rows["games_played"]
    fig = go.Figure()
    fig.add_hline(y=0.5, line_dash="dash", line_color="gray")
    fig.add_trace(go.Scatter(
        x=[f"after a {r}" for r in order], y=rates, mode="markers",
        marker=dict(size=14, color=[LOSS if r == "loss" else DRAW if r == "draw" else WIN for r in order],
                    line=dict(color="black", width=1)),
        error_y=dict(type="data", symmetric=False, thickness=2.5, color="#777",
                     array=[hi - r for (lo, hi), r in zip(cis, rates)],
                     arrayminus=[r - lo for (lo, hi), r in zip(cis, rates)]),
        customdata=np.stack([rows["games_played"], rows["avg_opponent_elo"]], axis=-1),
        hovertemplate="%{x}<br>Win rate %{y:.1%}<br>%{customdata[0]:,} games · "
                      "avg opponent %{customdata[1]:.0f}<extra></extra>",
        showlegend=False,
    ))
    fig.update_yaxes(tickformat=".0%", title="Win rate (95% interval)")
    fig.update_layout(height=340, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    elo_gap = rows.loc["win", "avg_opponent_elo"] - rows.loc["loss", "avg_opponent_elo"] if {"win", "loss"} <= set(rows.index) else 0
    st.caption(
        f"**Win rate by the previous game's result, within one session** (games starting less than "
        f"30 minutes apart; a session's first game is excluded). This is correlation, not tilt or "
        f"momentum proven: the next opponent is {abs(elo_gap):.0f} rating points "
        f"{'weaker' if elo_gap < 0 else 'stronger'} after a win than after a loss, which inflates the raw gap, "
        f"so the second metric compares like with like inside opponent-rating bands. What remains "
        f"could be form, focus or rating-pool matchmaking; the data can't separate them."
    )

# ---- method checks ---------------------------------------------------------
st.subheader("Method checks")


@st.cache_data(show_spinner=False)
def aa_rate(modes_key, openings_key, d_from, d_to):
    return stats.aa_false_positive_rate(
        q.win_flags(q.get_connection(), list(modes_key), list(openings_key), d_from, d_to)
    )


wins_n = metrics["total_games"]
m1, m2, m3 = st.columns(3)
if wins_n >= 2 * MIN_ARM:
    m1.metric("A/A test false-positive rate (target ≈ 5%)",
              f"{aa_rate(tuple(modes), tuple(selected_openings), date_from, date_to):.1%}")
base = metrics["win_rate"]
arm_n = max(wins_n // 2, 1)
m2.metric(f"Smallest detectable gap ({arm_n:,} games per group, 80% power)",
          f"{stats.minimum_detectable_diff(arm_n, base) * 100:.1f} pp")
if 0 < base < 1 and base + 0.02 < 1:
    m3.metric("Games per group needed to detect 2 pp",
              f"{stats.required_n_per_group(base, base + 0.02):,}")
st.caption(
    "**Does the test itself behave?** An A/A test splits the very same games at random into two "
    "halves and counts how often the z-test wrongly reports a difference; a sound test does so "
    "about 5% of the time. The other two numbers are the power analysis: how small a gap this much "
    "data can reliably detect, and how many games per group a 2-point difference would need."
)

# ---- design implications ---------------------------------------------------
st.subheader("From findings to design hypotheses")
st.markdown(
    "Treating these results as player-behaviour data from a competitive game, each one suggests a "
    "design question and the A/B test that would answer it. These are hypotheses to test, not "
    "conclusions this dataset can prove (figures are for the full history)."
)
d1, d2, d3 = st.columns(3)
d1.markdown(
    """
**Balance: first-move advantage**

*Finding.* White wins about 5 points more often, and the gap holds across time controls.

*Design question.* Does the advantage make matchmaking feel unfair, and does a small
compensation for the second player (e.g. a rating or reward adjustment) reduce it?

*Test.* Randomize compensation for the second player; metric: win-rate gap and
games played per day; guardrail: overall win rate.
"""
)
d2.markdown(
    """
**Engagement: results carry over**

*Finding.* The next game is won more often after a win than after a loss, even within the
same opponent-strength band.

*Design question.* Is momentum a retention lever, and does a loss need a softer landing
(easier next match, a short recap) so players keep going?

*Test.* Randomize the next-opponent difficulty after a loss; metric: share of players who
start another game within 30 minutes; guardrail: session win rate.
"""
)
d3.markdown(
    """
**Mechanics: the clock decides games**

*Finding.* Games decided on the clock are won far more often than games decided over the
board (see Terminations above).

*Design question.* Is time pressure a skill being rewarded or a frustration being created,
and does a time bonus per move change how games end?

*Test.* Randomize the increment between players of the same rating; metric: share of
games ending on time and completion rate.
"""
)
st.caption(
    "Every test above would need a pre-test power analysis like the one in this section "
    "and a sample-ratio check after launch."
)

st.divider()

with st.expander("Underlying data tables"):
    st.write("Win rate by time control", mode_df)
    st.write("Win rate by opponent Elo range", elo_df)
    st.write("Win rate by colour and Elo band", ce_df)
    st.write("Win rate by opponent title", title_df)
    st.write("Termination composition", term_df)
    st.write("Top openings", opening_df)
    st.write("Win rate by hour", hour_df)
    st.write("Colour experiment counts", color_df)
    st.write("Streak experiment counts", tilt_df)
    st.write("Monthly activity trend", trend_df)

st.caption(
    f"Raw data: PGN export of {PLAYER_FULL_NAME}'s Lichess history ({PLAYER_USERNAME}) · cleaning in pandas · "
    f"analysis layer in SQL over SQLite · charts in Plotly · app in Streamlit · "
    f"analysis by {ANALYST} · [notebook, SQL queries and source]({REPO_URL})"
)
