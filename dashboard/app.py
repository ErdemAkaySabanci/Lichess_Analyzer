"""Streamlit dashboard for the Lichess game history portfolio project.

Run from the repo root:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queries as q

st.set_page_config(page_title="Lichess Performance Dashboard", layout="wide")

st.title("Lichess Bullet/Blitz Performance Dashboard")
st.caption(
    "Interactive view of ~28,800 games exported from Lichess.org, backed by "
    "SQL queries (`dashboard/queries.py`) against `sql/lichess.db`."
)

conn = q.get_connection()
min_date, max_date = q.get_date_bounds(conn)
opening_options = q.get_opening_options(conn, min_games=10)

with st.sidebar:
    st.header("Filters")

    selected_modes = st.multiselect(
        "Time control",
        options=q.RATED_MODES,
        default=q.RATED_MODES,
    )

    selected_openings = st.multiselect(
        "Opening (leave empty = all)",
        options=opening_options,
        default=[],
    )

    date_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    date_from, date_to = (str(date_range[0]), str(date_range[1])) if len(date_range) == 2 else (min_date, max_date)

modes = selected_modes or q.RATED_MODES

metrics = q.summary_metrics(conn, modes, selected_openings, date_from, date_to)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total games", f"{metrics['total_games']:,}")
col2.metric("Win rate", f"{metrics['win_rate']:.1%}")
col3.metric(
    "Best opening (min. 10 games)",
    metrics["best_opening"],
    f"{metrics['best_opening_win_rate']:.1%} win rate",
)
col4.metric("Best-opening sample size", f"{metrics['best_opening_games']} games")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Win rate by time control")
    mode_df = q.winrate_by_mode(conn, modes, selected_openings, date_from, date_to)
    fig = px.bar(
        mode_df, x="time_control", y="win_rate", color="win_rate",
        text="games_played", color_continuous_scale="Blues",
        labels={"win_rate": "Win Rate", "time_control": "Time Control"},
    )
    fig.update_traces(texttemplate="%{text} games", textposition="outside")
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("White vs. Black win rate")
    color_df = q.winrate_by_color(conn, modes, selected_openings, date_from, date_to)
    fig = px.bar(
        color_df, x="PlayerColor", y="win_rate", color="PlayerColor",
        text="games_played",
        color_discrete_map={"White": "#dfe6e9", "Black": "#2d3436"},
        labels={"win_rate": "Win Rate", "PlayerColor": "Piece Color"},
    )
    fig.update_traces(texttemplate="%{text} games", textposition="outside", marker_line_color="black", marker_line_width=1)
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

left2, right2 = st.columns(2)

with left2:
    st.subheader("Win rate by opponent Elo range")
    elo_df = q.winrate_by_elo_range(conn, modes, selected_openings, date_from, date_to)
    fig = px.bar(
        elo_df, x="opponent_elo_range", y="win_rate", color="win_rate",
        text="games_played", color_continuous_scale="YlGnBu",
        labels={"win_rate": "Win Rate", "opponent_elo_range": "Opponent Elo Range"},
    )
    fig.update_traces(texttemplate="%{text} games", textposition="outside")
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

with right2:
    st.subheader("Win rate by hour of day (UTC)")
    hour_df = q.winrate_by_hour(conn, modes, selected_openings, date_from, date_to)
    hour_df = pd.merge(pd.DataFrame({"Hour": range(24)}), hour_df, on="Hour", how="left").fillna(0)
    hour_df["HourLabel"] = hour_df["Hour"].apply(lambda h: f"{h:02d}:00")
    fig = px.bar_polar(
        hour_df, r="win_rate", theta="HourLabel", color="win_rate",
        color_continuous_scale="Purples", hover_data=["games_played"],
        labels={"win_rate": "Win Rate", "HourLabel": "Hour (UTC)"},
    )
    fig.update_layout(polar=dict(radialaxis=dict(tickformat=".0%")))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Top openings — size = games played, color = win rate (min. 10 games)")
opening_df = q.winrate_by_opening(conn, modes, selected_openings, date_from, date_to, top_n=25)
fig = px.treemap(
    opening_df, path=["Opening"], values="games_played", color="win_rate",
    color_continuous_scale="RdYlGn", range_color=[0, 1],
    hover_data=["games_played", "win_rate"],
)
fig.update_traces(textinfo="label+percent entry")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Activity & win rate over time")
trend_df = q.activity_trend(conn, modes, selected_openings, date_from, date_to)
fig = px.line(
    trend_df, x="month", y=["games_played", "games_3mo_moving_avg"],
    labels={"value": "Games Played", "month": "Month", "variable": ""},
)
fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(fig, use_container_width=True)

with st.expander("Show underlying data tables"):
    st.write("Win rate by time control", mode_df)
    st.write("White vs. Black win rate", color_df)
    st.write("Win rate by opponent Elo range", elo_df)
    st.write("Win rate by hour", hour_df)
    st.write("Top openings", opening_df)
    st.write("Monthly activity trend", trend_df)
