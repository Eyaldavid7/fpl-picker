"""Comprehensive tests for the transfer strategy and chip timing module.

Covers:
- TransferPlanner: multi-GW rolling-horizon planning
- ChipStrategy: chip timing recommendations (WC, FH, TC, BB)
- SensitivityAnalyzer: transfer robustness under perturbation
- EffectiveOwnership: EO calculation and differential detection
- TransferEngine: facade integration
- API endpoints: return 200
"""

from __future__ import annotations

import pytest

from app.transfers.models import (
    ChipRecommendation,
    ChipType,
    PlayerEO,
    SensitivityResult,
    TransferAction,
    TransferClassification,
    TransferPlan,
)
from app.transfers.transfer_planner import TransferPlanner, _selling_price
from app.transfers.chip_strategy import ChipStrategy
from app.transfers.sensitivity import SensitivityAnalyzer
from app.transfers.effective_ownership import EffectiveOwnership
from app.transfers.engine import TransferEngine, get_transfer_engine


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

# 20 players across 5 teams: 3 GK, 6 DEF, 6 MID, 5 FWD
MOCK_PLAYERS: list[dict] = [
    # GK
    {"id": 1, "web_name": "GK_A", "position": "GK", "now_cost": 55, "team": 1, "selected_by_percent": 30.0},
    {"id": 2, "web_name": "GK_B", "position": "GK", "now_cost": 45, "team": 2, "selected_by_percent": 10.0},
    {"id": 3, "web_name": "GK_C", "position": "GK", "now_cost": 40, "team": 3, "selected_by_percent": 5.0},
    # DEF
    {"id": 4, "web_name": "DEF_A", "position": "DEF", "now_cost": 70, "team": 1, "selected_by_percent": 40.0},
    {"id": 5, "web_name": "DEF_B", "position": "DEF", "now_cost": 55, "team": 2, "selected_by_percent": 25.0},
    {"id": 6, "web_name": "DEF_C", "position": "DEF", "now_cost": 50, "team": 3, "selected_by_percent": 15.0},
    {"id": 7, "web_name": "DEF_D", "position": "DEF", "now_cost": 45, "team": 4, "selected_by_percent": 8.0},
    {"id": 8, "web_name": "DEF_E", "position": "DEF", "now_cost": 40, "team": 5, "selected_by_percent": 3.0},
    {"id": 9, "web_name": "DEF_F", "position": "DEF", "now_cost": 40, "team": 1, "selected_by_percent": 2.0},
    # MID
    {"id": 10, "web_name": "MID_A", "position": "MID", "now_cost": 130, "team": 2, "selected_by_percent": 60.0},
    {"id": 11, "web_name": "MID_B", "position": "MID", "now_cost": 110, "team": 3, "selected_by_percent": 45.0},
    {"id": 12, "web_name": "MID_C", "position": "MID", "now_cost": 80, "team": 4, "selected_by_percent": 20.0},
    {"id": 13, "web_name": "MID_D", "position": "MID", "now_cost": 65, "team": 5, "selected_by_percent": 12.0},
    {"id": 14, "web_name": "MID_E", "position": "MID", "now_cost": 55, "team": 1, "selected_by_percent": 6.0},
    {"id": 15, "web_name": "MID_F", "position": "MID", "now_cost": 45, "team": 2, "selected_by_percent": 1.0},
    # FWD
    {"id": 16, "web_name": "FWD_A", "position": "FWD", "now_cost": 140, "team": 3, "selected_by_percent": 55.0},
    {"id": 17, "web_name": "FWD_B", "position": "FWD", "now_cost": 85, "team": 4, "selected_by_percent": 22.0},
    {"id": 18, "web_name": "FWD_C", "position": "FWD", "now_cost": 70, "team": 5, "selected_by_percent": 15.0},
    {"id": 19, "web_name": "FWD_D", "position": "FWD", "now_cost": 60, "team": 1, "selected_by_percent": 4.0},
    {"id": 20, "web_name": "FWD_E", "position": "FWD", "now_cost": 55, "team": 2, "selected_by_percent": 2.0},
]

# A valid 15-player squad
SQUAD_IDS = [1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13, 16, 17, 18, 19]

# Predictions for GW28-32 (5 GW horizon)
PREDICTIONS_BY_GW: dict[int, dict[int, float]] = {
    28: {
        1: 3.5, 2: 3.0, 3: 2.8, 4: 5.0, 5: 4.2, 6: 3.8, 7: 3.5, 8: 3.0,
        9: 2.5, 10: 8.0, 11: 7.0, 12: 5.5, 13: 4.5, 14: 3.5, 15: 2.0,
        16: 9.0, 17: 6.0, 18: 5.0, 19: 3.0, 20: 2.5,
    },
    29: {
        1: 3.2, 2: 3.5, 3: 3.0, 4: 4.5, 5: 4.8, 6: 4.0, 7: 3.8, 8: 3.2,
        9: 2.8, 10: 7.5, 11: 7.5, 12: 6.0, 13: 5.0, 14: 4.0, 15: 2.5,
        16: 8.5, 17: 6.5, 18: 5.5, 19: 3.5, 20: 3.0,
    },
    30: {
        1: 3.8, 2: 2.8, 3: 3.2, 4: 5.2, 5: 3.8, 6: 4.2, 7: 4.0, 8: 3.5,
        9: 3.0, 10: 8.5, 11: 6.5, 12: 5.0, 13: 4.0, 14: 3.8, 15: 2.2,
        16: 9.5, 17: 5.5, 18: 4.5, 19: 4.0, 20: 3.5,
    },
    31: {
        1: 3.0, 2: 3.2, 3: 3.5, 4: 4.8, 5: 4.5, 6: 3.5, 7: 3.2, 8: 2.8,
        9: 2.5, 10: 7.0, 11: 7.2, 12: 5.8, 13: 4.8, 14: 4.2, 15: 2.8,
        16: 8.0, 17: 6.2, 18: 5.2, 19: 3.2, 20: 2.8,
    },
    32: {
        1: 3.5, 2: 3.0, 3: 2.5, 4: 5.5, 5: 4.0, 6: 4.5, 7: 3.5, 8: 3.0,
        9: 2.0, 10: 8.2, 11: 6.8, 12: 5.2, 13: 4.2, 14: 3.5, 15: 2.0,
        16: 9.2, 17: 5.8, 18: 4.8, 19: 3.5, 20: 2.5,
    },
}

# Flat predictions (single GW view)
FLAT_PREDICTIONS: dict[int, float] = PREDICTIONS_BY_GW[28]

# Player prices in real money units (e.g. 5.5 = 5.5m)
PLAYER_PRICES = {p["id"]: p["now_cost"] / 10.0 for p in MOCK_PLAYERS}


# ======================================================================
# TransferPlanner tests
# ======================================================================

class TestTransferPlanner:
    """Tests for the multi-GW rolling-horizon transfer planner."""

    def setup_method(self):
        self.planner = TransferPlanner()

    def test_plan_returns_transfer_plan(self):
        plan = self.planner.plan(
            current_squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            free_transfers=1,
            budget_remaining=1.0,
            horizon=5,
        )
        assert isinstance(plan, TransferPlan)
        assert plan.gameweeks_covered == 5

    def test_plan_with_no_predictions(self):
        plan = self.planner.plan(
            current_squad=SQUAD_IDS,
            predictions_by_gw={},
            free_transfers=1,
        )
        assert plan.gameweeks_covered == 0
        assert plan.actions == []

    def test_plan_respects_free_transfers(self):
        """With 1 FT, no transfer should be a hit unless its gain > 4 pts."""
        plan = self.planner.plan(
            current_squad=SQUAD_IDS,
            predictions_by_gw={28: FLAT_PREDICTIONS},
            free_transfers=1,
            budget_remaining=10.0,
            horizon=1,
            player_prices=PLAYER_PRICES,
            max_hits_per_gw=0,  # No hits allowed
        )
        # All actions should be free (at most 1 transfer with 0 max hits)
        assert len(plan.actions) <= 1
        assert plan.total_hits == 0

    def test_plan_identifies_beneficial_transfer(self):
        """Player 15 (2.0pts) -> player 14 (3.5pts) is a clear upgrade if affordable."""
        # Build squad with player 15 instead of 14
        squad = [1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 15, 16, 17, 18, 19]
        plan = self.planner.plan(
            current_squad=squad,
            predictions_by_gw=PREDICTIONS_BY_GW,
            free_transfers=1,
            budget_remaining=5.0,
            horizon=5,
            player_prices=PLAYER_PRICES,
        )
        # Should recommend at least one transfer
        if plan.actions:
            # The gain should be positive
            assert plan.net_point_gain > 0

    def test_plan_accumulates_free_transfers(self):
        """If no transfer is worthwhile, FT should accumulate to 2."""
        # Give predictions where current squad is already optimal
        optimal_preds = {
            28: {pid: 10.0 for pid in SQUAD_IDS},  # All squad players very good
        }
        # Non-squad players are bad
        for pid in range(1, 21):
            if pid not in SQUAD_IDS:
                optimal_preds[28][pid] = 0.5

        plan = self.planner.plan(
            current_squad=SQUAD_IDS,
            predictions_by_gw=optimal_preds,
            free_transfers=1,
            budget_remaining=5.0,
            horizon=1,
        )
        # Should make no transfers if squad is already the best
        assert len(plan.actions) == 0

    def test_plan_with_budget_constraint(self):
        """Transfers that exceed budget should not be recommended."""
        plan = self.planner.plan(
            current_squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            free_transfers=2,
            budget_remaining=0.0,  # No extra budget
            horizon=3,
            player_prices=PLAYER_PRICES,
        )
        assert isinstance(plan, TransferPlan)

    def test_net_point_gain_accounts_for_hits(self):
        """Net gain should be gross gain minus hit costs."""
        plan = self.planner.plan(
            current_squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            free_transfers=1,
            budget_remaining=10.0,
            horizon=5,
        )
        gross = sum(a.predicted_point_gain for a in plan.actions)
        expected_net = gross - plan.total_hits * 4
        assert abs(plan.net_point_gain - expected_net) < 0.01


class TestSellingPrice:
    """Tests for the FPL selling price calculation."""

    def test_no_profit(self):
        """If price hasn't risen, sell at current price."""
        assert _selling_price(8.0, 8.0) == 8.0

    def test_price_drop(self):
        """If price dropped, sell at current (lower) price."""
        assert _selling_price(8.0, 7.5) == 7.5

    def test_small_rise(self):
        """0.1m rise: profit = 0.1, kept = floor(0.5) / 10 = 0.0."""
        result = _selling_price(8.0, 8.1)
        assert result == 8.0  # floor(0.1 * 5) / 10 = 0.0

    def test_two_rises(self):
        """0.2m rise: profit = 0.2, kept = floor(1.0) / 10 = 0.1."""
        result = _selling_price(8.0, 8.2)
        assert result == 8.1

    def test_large_rise(self):
        """1.0m rise: profit = 1.0, kept = floor(5.0) / 10 = 0.5."""
        result = _selling_price(8.0, 9.0)
        assert result == 8.5


# ======================================================================
# ChipStrategy tests
# ======================================================================

class TestChipStrategy:
    """Tests for chip timing recommendations."""

    def setup_method(self):
        self.strategy = ChipStrategy()

    def test_recommend_returns_list(self):
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=["wildcard", "free_hit", "triple_captain", "bench_boost"],
        )
        assert isinstance(recs, list)
        assert len(recs) == 4

    def test_recommend_with_no_chips(self):
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=[],
        )
        assert recs == []

    def test_each_chip_has_recommendation(self):
        chips = ["wildcard", "free_hit", "triple_captain", "bench_boost"]
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=chips,
        )
        rec_chips = {r.chip_type.value for r in recs}
        for chip in chips:
            assert chip in rec_chips, f"Missing recommendation for {chip}"

    def test_recommendations_have_positive_ev(self):
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=["triple_captain"],
        )
        assert len(recs) == 1
        # TC should always have positive EV (captain's predicted points)
        assert recs[0].expected_value > 0

    def test_tc_ev_equals_best_player_prediction(self):
        """Triple Captain EV = best player's predicted points in that GW."""
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw={28: FLAT_PREDICTIONS},
            chips_available=["triple_captain"],
        )
        assert len(recs) == 1
        best_pts = max(FLAT_PREDICTIONS.get(pid, 0) for pid in SQUAD_IDS)
        assert recs[0].expected_value == best_pts

    def test_recommendations_sorted_by_ev(self):
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=["wildcard", "free_hit", "triple_captain", "bench_boost"],
        )
        evs = [r.expected_value for r in recs]
        assert evs == sorted(evs, reverse=True), "Recommendations should be sorted by EV descending"

    def test_recommend_gameweek_within_range(self):
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=["triple_captain"],
        )
        valid_gws = set(PREDICTIONS_BY_GW.keys())
        for rec in recs:
            assert rec.recommended_gameweek in valid_gws

    def test_simulate_chip(self):
        result = self.strategy.simulate_chip(
            chip_type=ChipType.TRIPLE_CAPTAIN,
            gameweek=28,
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
        )
        assert "projected_points_with_chip" in result
        assert "projected_points_without_chip" in result
        assert "point_delta" in result
        assert result["point_delta"] > 0

    def test_bench_boost_ev(self):
        """BB EV should be the sum of bench player predictions."""
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw={28: FLAT_PREDICTIONS},
            chips_available=["bench_boost"],
        )
        assert len(recs) == 1
        # Bench = bottom 4 from squad by prediction
        squad_preds = sorted(
            [(pid, FLAT_PREDICTIONS.get(pid, 0)) for pid in SQUAD_IDS],
            key=lambda x: x[1], reverse=True,
        )
        bench_pts = sum(pts for _, pts in squad_preds[11:15])
        assert abs(recs[0].expected_value - bench_pts) < 0.01

    def test_reasoning_not_empty(self):
        recs = self.strategy.recommend(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=["wildcard", "free_hit"],
        )
        for rec in recs:
            assert rec.reasoning, f"Reasoning for {rec.chip_type} should not be empty"


# ======================================================================
# SensitivityAnalyzer tests
# ======================================================================

class TestSensitivityAnalyzer:
    """Tests for transfer sensitivity analysis."""

    def setup_method(self):
        self.analyzer = SensitivityAnalyzer()

    def test_analyze_empty_transfers(self):
        result = self.analyzer.analyze(
            current_squad=SQUAD_IDS,
            proposed_transfers=[],
            predictions=FLAT_PREDICTIONS,
        )
        assert isinstance(result, SensitivityResult)
        assert result.robustness_score == 1.0

    def test_strong_transfer_classification(self):
        """A transfer with large point gap should be classified as strong."""
        # Player 19 (3.0pts) -> Player 14 (3.5pts) -- small gap
        # Player 19 (3.0pts) -> Player 9 (2.5pts) -- negative
        # Use a large gap: out=20(2.5pts), in=16(9.0pts)
        # But 16 is in squad already. Use out=19(3.0pts), in=14(3.5pts)
        # Actually let's make it clearer: custom preds
        preds = {19: 2.0, 14: 8.0}  # Huge gap
        result = self.analyzer.analyze(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14)],
            predictions=preds,
        )
        assert len(result.transfer_classifications) == 1
        tc = result.transfer_classifications[0]
        assert tc.classification == TransferClassification.STRONG
        assert tc.recommendation_rate > 0.8

    def test_volatile_transfer_classification(self):
        """A transfer with tiny point gap should be volatile or moderate."""
        preds = {19: 4.9, 14: 5.0}  # Very small gap (0.1)
        result = self.analyzer.analyze(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14)],
            predictions=preds,
        )
        tc = result.transfer_classifications[0]
        # With perturbations of +/-20%, a 0.1 gap flips easily
        assert tc.classification in (
            TransferClassification.MODERATE,
            TransferClassification.VOLATILE,
        )

    def test_robustness_score_range(self):
        result = self.analyzer.analyze(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14)],
            predictions=FLAT_PREDICTIONS,
        )
        assert 0.0 <= result.robustness_score <= 1.0

    def test_multiple_transfers(self):
        result = self.analyzer.analyze(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14), (8, 9)],
            predictions=FLAT_PREDICTIONS,
        )
        assert len(result.transfer_classifications) == 2

    def test_detailed_analysis(self):
        """Detailed analysis uses 9 perturbation levels."""
        result = self.analyzer.analyze_detailed(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14)],
            predictions={19: 2.0, 14: 8.0},
        )
        assert result.transfer_classifications[0].classification == TransferClassification.STRONG

    def test_asymmetric_analysis(self):
        """Asymmetric analysis creates a grid of scenarios."""
        result = self.analyzer.analyze_asymmetric(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14)],
            predictions={19: 2.0, 14: 8.0},
        )
        assert result.transfer_classifications[0].classification == TransferClassification.STRONG
        # 25 scenarios in asymmetric mode
        assert result.transfer_classifications[0].recommendation_rate > 0.5

    def test_serialization(self):
        result = self.analyzer.analyze(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14)],
            predictions=FLAT_PREDICTIONS,
        )
        d = result.to_dict()
        assert "transfer_classifications" in d
        assert "robustness_score" in d


# ======================================================================
# EffectiveOwnership tests
# ======================================================================

class TestEffectiveOwnership:
    """Tests for effective ownership calculation."""

    def setup_method(self):
        self.eo_calc = EffectiveOwnership()

    def test_calculate_returns_list(self):
        results = self.eo_calc.calculate(players=MOCK_PLAYERS)
        assert isinstance(results, list)
        assert len(results) == len(MOCK_PLAYERS)

    def test_eo_equals_ownership_plus_captaincy(self):
        captaincy = {10: 25.0, 16: 15.0}
        results = self.eo_calc.calculate(
            players=MOCK_PLAYERS,
            captaincy_rates=captaincy,
        )
        for r in results:
            if r.player_id == 10:
                assert r.effective_ownership == 60.0 + 25.0  # 60% ownership + 25% captaincy
            elif r.player_id == 16:
                assert r.effective_ownership == 55.0 + 15.0

    def test_sorted_by_eo_descending(self):
        results = self.eo_calc.calculate(players=MOCK_PLAYERS)
        eos = [r.effective_ownership for r in results]
        assert eos == sorted(eos, reverse=True)

    def test_differential_classification(self):
        """Low EO players with high predicted points are differentials."""
        # Player 14: 6% ownership -> very low EO
        # If predicted 8pts, should be differential
        results = self.eo_calc.calculate(
            players=MOCK_PLAYERS,
            predicted_points={14: 8.0},
        )
        p14 = next(r for r in results if r.player_id == 14)
        assert p14.is_differential, "Player 14 with 6% ownership and 8pts should be differential"

    def test_template_classification(self):
        """High EO players are template picks."""
        results = self.eo_calc.calculate(players=MOCK_PLAYERS)
        # Player 10 has 60% ownership -> with captaincy estimate, EO > 50%
        p10 = next(r for r in results if r.player_id == 10)
        assert p10.is_template, "Player 10 with 60% ownership should be template"

    def test_low_ownership_not_differential_without_points(self):
        """Low EO alone is not enough -- need predicted points."""
        results = self.eo_calc.calculate(
            players=MOCK_PLAYERS,
            predicted_points={20: 1.0},  # Low points
        )
        p20 = next(r for r in results if r.player_id == 20)
        assert not p20.is_differential, "Low predicted points should not be differential"

    def test_get_differentials(self):
        diffs = self.eo_calc.get_differentials(
            players=MOCK_PLAYERS,
            predicted_points={pid: 6.0 for pid in range(1, 21)},
        )
        assert isinstance(diffs, list)
        for d in diffs:
            assert d.effective_ownership < 10.0

    def test_get_template_picks(self):
        templates = self.eo_calc.get_template_picks(players=MOCK_PLAYERS)
        assert isinstance(templates, list)
        for t in templates:
            assert t.effective_ownership >= 50.0

    def test_captaincy_estimation(self):
        """Estimated captaincy should be reasonable."""
        rate = self.eo_calc._estimate_captaincy_rate(60.0)
        assert 10.0 <= rate <= 40.0, "60% ownership should give 10-40% captaincy"

        rate_low = self.eo_calc._estimate_captaincy_rate(3.0)
        assert rate_low < 2.0, "3% ownership should give very low captaincy"

    def test_serialization(self):
        results = self.eo_calc.calculate(players=MOCK_PLAYERS[:3])
        for r in results:
            d = r.to_dict()
            assert "player_id" in d
            assert "effective_ownership" in d
            assert "is_differential" in d


# ======================================================================
# TransferEngine facade tests
# ======================================================================

class TestTransferEngine:
    """Tests for the facade that composes all sub-modules."""

    def setup_method(self):
        self.engine = TransferEngine()

    def test_plan_transfers(self):
        plan = self.engine.plan_transfers(
            current_squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            free_transfers=1,
            budget_remaining=1.0,
            horizon=3,
        )
        assert isinstance(plan, TransferPlan)

    def test_recommend_transfers_legacy(self):
        moves = self.engine.recommend_transfers(
            current_squad=SQUAD_IDS,
            bank=10,
            free_transfers=1,
            horizon=1,
            predicted_points=FLAT_PREDICTIONS,
        )
        assert isinstance(moves, list)

    def test_recommend_transfers_empty_predictions(self):
        moves = self.engine.recommend_transfers(
            current_squad=SQUAD_IDS,
            bank=10,
            free_transfers=1,
        )
        assert moves == []

    def test_create_multi_gw_plan(self):
        plans = self.engine.create_multi_gw_plan(
            current_squad=SQUAD_IDS,
            bank=10,
            free_transfers=1,
            horizon=5,
            predictions_by_gw=PREDICTIONS_BY_GW,
        )
        assert isinstance(plans, list)

    def test_evaluate_transfers_valid(self):
        result = self.engine.evaluate_transfers(
            transfers_in=[14],
            transfers_out=[19],
            current_squad=SQUAD_IDS,
            bank=50,
        )
        assert result["is_valid"] is True

    def test_evaluate_transfers_mismatched_lengths(self):
        result = self.engine.evaluate_transfers(
            transfers_in=[14, 15],
            transfers_out=[19],
            current_squad=SQUAD_IDS,
            bank=50,
        )
        assert result["is_valid"] is False

    def test_evaluate_transfers_player_not_in_squad(self):
        result = self.engine.evaluate_transfers(
            transfers_in=[14],
            transfers_out=[99],  # Not in squad
            current_squad=SQUAD_IDS,
            bank=50,
        )
        assert result["is_valid"] is False

    def test_recommend_chips(self):
        recs = self.engine.recommend_chips(
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
            chips_available=["wildcard", "triple_captain"],
        )
        assert isinstance(recs, list)
        assert len(recs) == 2

    def test_simulate_chip(self):
        result = self.engine.simulate_chip(
            chip_type="triple_captain",
            gameweek=28,
            squad=SQUAD_IDS,
            predictions_by_gw=PREDICTIONS_BY_GW,
        )
        assert "point_delta" in result

    def test_analyze_sensitivity(self):
        result = self.engine.analyze_sensitivity(
            current_squad=SQUAD_IDS,
            proposed_transfers=[(19, 14)],
            predictions=FLAT_PREDICTIONS,
        )
        assert isinstance(result, SensitivityResult)

    def test_get_effective_ownership(self):
        results = self.engine.get_effective_ownership(players=MOCK_PLAYERS)
        assert isinstance(results, list)
        assert len(results) == len(MOCK_PLAYERS)

    def test_singleton_accessor(self):
        engine1 = get_transfer_engine()
        engine2 = get_transfer_engine()
        assert engine1 is engine2


# ======================================================================
# Model serialization tests
# ======================================================================

class TestModelSerialization:
    """Verify all dataclass models serialize correctly."""

    def test_transfer_action_to_dict(self):
        action = TransferAction(
            gameweek=28, player_out_id=19, player_in_id=14,
            cost_delta=0.5, predicted_point_gain=2.0,
        )
        d = action.to_dict()
        assert d["gameweek"] == 28
        assert d["player_out_id"] == 19
        assert d["player_in_id"] == 14

    def test_transfer_plan_to_dict(self):
        plan = TransferPlan(
            actions=[
                TransferAction(28, 19, 14, 0.5, 2.0),
            ],
            total_hits=0,
            net_point_gain=2.0,
            gameweeks_covered=1,
        )
        d = plan.to_dict()
        assert d["total_hits"] == 0
        assert d["net_point_gain"] == 2.0
        assert d["total_hit_cost"] == 0
        assert len(d["actions"]) == 1

    def test_chip_recommendation_to_dict(self):
        rec = ChipRecommendation(
            chip_type=ChipType.TRIPLE_CAPTAIN,
            recommended_gameweek=28,
            expected_value=8.5,
            reasoning="Best captain fixture",
        )
        d = rec.to_dict()
        assert d["chip_type"] == "triple_captain"
        assert d["recommended_gameweek"] == 28

    def test_player_eo_to_dict(self):
        eo = PlayerEO(
            player_id=10, ownership=60.0, captaincy_rate=25.0,
            effective_ownership=85.0, is_differential=False, is_template=True,
        )
        d = eo.to_dict()
        assert d["effective_ownership"] == 85.0
        assert d["is_template"] is True

    def test_transfer_plan_hit_cost_property(self):
        plan = TransferPlan(total_hits=3)
        assert plan.total_hit_cost == 12


# ======================================================================
# API endpoint tests (smoke tests -- verify routes return 200)
# ======================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class TestTransferAPIEndpoints:
    """Smoke tests for transfer API endpoints."""

    def test_recommend_endpoint(self, client):
        response = client.post("/api/transfers/recommend", json={
            "current_squad": SQUAD_IDS,
            "bank": 10,
            "free_transfers": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "transfers" in data

    def test_plan_endpoint(self, client):
        response = client.post("/api/transfers/plan", json={
            "current_squad": SQUAD_IDS,
            "bank": 10,
            "free_transfers": 1,
            "horizon": 3,
        })
        assert response.status_code == 200
        data = response.json()
        assert "gameweek_plans" in data

    def test_evaluate_endpoint(self, client):
        response = client.post("/api/transfers/evaluate", json={
            "transfers_in": [14],
            "transfers_out": [19],
            "current_squad": SQUAD_IDS,
            "bank": 50,
        })
        assert response.status_code == 200
        data = response.json()
        assert "is_valid" in data

    def test_effective_ownership_endpoint(self, client):
        response = client.get("/api/transfers/effective-ownership")
        assert response.status_code == 200

    def test_chip_strategy_endpoint(self, client):
        response = client.post("/api/chips/strategy", json={
            "current_squad": SQUAD_IDS,
            "available_chips": ["wildcard", "triple_captain"],
            "current_gw": 28,
        })
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data

    def test_chip_simulate_endpoint(self, client):
        response = client.post("/api/chips/simulate", json={
            "chip": "triple_captain",
            "gameweek": 28,
            "current_squad": SQUAD_IDS,
        })
        assert response.status_code == 200
        data = response.json()
        assert "point_delta" in data
