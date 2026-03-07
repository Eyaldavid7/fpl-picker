"""Multi-window temporal features for player scoring.

Computes rolling averages over 3, 5, and 10 match windows from player history.
"""

from __future__ import annotations

import logging
from app.data.fpl_client import get_fpl_client
from app.data.models import PlayerHistory

logger = logging.getLogger(__name__)

WINDOWS = [3, 5, 10]


class TemporalFeatures:
    """Compute rolling-window averages from player gameweek history."""

    async def compute_windows(self, player_id: int) -> dict | None:
        """Fetch player history and compute rolling averages for each window.

        Returns dict with window_3, window_5, window_10 keys, each containing
        per-90 stats, plus a trend indicator. Returns None on failure.
        """
        try:
            client = get_fpl_client()
            history = await client.get_player_history(player_id)
        except Exception as exc:
            logger.warning("Failed to fetch history for player %d: %s", player_id, exc)
            return None

        if not history:
            return None

        # Sort by round descending (most recent first)
        history.sort(key=lambda h: h.round, reverse=True)

        result = {}
        for window in WINDOWS:
            subset = history[:window]
            if not subset:
                continue
            n = len(subset)
            total_minutes = sum(h.minutes for h in subset)
            appearances = total_minutes / 90 if total_minutes > 0 else n

            result[f"window_{window}"] = {
                "ppg": sum(h.total_points for h in subset) / n,
                "minutes_avg": total_minutes / n,
                "goals_assists": (sum(h.goals_scored for h in subset) + sum(h.assists for h in subset)) / n,
                "xg": sum(h.expected_goals for h in subset) / max(appearances, 1),
                "xa": sum(h.expected_assists for h in subset) / max(appearances, 1),
                "xgi": sum(h.expected_goal_involvements for h in subset) / max(appearances, 1),
                "xgc": sum(h.expected_goals_conceded for h in subset) / max(appearances, 1),
                "clean_sheets": sum(h.clean_sheets for h in subset) / n,
                "threat": sum(h.threat for h in subset) / max(appearances, 1),
                "creativity": sum(h.creativity for h in subset) / max(appearances, 1),
                "influence": sum(h.influence for h in subset) / max(appearances, 1),
                "bonus": sum(h.bonus for h in subset) / n,
            }

        # Determine trend from window_3 vs window_10 PPG
        w3_ppg = result.get("window_3", {}).get("ppg", 0)
        w10_ppg = result.get("window_10", {}).get("ppg", 0)
        if w10_ppg > 0:
            ratio = w3_ppg / w10_ppg
            if ratio > 1.15:
                result["trend"] = "improving"
            elif ratio < 0.85:
                result["trend"] = "declining"
            else:
                result["trend"] = "stable"
        else:
            result["trend"] = "stable"

        return result


def get_temporal_features() -> TemporalFeatures:
    """Return a TemporalFeatures instance."""
    return TemporalFeatures()
