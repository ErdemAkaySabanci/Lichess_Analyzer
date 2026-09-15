"""Parametrized SQL queries backing the Streamlit dashboard.

Every function here runs a GROUP BY / CASE WHEN query against the same
`sql/lichess.db` SQLite database built by `sql/build_database.py`, filtered
to whatever time control / opening / date range the user picked in the
sidebar. They are the interactive counterparts of the fixed analyses in
`/sql/*.sql`.
"""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "sql" / "lichess.db"

RATED_MODES = ["Rated bullet game", "Rated blitz game", "Rated classical game"]


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _where_clause(modes: list[str], openings: list[str], date_from: str, date_to: str):
    clauses = ["Date BETWEEN ? AND ?"]
    params: list = [date_from, date_to]

    if modes:
        clauses.append(f"Event IN ({','.join('?' for _ in modes)})")
        params.extend(modes)

    if openings:
        clauses.append(f"Opening IN ({','.join('?' for _ in openings)})")
        params.extend(openings)

    return " AND ".join(clauses), params


def get_date_bounds(conn: sqlite3.Connection) -> tuple[str, str]:
    row = conn.execute("SELECT MIN(Date), MAX(Date) FROM games WHERE Date IS NOT NULL").fetchone()
    return row[0], row[1]


def get_opening_options(conn: sqlite3.Connection, min_games: int = 10) -> list[str]:
    query = """
        SELECT Opening
        FROM games
        WHERE Event IN ({modes})
        GROUP BY Opening
        HAVING COUNT(*) >= ?
        ORDER BY COUNT(*) DESC
    """.format(modes=",".join("?" for _ in RATED_MODES))
    df = pd.read_sql_query(query, conn, params=[*RATED_MODES, min_games])
    return df["Opening"].tolist()


def summary_metrics(conn, modes, openings, date_from, date_to) -> dict:
    where, params = _where_clause(modes, openings, date_from, date_to)
    query = f"""
        SELECT
            COUNT(*) AS total_games,
            ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
        FROM games
        WHERE {where}
    """
    row = conn.execute(query, params).fetchone()
    total_games, win_rate = row

    best_opening_query = f"""
        SELECT Opening, COUNT(*) AS games_played,
               ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
        FROM games
        WHERE {where}
        GROUP BY Opening
        HAVING COUNT(*) >= 10
        ORDER BY win_rate DESC
        LIMIT 1
    """
    best = conn.execute(best_opening_query, params).fetchone()

    return {
        "total_games": total_games or 0,
        "win_rate": win_rate or 0.0,
        "best_opening": best[0] if best else "N/A",
        "best_opening_win_rate": best[2] if best else 0.0,
        "best_opening_games": best[1] if best else 0,
    }


def winrate_by_mode(conn, modes, openings, date_from, date_to) -> pd.DataFrame:
    where, params = _where_clause(modes, openings, date_from, date_to)
    query = f"""
        SELECT
            Event AS time_control,
            COUNT(*) AS games_played,
            ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
        FROM games
        WHERE {where}
        GROUP BY Event
        ORDER BY win_rate DESC
    """
    return pd.read_sql_query(query, conn, params=params)


def winrate_by_opening(conn, modes, openings, date_from, date_to, top_n: int = 15) -> pd.DataFrame:
    where, params = _where_clause(modes, openings, date_from, date_to)
    query = f"""
        SELECT
            Opening,
            COUNT(*) AS games_played,
            ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
        FROM games
        WHERE {where}
        GROUP BY Opening
        HAVING COUNT(*) >= 10
        ORDER BY win_rate DESC
        LIMIT {int(top_n)}
    """
    return pd.read_sql_query(query, conn, params=params)


def winrate_by_elo_range(conn, modes, openings, date_from, date_to) -> pd.DataFrame:
    where, params = _where_clause(modes, openings, date_from, date_to)
    query = f"""
        SELECT
            CASE
                WHEN OpponentElo < 1200 THEN '<1200'
                WHEN OpponentElo < 1400 THEN '1200-1399'
                WHEN OpponentElo < 1600 THEN '1400-1599'
                WHEN OpponentElo < 1800 THEN '1600-1799'
                WHEN OpponentElo < 2000 THEN '1800-1999'
                WHEN OpponentElo < 2200 THEN '2000-2199'
                WHEN OpponentElo < 2400 THEN '2200-2399'
                WHEN OpponentElo < 2600 THEN '2400-2599'
                WHEN OpponentElo < 2800 THEN '2600-2799'
                WHEN OpponentElo < 3000 THEN '2800-2999'
                ELSE '3000+'
            END AS opponent_elo_range,
            MIN(OpponentElo) AS sort_key,
            COUNT(*) AS games_played,
            ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
        FROM games
        WHERE {where} AND OpponentElo IS NOT NULL
        GROUP BY opponent_elo_range
        ORDER BY sort_key
    """
    return pd.read_sql_query(query, conn, params=params)


def winrate_by_hour(conn, modes, openings, date_from, date_to) -> pd.DataFrame:
    where, params = _where_clause(modes, openings, date_from, date_to)
    query = f"""
        SELECT
            Hour,
            COUNT(*) AS games_played,
            ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
        FROM games
        WHERE {where}
        GROUP BY Hour
        ORDER BY Hour
    """
    return pd.read_sql_query(query, conn, params=params)


def winrate_by_color(conn, modes, openings, date_from, date_to) -> pd.DataFrame:
    where, params = _where_clause(modes, openings, date_from, date_to)
    query = f"""
        SELECT
            PlayerColor,
            COUNT(*) AS games_played,
            ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
        FROM games
        WHERE {where}
        GROUP BY PlayerColor
        ORDER BY PlayerColor DESC
    """
    return pd.read_sql_query(query, conn, params=params)


def activity_trend(conn, modes, openings, date_from, date_to) -> pd.DataFrame:
    where, params = _where_clause(modes, openings, date_from, date_to)
    query = f"""
        WITH monthly AS (
            SELECT
                strftime('%Y-%m', Date) AS month,
                COUNT(*) AS games_played,
                ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
            FROM games
            WHERE {where}
            GROUP BY month
        )
        SELECT
            month,
            games_played,
            win_rate,
            ROUND(AVG(games_played) OVER (
                ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
            ), 1) AS games_3mo_moving_avg
        FROM monthly
        ORDER BY month
    """
    return pd.read_sql_query(query, conn, params=params)
