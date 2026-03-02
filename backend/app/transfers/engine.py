"""Transfer engine facade.

Provides a unified interface over all transfer-related sub-modules:

- **TransferPlanner** -- multi-GW rolling-horizon transfer planning
- **ChipStrategy**    -- chip timing optimisation
- **SensitivityAnalyzer** -- transfer robustness under prediction noise
- **EffectiveOwnership**  -- EO calculation and differential detection

Legacy dataclasses (TransferMove, GameweekTransferPlan) are preserved
for backward-compatibility with existing API schemas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.transfers.chip_strategy import ChipStrategy
from app.transfers.effective_ownership import EffectiveOwnership
from app.transfers.models import (
    ChipRecommendation,
    ChipType,
    PlayerEO,
    SensitivityResult,
    TransferAction,
    TransferPlan,
)
from app.transfers.sensitivity import SensitivityAnalyzer
from app.transfers.transfer_planner import TransferPlanner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy dataclasses (kept for API-layer compatibility)
# ---------------------------------------------------------------------------

@dataclass
class TransferMove:
    """A single transfer recommendation (legacy format)."""

    player_in_id: int
    player_out_id: int
    expected_point_gain: float
    cost_delta: int  # in 0.1m units


@dataclass
class GameweekTransferPlan:
    """Transfer plan for a single gameweek (legacy format)."""

    gameweek: int
    transfers: list[TransferMove] = field(default_factory=list)
    hits: int = 0
    expected_points: float = 0.0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TransferEngine:
    """Facade that orchestrates all transfer-related operations.

    Composes the planner, chip strategy, sensitivity analyser, and
    effective-ownership calculator into a single coherent API.
    """

    HIT_PENALTY = 4

    def __init__(self) -> None:
        self._planner = TransferPlanner()
        self._chip_strategy = ChipStrategy()
        self._sensitivity = SensitivityAnalyzer()
        self._eo = EffectiveOwnership()

    # ------------------------------------------------------------------
    # Transfer Planning
    # ------------------------------------------------------------------

    def plan_transfers(
        self,
        current_squad: list[int],
        predictions_by_gw: dict[int, dict[int, float]],
        free_transfers: int = 1,
        budget_remaining: float = 0.0,
        horizon: int = 5,
        player_prices: dict[int, float] | None = None,
        purchase_prices: dict[int, float] | None = None,
        max_hits_per_gw: int = 2,
    ) -> TransferPlan:
        """Plan transfers across multiple gameweeks.

        Delegates to :class:`TransferPlanner` for the rolling-horizon
        greedy algorithm.

        Returns
        -------
        TransferPlan
            Contains ordered TransferActions, total hits, and net gain.
        """
        logger.info(
            "Planning transfers: squad=%d, FT=%d, budget=%.1f, horizon=%d GWs",
            len(current_squad), free_transfers, budget_remaining, horizon,
        )
        return self._planner.plan(
            current_squad=current_squad,
            predictions_by_gw=predictions_by_gw,
            free_transfers=free_transfers,
            budget_remaining=budget_remaining,
            horizon=horizon,
            player_prices=player_prices,
            purchase_prices=purchase_prices,
            max_hits_per_gw=max_hits_per_gw,
        )

    def recommend_transfers(
        self,
        current_squad: list[int],
        bank: int,
        free_transfers: int,
        horizon: int = 1,
        max_hits: int | None = None,
        predicted_points: dict[int, float] | None = None,
    ) -> list[TransferMove]:
        """Recommend optimal transfers for the current gameweek.

        This is a convenience wrapper over ``plan_transfers`` that
        returns the legacy ``TransferMove`` format.

        Args:
            current_squad: List of 15 player IDs
            bank: Available budget in 0.1m units
            free_transfers: Free transfers available (1 or 2)
            horizon: Number of future GWs to consider
            max_hits: Max hit-transfers (None = unlimited)
            predicted_points: {player_id: predicted_points}
        """
        logger.info(
            "Recommending transfers: squad=%d, bank=%.1fm, FT=%d, horizon=%dGW",
            len(current_squad), bank / 10, free_transfers, horizon,
        )
        if not predicted_points:
            return []

        # Build a single-GW predictions_by_gw from flat predictions
        # Use GW 1 as placeholder if no specific GW context
        predictions_by_gw = {1: predicted_points}
        plan = self._planner.plan(
            current_squad=current_squad,
            predictions_by_gw=predictions_by_gw,
            free_transfers=free_transfers,
            budget_remaining=bank / 10.0,
            horizon=1,
            max_hits_per_gw=max_hits if max_hits is not None else 2,
        )

        return [
            TransferMove(
                player_in_id=a.player_in_id,
                player_out_id=a.player_out_id,
                expected_point_gain=a.predicted_point_gain,
                cost_delta=int(a.cost_delta * 10),
            )
            for a in plan.actions
        ]

    def create_multi_gw_plan(
        self,
        current_squad: list[int],
        bank: int,
        free_transfers: int,
        horizon: int = 5,
        max_hits_per_gw: int = 1,
        predictions_by_gw: dict[int, dict[int, float]] | None = None,
    ) -> list[GameweekTransferPlan]:
        """Create a multi-GW plan in legacy format.

        Returns a list of GameweekTransferPlan (one per GW that has actions).
        """
        logger.info("Creating %d-GW transfer plan", horizon)
        if not predictions_by_gw:
            return []

        plan = self._planner.plan(
            current_squad=current_squad,
            predictions_by_gw=predictions_by_gw,
            free_transfers=free_transfers,
            budget_remaining=bank / 10.0,
            horizon=horizon,
            max_hits_per_gw=max_hits_per_gw,
        )

        # Group actions by GW
        gw_actions: dict[int, list[TransferAction]] = {}
        for action in plan.actions:
            gw_actions.setdefault(action.gameweek, []).append(action)

        result: list[GameweekTransferPlan] = []
        ft = free_transfers
        for gw in sorted(gw_actions.keys()):
            actions = gw_actions[gw]
            hits = max(0, len(actions) - ft)
            moves = [
                TransferMove(
                    player_in_id=a.player_in_id,
                    player_out_id=a.player_out_id,
                    expected_point_gain=a.predicted_point_gain,
                    cost_delta=int(a.cost_delta * 10),
                )
                for a in actions
            ]
            total_pts = sum(a.predicted_point_gain for a in actions) - hits * self.HIT_PENALTY
            result.append(
                GameweekTransferPlan(
                    gameweek=gw,
                    transfers=moves,
                    hits=hits,
                    expected_points=round(total_pts, 2),
                )
            )
            # Update FT for next GW
            ft = min(max(0, ft - len(actions)) + 1, 2)

        return result

    def evaluate_transfers(
        self,
        transfers_in: list[int],
        transfers_out: list[int],
        current_squad: list[int],
        bank: int,
        predicted_points: dict[int, float] | None = None,
        player_prices: dict[int, float] | None = None,
    ) -> dict:
        """Evaluate a proposed set of transfers.

        Returns a dict with validity, cost, budget impact, expected gain,
        and a human-readable verdict.
        """
        if len(transfers_in) != len(transfers_out):
            return {
                "is_valid": False,
                "cost": 0,
                "budget_remaining": bank / 10.0,
                "expected_gain": 0.0,
                "verdict": "Number of transfers in must equal transfers out",
            }

        preds = predicted_points or {}
        prices = player_prices or {}

        # Check all out-players are in squad
        for pid in transfers_out:
            if pid not in current_squad:
                return {
                    "is_valid": False,
                    "cost": 0,
                    "budget_remaining": bank / 10.0,
                    "expected_gain": 0.0,
                    "verdict": f"Player {pid} is not in your squad",
                }

        # Budget calculation
        budget = bank / 10.0
        for out_id, in_id in zip(transfers_out, transfers_in):
            sell = prices.get(out_id, 0.0)
            buy = prices.get(in_id, 0.0)
            budget += sell - buy

        if budget < -0.01:
            return {
                "is_valid": False,
                "cost": 0,
                "budget_remaining": round(budget, 1),
                "expected_gain": 0.0,
                "verdict": f"Insufficient budget: {round(budget, 1)}m remaining",
            }

        # Expected point gain
        gain = 0.0
        for out_id, in_id in zip(transfers_out, transfers_in):
            gain += preds.get(in_id, 0.0) - preds.get(out_id, 0.0)

        # Determine hits
        n_transfers = len(transfers_in)
        cost = max(0, n_transfers - 1) * self.HIT_PENALTY  # assume 1 FT

        net = gain - cost
        verdict = (
            f"{'Good' if net > 0 else 'Marginal' if net > -2 else 'Poor'} transfer: "
            f"+{round(gain, 1)}pts gain, -{cost}pts hits = "
            f"{'+'if net >= 0 else ''}{round(net, 1)}pts net"
        )

        return {
            "is_valid": True,
            "cost": cost,
            "budget_remaining": round(budget, 1),
            "expected_gain": round(gain, 2),
            "verdict": verdict,
        }

    # ------------------------------------------------------------------
    # Chip Strategy
    # ------------------------------------------------------------------

    def recommend_chips(
        self,
        squad: list[int],
        predictions_by_gw: dict[int, dict[int, float]],
        chips_available: list[str],
        bench_order: list[int] | None = None,
    ) -> list[ChipRecommendation]:
        """Recommend optimal chip timing.

        Delegates to :class:`ChipStrategy`.
        """
        logger.info("Recommending chips: available=%s", chips_available)
        return self._chip_strategy.recommend(
            squad=squad,
            predictions_by_gw=predictions_by_gw,
            chips_available=chips_available,
            bench_order=bench_order,
        )

    def simulate_chip(
        self,
        chip_type: str,
        gameweek: int,
        squad: list[int],
        predictions_by_gw: dict[int, dict[int, float]],
        bench_order: list[int] | None = None,
    ) -> dict:
        """Simulate using a chip in a specific GW."""
        ct = ChipType(chip_type)
        return self._chip_strategy.simulate_chip(
            chip_type=ct,
            gameweek=gameweek,
            squad=squad,
            predictions_by_gw=predictions_by_gw,
            bench_order=bench_order,
        )

    # ------------------------------------------------------------------
    # Sensitivity Analysis
    # ------------------------------------------------------------------

    def analyze_sensitivity(
        self,
        current_squad: list[int],
        proposed_transfers: list[tuple[int, int]],
        predictions: dict[int, float],
    ) -> SensitivityResult:
        """Analyze transfer robustness under prediction uncertainty.

        Delegates to :class:`SensitivityAnalyzer`.
        """
        logger.info(
            "Sensitivity analysis: %d transfers", len(proposed_transfers)
        )
        return self._sensitivity.analyze(
            current_squad=current_squad,
            proposed_transfers=proposed_transfers,
            predictions=predictions,
        )

    # ------------------------------------------------------------------
    # Effective Ownership
    # ------------------------------------------------------------------

    def get_effective_ownership(
        self,
        players: list[dict],
        captaincy_rates: dict[int, float] | None = None,
        predicted_points: dict[int, float] | None = None,
    ) -> list[PlayerEO]:
        """Calculate effective ownership for all players.

        Delegates to :class:`EffectiveOwnership`.
        """
        return self._eo.calculate(
            players=players,
            captaincy_rates=captaincy_rates,
            predicted_points=predicted_points,
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_engine_instance: TransferEngine | None = None


def get_transfer_engine() -> TransferEngine:
    """Return a singleton TransferEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = TransferEngine()
    return _engine_instance
