"""Chip timing optimiser for FPL.

Evaluates the expected value of deploying each available chip in each
remaining gameweek and recommends the optimal timing.

Chip descriptions and scoring heuristics
-----------------------------------------

**Wildcard (WC)** -- unlimited transfers for one GW.
    Best when the current squad is poorly suited for upcoming fixtures.
    EV = sum of point gains from best possible squad minus current squad
    over the remaining horizon.

**Free Hit (FH)** -- temporary unlimited transfers for one GW only
    (squad reverts after the GW).
    Best for blank or double GWs when fixtures are unusual.
    EV = best-possible-XI points for that GW minus current XI points.

**Triple Captain (TC)** -- captain scores 3x instead of 2x.
    Best when a premium player has an ideal fixture (home, weak opponent).
    EV = extra captain points (i.e. 1x the captain's predicted score).

**Bench Boost (BB)** -- bench players also score that GW.
    Best when all 15 players have good fixtures.
    EV = sum of bench players' predicted points.
"""

from __future__ import annotations

import logging

from app.transfers.models import ChipRecommendation, ChipType

logger = logging.getLogger(__name__)


class ChipStrategy:
    """Recommend optimal chip deployment across remaining gameweeks."""

    def __init__(self) -> None:
        pass

    def recommend(
        self,
        squad: list[int],
        predictions_by_gw: dict[int, dict[int, float]],
        chips_available: list[str],
        bench_order: list[int] | None = None,
    ) -> list[ChipRecommendation]:
        """Produce chip recommendations for each available chip.

        Parameters
        ----------
        squad : list[int]
            Current 15-player squad (player IDs).
        predictions_by_gw : dict[int, dict[int, float]]
            ``{gameweek: {player_id: predicted_points}}`` for all known
            players across multiple future GWs.
        chips_available : list[str]
            Chip names still available (e.g. ``["wildcard", "free_hit"]``).
        bench_order : list[int] or None
            Ordered bench player IDs (index 0 = GK bench).  If not provided,
            the last 4 IDs in ``squad`` are assumed to be bench.

        Returns
        -------
        list[ChipRecommendation]
            One recommendation per available chip, sorted by expected value.
        """
        if not predictions_by_gw or not chips_available:
            return []

        gameweeks = sorted(predictions_by_gw.keys())
        recommendations: list[ChipRecommendation] = []

        for chip_name in chips_available:
            try:
                chip_type = ChipType(chip_name)
            except ValueError:
                logger.warning("Unknown chip type: %s", chip_name)
                continue

            best_gw = gameweeks[0]
            best_ev = float("-inf")
            best_reason = ""

            for gw in gameweeks:
                gw_preds = predictions_by_gw[gw]
                ev, reason = self._score_chip_for_gw(
                    chip_type=chip_type,
                    gw=gw,
                    squad=squad,
                    gw_preds=gw_preds,
                    all_preds=predictions_by_gw,
                    bench_order=bench_order,
                )
                if ev > best_ev:
                    best_ev = ev
                    best_gw = gw
                    best_reason = reason

            recommendations.append(
                ChipRecommendation(
                    chip_type=chip_type,
                    recommended_gameweek=best_gw,
                    expected_value=round(max(best_ev, 0.0), 2),
                    reasoning=best_reason,
                )
            )

        # Sort by expected value descending
        recommendations.sort(key=lambda r: r.expected_value, reverse=True)
        return recommendations

    def simulate_chip(
        self,
        chip_type: ChipType,
        gameweek: int,
        squad: list[int],
        predictions_by_gw: dict[int, dict[int, float]],
        bench_order: list[int] | None = None,
    ) -> dict:
        """Simulate using a specific chip in a specific GW.

        Returns a dict with projected points with/without chip and delta.
        """
        gw_preds = predictions_by_gw.get(gameweek, {})
        if not gw_preds:
            return {
                "chip": chip_type.value,
                "gameweek": gameweek,
                "projected_points_with_chip": 0.0,
                "projected_points_without_chip": 0.0,
                "point_delta": 0.0,
            }

        without_chip = self._squad_points(squad, gw_preds, bench_order, include_bench=False)
        ev, _ = self._score_chip_for_gw(
            chip_type=chip_type,
            gw=gameweek,
            squad=squad,
            gw_preds=gw_preds,
            all_preds=predictions_by_gw,
            bench_order=bench_order,
        )
        with_chip = without_chip + ev

        return {
            "chip": chip_type.value,
            "gameweek": gameweek,
            "projected_points_with_chip": round(with_chip, 2),
            "projected_points_without_chip": round(without_chip, 2),
            "point_delta": round(ev, 2),
        }

    # ------------------------------------------------------------------
    # Scoring logic per chip type
    # ------------------------------------------------------------------

    def _score_chip_for_gw(
        self,
        chip_type: ChipType,
        gw: int,
        squad: list[int],
        gw_preds: dict[int, float],
        all_preds: dict[int, dict[int, float]],
        bench_order: list[int] | None = None,
    ) -> tuple[float, str]:
        """Return (expected_value, reasoning) for using *chip_type* in *gw*."""

        if chip_type == ChipType.WILDCARD:
            return self._score_wildcard(squad, gw, gw_preds, all_preds)
        elif chip_type == ChipType.FREE_HIT:
            return self._score_free_hit(squad, gw, gw_preds)
        elif chip_type == ChipType.TRIPLE_CAPTAIN:
            return self._score_triple_captain(squad, gw_preds)
        elif chip_type == ChipType.BENCH_BOOST:
            return self._score_bench_boost(squad, gw_preds, bench_order)
        else:
            return 0.0, f"Unknown chip type: {chip_type}"

    def _score_wildcard(
        self,
        squad: list[int],
        gw: int,
        gw_preds: dict[int, float],
        all_preds: dict[int, dict[int, float]],
    ) -> tuple[float, str]:
        """WC score: how much better is the best-possible squad over current?

        We approximate by summing horizon-remaining predictions for the
        best 15 players vs. the current 15.
        """
        remaining_gws = [g for g in sorted(all_preds.keys()) if g >= gw]

        # Current squad horizon points
        current_horizon = 0.0
        for g in remaining_gws:
            gp = all_preds.get(g, {})
            for pid in squad:
                current_horizon += gp.get(pid, 0.0)

        # Best possible 15 (simplified: top-15 by horizon total)
        all_players: set[int] = set()
        for gp in all_preds.values():
            all_players.update(gp.keys())

        player_horizon: dict[int, float] = {}
        for pid in all_players:
            total = 0.0
            for g in remaining_gws:
                total += all_preds.get(g, {}).get(pid, 0.0)
            player_horizon[pid] = total

        sorted_players = sorted(
            player_horizon.items(), key=lambda x: x[1], reverse=True
        )
        best_15_pts = sum(pts for _, pts in sorted_players[:15])

        ev = best_15_pts - current_horizon
        squad_deficit = round(ev / max(len(remaining_gws), 1), 1)
        reason = (
            f"WC in GW{gw}: current squad {round(current_horizon, 1)}pts vs "
            f"best-15 {round(best_15_pts, 1)}pts over {len(remaining_gws)} GWs "
            f"(deficit ~{squad_deficit}pts/GW)"
        )
        return ev, reason

    def _score_free_hit(
        self,
        squad: list[int],
        gw: int,
        gw_preds: dict[int, float],
    ) -> tuple[float, str]:
        """FH score: best-possible XI for this GW vs. current XI.

        Approximation: top-11 predicted players vs. top-11 from current squad.
        """
        # Current squad best XI (top 11 by prediction)
        squad_preds = [(pid, gw_preds.get(pid, 0.0)) for pid in squad]
        squad_preds.sort(key=lambda x: x[1], reverse=True)
        current_xi_pts = sum(pts for _, pts in squad_preds[:11])

        # Best possible XI from all players
        all_sorted = sorted(gw_preds.items(), key=lambda x: x[1], reverse=True)
        best_xi_pts = sum(pts for _, pts in all_sorted[:11])

        ev = best_xi_pts - current_xi_pts
        reason = (
            f"FH in GW{gw}: best XI {round(best_xi_pts, 1)}pts vs "
            f"current XI {round(current_xi_pts, 1)}pts"
        )
        return ev, reason

    def _score_triple_captain(
        self,
        squad: list[int],
        gw_preds: dict[int, float],
    ) -> tuple[float, str]:
        """TC score: extra captain points = 1x best player's predicted score.

        Normally captain gets 2x; with TC it's 3x.  The additional
        value is therefore 1x the captain's predicted score.
        """
        squad_preds = [(pid, gw_preds.get(pid, 0.0)) for pid in squad]
        if not squad_preds:
            return 0.0, "No predictions for squad players"

        best_player = max(squad_preds, key=lambda x: x[1])
        ev = best_player[1]  # 1x extra
        reason = (
            f"TC: best captain candidate player {best_player[0]} "
            f"predicted {round(best_player[1], 1)}pts "
            f"(+{round(ev, 1)}pts extra from 3x)"
        )
        return ev, reason

    def _score_bench_boost(
        self,
        squad: list[int],
        gw_preds: dict[int, float],
        bench_order: list[int] | None = None,
    ) -> tuple[float, str]:
        """BB score: sum of bench players' predicted points.

        If bench_order is given, use those 4 players.
        Otherwise, the bottom 4 from the squad by prediction.
        """
        if bench_order and len(bench_order) >= 4:
            bench_ids = bench_order[:4]
        else:
            squad_preds = [(pid, gw_preds.get(pid, 0.0)) for pid in squad]
            squad_preds.sort(key=lambda x: x[1], reverse=True)
            # Bench = bottom 4
            bench_ids = [pid for pid, _ in squad_preds[11:15]]

        bench_pts = sum(gw_preds.get(pid, 0.0) for pid in bench_ids)
        reason = (
            f"BB: bench players {bench_ids} predicted "
            f"{round(bench_pts, 1)}pts total"
        )
        return bench_pts, reason

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _squad_points(
        squad: list[int],
        gw_preds: dict[int, float],
        bench_order: list[int] | None = None,
        include_bench: bool = False,
    ) -> float:
        """Calculate total predicted points for the squad's best XI.

        If *include_bench* is True, add bench points too (Bench Boost).
        """
        squad_preds = [(pid, gw_preds.get(pid, 0.0)) for pid in squad]
        squad_preds.sort(key=lambda x: x[1], reverse=True)

        xi_pts = sum(pts for _, pts in squad_preds[:11])

        # Add captain bonus (best player gets 2x -> add 1x extra)
        if squad_preds:
            xi_pts += squad_preds[0][1]

        if include_bench:
            bench_pts = sum(pts for _, pts in squad_preds[11:15])
            return xi_pts + bench_pts

        return xi_pts
