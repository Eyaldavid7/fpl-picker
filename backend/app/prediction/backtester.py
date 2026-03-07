"""Backtesting framework for FPL scoring models.

Validates predictions against historical gameweek data by:
1. For each GW in range, predicting scores using the fixture scorer
2. Comparing predictions to actual points from player history
3. Computing MAE, R², and captain accuracy metrics
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

from app.data.fpl_client import get_fpl_client
from app.data.models import Player, PlayerHistory
from app.prediction.fixture_scorer import FixtureAwareScorer, build_fixture_lookup

logger = logging.getLogger(__name__)


class Backtester:
    """Backtest scoring models against historical FPL data."""

    def __init__(self):
        self.scorer = FixtureAwareScorer()

    async def run_backtest(self, model: str, gw_start: int, gw_end: int) -> dict:
        """Run backtest over a gameweek range.

        For each gameweek:
        1. Get fixture data for that GW
        2. Score all players using the fixture scorer
        3. Compare predicted vs actual points from history
        4. Compute per-GW and aggregate metrics

        Args:
            model: Model name (currently only "fixture_scorer" supported)
            gw_start: First gameweek (inclusive)
            gw_end: Last gameweek (inclusive)

        Returns:
            Dict matching BacktestResponse schema
        """
        if model != "fixture_scorer":
            return {
                "model": model,
                "gw_start": gw_start,
                "gw_end": gw_end,
                "mae": 0.0,
                "cumulative_points": 0.0,
                "r_squared": 0.0,
                "top_captain_accuracy": 0.0,
                "results": [],
            }

        client = get_fpl_client()

        # Fetch all players and teams once
        all_players = await client.get_players()
        all_teams = await client.get_teams()
        teams_map = await client.get_teams_map()
        teams_by_id = {t.id: t for t in all_teams}
        player_map = {p.id: p for p in all_players}

        # Fetch history for all players (we'll filter by GW)
        player_histories: dict[int, list[PlayerHistory]] = {}
        for player in all_players:
            if player.minutes > 0:  # Only players with playing time
                try:
                    history = await client.get_player_history(player.id)
                    player_histories[player.id] = history
                except Exception:
                    continue

        league_avgs = self.scorer._precompute_league_avgs(teams_by_id)

        gw_results = []
        all_predicted = []
        all_actual = []
        captain_correct = 0
        captain_total = 0
        cumulative_predicted = 0.0
        cumulative_actual = 0.0

        for gw in range(gw_start, gw_end + 1):
            try:
                # Get fixtures for this GW
                fixtures = await client.get_typed_fixtures(gw)
                fixture_lookup = build_fixture_lookup(fixtures, teams_map)
            except Exception:
                logger.warning("Could not fetch fixtures for GW %d", gw)
                continue

            # Build actual points lookup for this GW from history
            actual_points: dict[int, int] = {}
            for pid, history in player_histories.items():
                for h in history:
                    if h.round == gw:
                        actual_points[pid] = h.total_points
                        break

            if not actual_points:
                continue

            # Score players for this GW
            gw_predicted_total = 0.0
            gw_actual_total = 0.0
            gw_errors = []
            gw_predictions: list[tuple[int, float, int]] = []  # (pid, predicted, actual)

            for pid, actual_pts in actual_points.items():
                player = player_map.get(pid)
                if player is None:
                    continue

                try:
                    scored = self.scorer.score_player(
                        player, fixture_lookup, teams_by_id,
                        teams_name_map=teams_map, league_avgs=league_avgs,
                    )
                    predicted = scored.final_score
                except Exception:
                    continue

                error = abs(predicted - actual_pts)
                gw_errors.append(error)
                gw_predicted_total += predicted
                gw_actual_total += actual_pts
                all_predicted.append(predicted)
                all_actual.append(actual_pts)
                gw_predictions.append((pid, predicted, actual_pts))

            # Per-GW MAE
            gw_mae = sum(gw_errors) / len(gw_errors) if gw_errors else 0.0
            cumulative_predicted += gw_predicted_total
            cumulative_actual += gw_actual_total

            # Captain accuracy: was our top predicted player in actual top 3?
            if gw_predictions:
                gw_predictions.sort(key=lambda x: x[1], reverse=True)
                top_predicted_pid = gw_predictions[0][0]

                actual_sorted = sorted(gw_predictions, key=lambda x: x[2], reverse=True)
                top_3_actual = {x[0] for x in actual_sorted[:3]}

                captain_total += 1
                if top_predicted_pid in top_3_actual:
                    captain_correct += 1

            gw_results.append({
                "gameweek": gw,
                "mae": round(gw_mae, 2),
                "predicted_total": round(gw_predicted_total, 2),
                "actual_total": round(gw_actual_total, 2),
            })

        # Aggregate metrics
        overall_mae = sum(abs(p - a) for p, a in zip(all_predicted, all_actual)) / len(all_predicted) if all_predicted else 0.0

        # R² calculation
        r_squared = 0.0
        if len(all_actual) > 1:
            mean_actual = sum(all_actual) / len(all_actual)
            ss_res = sum((a - p) ** 2 for p, a in zip(all_predicted, all_actual))
            ss_tot = sum((a - mean_actual) ** 2 for a in all_actual)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        captain_accuracy = captain_correct / captain_total if captain_total > 0 else 0.0

        return {
            "model": model,
            "gw_start": gw_start,
            "gw_end": gw_end,
            "mae": round(overall_mae, 2),
            "cumulative_points": round(cumulative_predicted, 2),
            "r_squared": round(r_squared, 4),
            "top_captain_accuracy": round(captain_accuracy, 4),
            "results": gw_results,
        }
