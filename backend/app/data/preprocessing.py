"""Data preprocessing and feature engineering pipeline.

Provides both:
1. High-level helpers that operate on ``Player`` / ``PlayerHistory`` Pydantic
   models (used by the API layer for derived features).
2. A ``DataPipeline`` class that builds pandas DataFrames and numpy feature
   matrices suitable for ML model training and inference.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.data.models import (
    POSITION_DEFAULTS,
    Player,
    PlayerHistory,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key feature columns used by ML models
# ---------------------------------------------------------------------------
ML_FEATURES: list[str] = [
    "ict_index",
    "expected_goal_involvements",
    "expected_goals",
    "expected_assists",
    "form",
    "minutes",
    "bps",
    "selected_by_percent",
    "points_per_million",
    "xgi_per_90",
]


# ===================================================================
# 1. Model-level helpers (operate on Player / PlayerHistory objects)
# ===================================================================

def calculate_derived_features(
    player: Player,
    history: list[PlayerHistory] | None = None,
) -> Player:
    """Compute and attach derived features to a ``Player`` instance.

    Derived features:
    - ``points_per_million``: total_points / (now_cost / 10)
    - ``xgi_per_90``: expected_goal_involvements per 90 minutes
    - ``form`` (override): average total_points over the last 5 GW history
      entries (if history is provided)

    Returns the *same* Player instance (mutated in-place) for convenience.
    """
    # Points per million
    cost_m = player.now_cost / 10.0
    player.points_per_million = (
        round(player.total_points / cost_m, 2) if cost_m > 0 else 0.0
    )

    # xGI per 90
    if player.minutes > 0:
        player.xgi_per_90 = round(
            player.expected_goal_involvements / player.minutes * 90, 3
        )
    else:
        player.xgi_per_90 = 0.0

    # Recalculate form from last 5 gameweeks of history
    if history:
        last_five = sorted(history, key=lambda h: h.round, reverse=True)[:5]
        if last_five:
            player.form = round(
                sum(h.total_points for h in last_five) / len(last_five), 1
            )

    return player


def calculate_fixture_difficulty_weighted_points(
    history: list[PlayerHistory],
    fixtures: list[dict] | None = None,
    fixture_difficulty_map: dict[int, int] | None = None,
) -> float:
    """Compute fixture-difficulty-weighted average points from history.

    Each GW's points are multiplied by (difficulty / 3) so that points
    scored against harder opponents count more. Default difficulty is 3
    if not provided.
    """
    if not history:
        return 0.0

    if fixture_difficulty_map is None:
        fixture_difficulty_map = {}

    total_weighted = 0.0
    total_weight = 0.0
    for h in history:
        diff = fixture_difficulty_map.get(h.fixture, 3)
        weight = diff / 3.0
        total_weighted += h.total_points * weight
        total_weight += weight

    return round(total_weighted / total_weight, 2) if total_weight > 0 else 0.0


def handle_missing_data(players: list[Player]) -> list[Player]:
    """Fill missing / zero stats with position-appropriate defaults.

    Only fills a stat when the player has 0 minutes (i.e. no data at all)
    so that genuine zero-stat players are not affected.
    """
    for player in players:
        if player.minutes > 0:
            continue
        defaults = POSITION_DEFAULTS.get(player.position, {})
        for field_name, default_val in defaults.items():
            if hasattr(player, field_name):
                current = getattr(player, field_name)
                if current == 0 or current == 0.0:
                    setattr(player, field_name, default_val)
    return players


def normalize_features(
    players: list[Player],
    features: list[str] | None = None,
) -> list[dict]:
    """Apply min-max normalisation for the specified features.

    Returns a list of dicts (one per player) with the same keys, each
    normalised to the [0, 1] range.
    """
    features = features or ML_FEATURES

    # Build raw value lists
    raw: dict[str, list[float]] = {f: [] for f in features}
    for p in players:
        for f in features:
            raw[f].append(float(getattr(p, f, 0)))

    # Compute min / max
    mins: dict[str, float] = {}
    maxs: dict[str, float] = {}
    for f in features:
        vals = raw[f]
        mins[f] = min(vals) if vals else 0.0
        maxs[f] = max(vals) if vals else 0.0

    # Normalise
    results: list[dict] = []
    for i, p in enumerate(players):
        row: dict[str, float] = {"id": p.id}
        for f in features:
            col_min = mins[f]
            col_max = maxs[f]
            val = raw[f][i]
            if col_max > col_min:
                row[f] = (val - col_min) / (col_max - col_min)
            else:
                row[f] = 0.0
        results.append(row)
    return results


def get_feature_matrix(
    players: list[Player],
    features: list[str] | None = None,
) -> np.ndarray:
    """Return a (num_players, num_features) numpy array for ML models.

    Each row corresponds to one player; columns follow the order of
    ``features`` (defaults to ``ML_FEATURES``).
    """
    features = features or ML_FEATURES

    matrix = np.zeros((len(players), len(features)), dtype=np.float64)
    for i, p in enumerate(players):
        for j, f in enumerate(features):
            matrix[i, j] = float(getattr(p, f, 0))

    return matrix


# ===================================================================
# 2. DataFrame / pipeline-oriented class (for training pipelines)
# ===================================================================

class DataPipeline:
    """Feature engineering and data transformation pipeline.

    Transforms raw FPL per-gameweek player data into a feature matrix
    suitable for prediction models.
    """

    SHORT_WINDOW = 3
    MEDIUM_WINDOW = 5
    LONG_WINDOW = 10

    def build_player_features(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Build feature matrix from raw per-GW player data.

        Input: DataFrame with columns from FPL API (minutes, goals_scored,
               assists, clean_sheets, bonus, bps, ict_index, etc.)
        Output: Feature matrix with engineered features.
        """
        df = raw_data.copy()

        numeric_cols = [
            "minutes", "goals_scored", "assists", "clean_sheets",
            "bonus", "bps", "total_points", "ict_index",
            "influence", "creativity", "threat",
            "expected_goals", "expected_assists",
            "expected_goal_involvements", "expected_goals_conceded",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Rolling averages for form
        for base_col, prefix in [
            ("total_points", "pts"),
            ("minutes", "mins"),
            ("ict_index", "ict"),
            ("expected_goal_involvements", "xgi"),
        ]:
            if base_col in df.columns:
                df = self._add_rolling_features(df, base_col, prefix)

        # Form trend: short vs long rolling average
        if "pts_rolling_3" in df.columns and "pts_rolling_10" in df.columns:
            df["form_trend"] = df["pts_rolling_3"] - df["pts_rolling_10"]

        # Minutes played ratio (out of 90)
        if "minutes" in df.columns:
            df["minutes_ratio"] = df["minutes"] / 90.0

        # Points per million
        if "total_points" in df.columns and "value" in df.columns:
            cost_m = pd.to_numeric(df["value"], errors="coerce").fillna(0) / 10.0
            df["points_per_million"] = np.where(
                cost_m > 0,
                df["total_points"] / cost_m,
                0.0,
            )

        # xGI per 90
        if "expected_goal_involvements" in df.columns and "minutes" in df.columns:
            mins = df["minutes"].replace(0, np.nan)
            df["xgi_per_90"] = (
                df["expected_goal_involvements"] / mins * 90
            ).fillna(0.0)

        logger.info(
            "Built feature matrix with %d rows, %d columns",
            len(df), len(df.columns),
        )
        return df

    def _add_rolling_features(
        self, df: pd.DataFrame, col: str, prefix: str
    ) -> pd.DataFrame:
        """Add rolling mean features for a given column."""
        if "element" in df.columns:
            group = df.groupby("element")[col]
        else:
            group = df[col]

        for window in [self.SHORT_WINDOW, self.MEDIUM_WINDOW, self.LONG_WINDOW]:
            col_name = f"{prefix}_rolling_{window}"
            if "element" in df.columns:
                df[col_name] = group.transform(
                    lambda x: x.rolling(window, min_periods=1).mean()
                )
            else:
                df[col_name] = df[col].rolling(window, min_periods=1).mean()

        return df

    def handle_missing_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in the feature matrix."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)
        return df

    def normalize_features(
        self,
        df: pd.DataFrame,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Normalize specified feature columns to [0, 1] range."""
        cols_to_normalize = (
            columns
            or df.select_dtypes(include=[np.number]).columns.tolist()
        )
        for col in cols_to_normalize:
            if col in df.columns:
                col_min = df[col].min()
                col_max = df[col].max()
                if col_max > col_min:
                    df[col] = (df[col] - col_min) / (col_max - col_min)
                else:
                    df[col] = 0.0
        return df

    def create_target(self, df: pd.DataFrame, horizon: int = 1) -> pd.Series:
        """Create prediction target: points scored ``horizon`` GWs ahead."""
        if "element" in df.columns:
            return df.groupby("element")["total_points"].shift(-horizon)
        return df["total_points"].shift(-horizon)
