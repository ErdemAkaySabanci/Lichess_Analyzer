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

WIN, DRAW, LOSS = "#1a9850", "#bdbdbd", "#d73027"
WHITE_PIECE, BLACK_PIECE = "#e8eced", "#2d3436"
MODE_COLORS = {"Bullet": "#4C78A8", "Blitz": "#F58518", "Classical": "#54A24B"}
CALENDAR_ZMAX = 20
REPO_URL = "https://github.com/ErdemAkaySabanci/Lichess_Analyzer"

st.set_page_config(page_title="Lichess Performance Dashboard", page_icon="♟️", layout="wide")


def pct(x: float) -> str:
    return f"{x:.1%}"


st.title("♟️ Eight years of bullet chess, as data")
st.markdown(
    f"**28,838 games** played on [Lichess.org](https://lichess.org) between 2016 and 2024, "
    f"exported as raw PGN and rebuilt into a cleaned dataset, a SQL layer and this dashboard. "
    f"Every chart below is a SQL query against `sql/lichess.db` — [code on GitHub]({REPO_URL})."
)

conn = q.get_connection()
min_date, max_date = q.get_date_bounds(conn)
opening_options = q.get_opening_options(conn, min_games=10)

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
        f"Data: Lichess PGN export · Built with pandas, SQLite, Plotly & Streamlit · "
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
st.header("How much do I actually play?")

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
st.header("How strong am I, really?")

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

# ------------------------------------------------------------- who I beat ---
st.header("Who can I actually beat?")

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
st.header("How do my games end?")

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
            f"This is the chart that corrected me. I had written that time pressure was my weakness; "
            f"games decided on the clock are actually a "
            f"**{pct(forfeit.iloc[0]['wins_share'])} win rate** against "
            f"**{pct(normal.iloc[0]['wins_share'])}** when a game is decided over the board. "
            f"The clock is where I win — being outplayed is where I lose."
        )
    else:
        st.caption(
            "**Marimekko / mosaic plot.** Column width is each termination type's share of all "
            "games; column height is its win/draw/loss composition."
        )

st.divider()

# ------------------------------------------------------- what and when ---
st.header("What and when do I play?")

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

with st.expander("Underlying data tables"):
    st.write("Win rate by time control", mode_df)
    st.write("Win rate by opponent Elo range", elo_df)
    st.write("Win rate by colour and Elo band", ce_df)
    st.write("Win rate by opponent title", title_df)
    st.write("Termination composition", term_df)
    st.write("Top openings", opening_df)
    st.write("Win rate by hour", hour_df)
    st.write("Monthly activity trend", trend_df)

st.caption(
    f"Raw data: personal PGN export from Lichess.org · cleaning in pandas · "
    f"analysis layer in SQL over SQLite · charts in Plotly · app in Streamlit · "
    f"[notebook, SQL queries and source]({REPO_URL})"
)
