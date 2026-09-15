"""
Shared data pipeline for the Lichess game history portfolio project.

This module is the single source of truth for turning the raw Lichess PGN
export into the cleaned, feature-enriched dataset used by the notebook,
the SQLite build script, and the Streamlit dashboard.

Sections marked "[RECONSTRUCTED]" reproduce logic that existed in the
original analysis notebook (as evidenced by its cached outputs and
downstream cell references) but whose source cells were missing from the
saved .ipynb file. They are re-implemented here with the most natural
interpretation of the original approach.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from eco_codes import ECO_DICT

NICKNAME = "legend2014"

RANKED_EVENTS = [
    "Rated bullet game",
    "Rated blitz game",
    "Rated classical game",
]

ELO_BINS = np.arange(1000, 3200, 200)
ELO_LABELS = [f"{ELO_BINS[i]}-{ELO_BINS[i + 1] - 1}" for i in range(len(ELO_BINS) - 1)]


def parse_pgn(file_path: str) -> pd.DataFrame:
    """Parse a Lichess multi-game PGN export into one row per game."""
    games = []
    game_data: dict = {}
    moves: list[str] = []

    with open(file_path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()

            if line.startswith("["):
                key, value = line[1:-1].split(" ", 1)
                game_data[key] = value.strip('"')
            elif line == "":
                if game_data:
                    game_data["Moves"] = " ".join(moves)
                    game_data.setdefault("WhiteTitle", None)
                    game_data.setdefault("BlackTitle", None)
                    games.append(game_data)
                    game_data = {}
                    moves = []
            else:
                moves.append(line)

        if game_data:
            game_data["Moves"] = " ".join(moves)
            game_data.setdefault("WhiteTitle", None)
            game_data.setdefault("BlackTitle", None)
            games.append(game_data)

    df = pd.DataFrame(games)
    df.reset_index(drop=True, inplace=True)
    return df


def determine_result(row: pd.Series) -> str | None:
    if row["Result"] == "1/2-1/2":
        return "draw"
    if row["White"] == NICKNAME and row["Result"] == "1-0":
        return "win"
    if row["White"] == NICKNAME and row["Result"] == "0-1":
        return "loss"
    if row["Black"] == NICKNAME and row["Result"] == "0-1":
        return "win"
    if row["Black"] == NICKNAME and row["Result"] == "1-0":
        return "loss"
    return None


def clean_games(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Reproduces the original notebook's DATA PREPROCESSING section."""
    # Moves is dropped too: no cell in the original or reconstructed analysis
    # does move-by-move parsing, and it dominates the file size (~15MB of the
    # ~20MB raw export) for no analytical benefit.
    df = raw_df.drop(columns=["FEN", "SetUp", "Site", "Date", "Moves"], errors="ignore").copy()
    df["ResultStatus"] = df.apply(determine_result, axis=1)

    if "BlackRatingDiff" in df.columns and "WhiteTitle" in df.columns:
        columns = list(df.columns)
        columns.insert(
            columns.index("BlackRatingDiff") + 1,
            columns.pop(columns.index("WhiteTitle")),
        )
        df = df[columns]

    return df


def enrich_games(df: pd.DataFrame) -> pd.DataFrame:
    """Adds derived columns used across the analysis.

    [RECONSTRUCTED] Hour, Opening, OpponentElo(Range) and IsRanked were
    used by later cells in the original notebook but their creation was
    lost; this reproduces them from the raw PGN fields.
    """
    df = df.copy()

    df["WhiteElo"] = pd.to_numeric(df["WhiteElo"], errors="coerce")
    df["BlackElo"] = pd.to_numeric(df["BlackElo"], errors="coerce")

    df["Date"] = pd.to_datetime(df["UTCDate"], format="%Y.%m.%d", errors="coerce")

    # [RECONSTRUCTED] Hour of day, from UTCTime ("HH:MM:SS").
    df["Hour"] = pd.to_datetime(df["UTCTime"], format="%H:%M:%S", errors="coerce").dt.hour

    # [RECONSTRUCTED] ECO code -> human-readable opening name.
    df["Opening"] = df["ECO"].map(ECO_DICT).fillna(df["ECO"])

    df["IsRanked"] = df["Event"].isin(RANKED_EVENTS)

    df["OpponentElo"] = np.where(df["White"] == NICKNAME, df["BlackElo"], df["WhiteElo"])
    df["OpponentElo"] = pd.to_numeric(df["OpponentElo"], errors="coerce")
    df["OpponentEloRange"] = pd.cut(df["OpponentElo"], bins=ELO_BINS, labels=ELO_LABELS)

    df["PlayerColor"] = np.where(df["White"] == NICKNAME, "White", "Black")

    return df


def load_clean_dataset(pgn_path: str) -> pd.DataFrame:
    raw_df = parse_pgn(pgn_path)
    cleaned = clean_games(raw_df)
    enriched = enrich_games(cleaned)
    return enriched


def build_opening_stats(df: pd.DataFrame, event: str = "Rated bullet game", min_games: int = 20) -> pd.DataFrame:
    """[RECONSTRUCTED] Combines White-side and Black-side opening
    performance (original cells 27/29) into the single `opening_stats`
    table consumed by the "Best Opening For Me" chart (original cell 31).
    """
    subset = df[df["Event"] == event]

    def side_stats(side_col: str) -> pd.DataFrame:
        side_df = subset[subset[side_col] == NICKNAME]
        return side_df.groupby("Opening").agg(
            game_count=("ResultStatus", "size"),
            win_count=("ResultStatus", lambda x: (x == "win").sum()),
        )

    white_stats = side_stats("White")
    black_stats = side_stats("Black")

    combined = white_stats.add(black_stats, fill_value=0)
    combined["win_rate"] = combined["win_count"] / combined["game_count"]
    combined = combined[combined["game_count"] >= min_games]

    min_count, max_count = combined["game_count"].min(), combined["game_count"].max()
    span = max(max_count - min_count, 1)
    combined["normalized_size"] = 0.3 + 0.7 * (combined["game_count"] - min_count) / span

    return combined.reset_index()


ML_FEATURES = ["EloDiff", "IsWhite", "IsTimeForfeit", "Hour"]


def build_ml_dataset(df: pd.DataFrame, event: str = "Rated bullet game") -> pd.DataFrame:
    """[RECONSTRUCTED] Feature table for the "which factor drives my
    win rate" logistic regression. The original feature engineering cell
    was lost; PlayerElo/OpponentElo, color, termination type and hour are
    the same factors examined individually in the earlier EDA/hypothesis
    cells, so they are reused here as the candidate predictors.
    """
    subset = df[(df["Event"] == event) & df["ResultStatus"].notna()].copy()

    subset["PlayerElo"] = np.where(subset["White"] == NICKNAME, subset["WhiteElo"], subset["BlackElo"])
    subset["EloDiff"] = subset["PlayerElo"] - subset["OpponentElo"]
    subset["IsWhite"] = (subset["PlayerColor"] == "White").astype(int)
    subset["IsTimeForfeit"] = (subset["Termination"] == "Time forfeit").astype(int)
    subset["ResultClass"] = subset["ResultStatus"].map({"win": 1, "draw": 0, "loss": -1})

    subset = subset.dropna(subset=ML_FEATURES + ["ResultClass"])
    return subset[ML_FEATURES + ["ResultClass"]].reset_index(drop=True)
