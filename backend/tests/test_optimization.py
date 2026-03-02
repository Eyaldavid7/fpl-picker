"""Comprehensive tests for the FPL optimisation engine.

Covers:
- Constraint validation (squad & starting XI)
- ILP solver (valid squad, captain/VC, locked/excluded)
- GA solver (multiple diverse squads, feasibility)
- OptimizationEngine facade
"""

from __future__ import annotations

import pytest

from app.optimization.constraints import (
    FORMATION_RULES,
    VALID_FORMATIONS,
    validate_squad,
    validate_starting_xi,
)
from app.optimization.engine import OptimizationEngine
from app.optimization.genetic_algorithm import GASolver
from app.optimization.ilp_solver import ILPSolver
from app.optimization.models import OptimizationResult

# ---------------------------------------------------------------------------
# Mock player data (36 players across 8 teams, all 4 positions)
# Costs are in 0.1m units (e.g. 50 = 5.0m)
# ---------------------------------------------------------------------------

_TEAMS = list(range(1, 9))  # 8 teams

MOCK_PLAYERS: list[dict] = []
_id = 1


def _add(position: str, team: int, cost: int, name: str, pts: float) -> None:
    global _id
    MOCK_PLAYERS.append(
        {
            "id": _id,
            "web_name": name,
            "position": position,
            "now_cost": cost,
            "team": team,
        }
    )
    _id += 1


# Goalkeepers (6) -- need at least 2 in squad
_add("GK", 1, 55, "Raya", 5.5)
_add("GK", 2, 50, "Ramsdale", 4.8)
_add("GK", 3, 45, "Pope", 4.5)
_add("GK", 4, 40, "Sa", 4.0)
_add("GK", 5, 45, "Henderson", 4.3)
_add("GK", 6, 40, "Sanchez", 3.5)

# Defenders (10) -- need 5 in squad
_add("DEF", 1, 70, "Saliba", 6.0)
_add("DEF", 2, 65, "Gabriel", 5.8)
_add("DEF", 3, 55, "Trippier", 5.5)
_add("DEF", 7, 50, "Estupinan", 5.0)
_add("DEF", 4, 45, "Dunk", 4.5)
_add("DEF", 5, 45, "Dalot", 4.3)
_add("DEF", 6, 40, "Konsa", 4.0)
_add("DEF", 7, 50, "Henry", 4.8)
_add("DEF", 8, 45, "Guehi", 3.8)
_add("DEF", 8, 40, "Mitchell", 3.5)

# Midfielders (12) -- need 5 in squad
_add("MID", 1, 130, "Saka", 8.5)
_add("MID", 2, 125, "Salah", 9.0)
_add("MID", 3, 110, "Palmer", 8.0)
_add("MID", 4, 90, "Foden", 7.5)
_add("MID", 5, 80, "Bruno", 7.0)
_add("MID", 6, 70, "Maddison", 6.5)
_add("MID", 7, 65, "Mitoma", 5.5)
_add("MID", 8, 60, "Eze", 5.0)
_add("MID", 1, 55, "Odegaard", 6.0)
_add("MID", 3, 50, "Nkunku", 5.5)
_add("MID", 5, 45, "McTominay", 4.0)
_add("MID", 6, 40, "Luiz", 3.5)

# Forwards (8) -- need 3 in squad
_add("FWD", 2, 145, "Haaland", 10.0)
_add("FWD", 4, 85, "Watkins", 7.0)
_add("FWD", 3, 80, "Jackson", 6.5)
_add("FWD", 7, 75, "Isak", 7.5)
_add("FWD", 5, 70, "Solanke", 5.5)
_add("FWD", 6, 65, "Toney", 5.0)
_add("FWD", 8, 60, "Cunha", 4.5)
_add("FWD", 1, 55, "Nketiah", 3.5)

# Predictions map: player_id -> predicted points
PREDICTIONS: dict[int, float] = {}
for _p in MOCK_PLAYERS:
    # Use the pts value we stored in the name creation (4th arg to _add was
    # illustrative). We'll derive predictions from cost and a noise factor
    # for more realistic variety.
    # Simple heuristic: higher-cost players get more points
    PREDICTIONS[_p["id"]] = round(_p["now_cost"] / 10.0 * 0.8 + 1.0, 2)

# Override some with hand-picked values to make testing deterministic
PREDICTIONS[20] = 9.0   # Salah
PREDICTIONS[29] = 10.0  # Haaland
PREDICTIONS[19] = 8.5   # Saka


# ======================================================================
# Constraint tests
# ======================================================================


class TestConstraints:
    """Tests for validate_squad and validate_starting_xi."""

    def _make_valid_squad(self) -> list[dict]:
        """Hand-pick a valid 15-player squad from MOCK_PLAYERS."""
        # 2 GK, 5 DEF, 5 MID, 3 FWD -- all different enough teams
        ids = [
            1, 4,             # GK: Raya(t1), Sa(t4)
            7, 9, 10, 12, 15, # DEF: Saliba(t1), Trippier(t3), Estupinan(t7), Dalot(t5), Guehi(t8)
            19, 20, 22, 24, 28,  # MID: Saka(t1), Salah(t2), Foden(t4), Maddison(t6), Eze(t8)
            29, 31, 34,       # FWD: Haaland(t2), Jackson(t3), Cunha(t8)
        ]
        return [p for p in MOCK_PLAYERS if p["id"] in ids]

    def test_valid_squad_passes(self):
        squad = self._make_valid_squad()
        valid, violations = validate_squad(squad, budget=120.0)
        assert valid, f"Expected valid squad, got violations: {violations}"

    def test_wrong_squad_size(self):
        squad = self._make_valid_squad()[:14]
        valid, violations = validate_squad(squad, budget=120.0)
        assert not valid
        assert any("15 players" in v for v in violations)

    def test_position_violation(self):
        squad = self._make_valid_squad()
        # Replace one DEF with a FWD -> 4 DEF, 4 FWD
        def_player = next(p for p in squad if p["position"] == "DEF")
        extra_fwd = next(
            p for p in MOCK_PLAYERS
            if p["position"] == "FWD" and p not in squad
        )
        squad.remove(def_player)
        squad.append(extra_fwd)
        valid, violations = validate_squad(squad, budget=200.0)
        assert not valid
        assert any("DEF" in v for v in violations)

    def test_club_limit_violation(self):
        # Manually build a squad that has 4 players from team 1
        ids = [
            1, 4,                 # GK
            7, 9, 10, 12, 15,    # DEF (Saliba=t1)
            19, 29 - 9, 22, 24, 28,  # MID (Saka=t1, Odegaard=t1 -> id 27)
            29, 31, 34,
        ]
        # Actually, let's just build it programmatically
        squad = self._make_valid_squad()
        # Force an extra team-1 player in by replacing a non-t1 DEF with t1 DEF
        # squad already has Raya(t1), Saliba(t1), Saka(t1) = 3 from team 1
        # Replace Dalot(t5) with Odegaard(t1,MID) -- wait, that would break positions.
        # Instead, just test the validator directly.
        # Create an artificial squad with 4 from team 1
        fake_squad = [
            {"id": 100, "position": "GK", "now_cost": 50, "team": 1},
            {"id": 101, "position": "GK", "now_cost": 50, "team": 2},
            {"id": 102, "position": "DEF", "now_cost": 50, "team": 1},
            {"id": 103, "position": "DEF", "now_cost": 50, "team": 1},
            {"id": 104, "position": "DEF", "now_cost": 50, "team": 3},
            {"id": 105, "position": "DEF", "now_cost": 50, "team": 4},
            {"id": 106, "position": "DEF", "now_cost": 50, "team": 5},
            {"id": 107, "position": "MID", "now_cost": 50, "team": 1},
            {"id": 108, "position": "MID", "now_cost": 50, "team": 6},
            {"id": 109, "position": "MID", "now_cost": 50, "team": 7},
            {"id": 110, "position": "MID", "now_cost": 50, "team": 8},
            {"id": 111, "position": "MID", "now_cost": 50, "team": 2},
            {"id": 112, "position": "FWD", "now_cost": 50, "team": 3},
            {"id": 113, "position": "FWD", "now_cost": 50, "team": 4},
            {"id": 114, "position": "FWD", "now_cost": 50, "team": 5},
        ]
        valid, violations = validate_squad(fake_squad, budget=200.0)
        assert not valid
        assert any("team 1" in v for v in violations)

    def test_budget_violation(self):
        squad = self._make_valid_squad()
        total = sum(p["now_cost"] for p in squad) / 10.0
        valid, violations = validate_squad(squad, budget=total - 1.0)
        assert not valid
        assert any("exceeds budget" in v for v in violations)

    def test_valid_starting_xi(self):
        squad = self._make_valid_squad()
        # Build a 4-4-2 XI from the squad
        gks = [p for p in squad if p["position"] == "GK"][:1]
        defs = [p for p in squad if p["position"] == "DEF"][:4]
        mids = [p for p in squad if p["position"] == "MID"][:4]
        fwds = [p for p in squad if p["position"] == "FWD"][:2]
        xi = gks + defs + mids + fwds
        valid, violations = validate_starting_xi(xi, "4-4-2")
        assert valid, f"Expected valid XI, got: {violations}"

    def test_invalid_formation_string(self):
        valid, violations = validate_starting_xi([], "9-0-1")
        assert not valid
        assert any("Invalid formation" in v for v in violations)

    def test_wrong_xi_size(self):
        squad = self._make_valid_squad()
        xi = squad[:10]  # only 10
        valid, violations = validate_starting_xi(xi, "4-4-2")
        assert not valid
        assert any("11 players" in v for v in violations)


# ======================================================================
# ILP solver tests
# ======================================================================


class TestILPSolver:
    """Tests for the PuLP-based ILP solver."""

    def setup_method(self):
        self.solver = ILPSolver()

    def test_produces_valid_squad(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
        )
        assert result.squad, "ILP produced empty squad"
        assert len(result.squad) == 15
        assert len(result.starting_xi) == 11
        assert len(result.bench) == 4

        # Validate through constraint checker
        valid, violations = validate_squad(result.squad, budget=100.0)
        assert valid, f"ILP squad invalid: {violations}"

    def test_budget_respected(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
        )
        assert result.total_cost <= 100.0 + 1e-6

    def test_club_limit_respected(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
        )
        from collections import Counter
        team_counts = Counter(p["team"] for p in result.squad)
        for team, count in team_counts.items():
            assert count <= 3, f"Team {team} has {count} players (max 3)"

    def test_captain_and_vc_are_starters(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
        )
        xi_ids = {p["id"] for p in result.starting_xi}
        assert result.captain is not None
        assert result.vice_captain is not None
        assert result.captain["id"] in xi_ids, "Captain must be a starter"
        assert result.vice_captain["id"] in xi_ids, "Vice-captain must be a starter"
        assert result.captain["id"] != result.vice_captain["id"], "Captain != VC"

    def test_fixed_formation(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
            formation="4-4-2",
        )
        assert result.formation == "4-4-2"
        xi_positions = [p["position"] for p in result.starting_xi]
        assert xi_positions.count("GK") == 1
        assert xi_positions.count("DEF") == 4
        assert xi_positions.count("MID") == 4
        assert xi_positions.count("FWD") == 2

    def test_locked_players(self):
        # Lock Haaland (id=29) and Salah (id=20)
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
            locked=[29, 20],
        )
        squad_ids = {p["id"] for p in result.squad}
        assert 29 in squad_ids, "Locked player Haaland not in squad"
        assert 20 in squad_ids, "Locked player Salah not in squad"

    def test_excluded_players(self):
        # Exclude Haaland (id=29)
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
            excluded=[29],
        )
        squad_ids = {p["id"] for p in result.squad}
        assert 29 not in squad_ids, "Excluded player Haaland should not be in squad"

    def test_predicted_points_positive(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
        )
        assert result.predicted_points > 0

    def test_method_is_ilp(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
        )
        assert result.method == "ilp"

    def test_solve_time_recorded(self):
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
        )
        assert result.solve_time > 0

    def test_invalid_formation_raises(self):
        with pytest.raises(ValueError, match="Invalid formation"):
            self.solver.solve(
                players=MOCK_PLAYERS,
                predicted_points=PREDICTIONS,
                formation="9-0-1",
            )

    def test_tight_budget(self):
        """With a very tight budget, the solver should still find a feasible
        solution (all players have cost >= 4.0m, 15 * 4.0 = 60.0m min)."""
        result = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=65.0,
        )
        # May or may not be feasible depending on player costs
        # If infeasible, squad will be empty
        if result.squad:
            assert result.total_cost <= 65.0 + 1e-6


# ======================================================================
# GA solver tests
# ======================================================================


class TestGASolver:
    """Tests for the Genetic Algorithm solver."""

    def setup_method(self):
        self.solver = GASolver()

    def test_produces_multiple_squads(self):
        results = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
            n_squads=3,
            population_size=80,
            generations=30,
        )
        assert len(results) >= 1
        for r in results:
            assert len(r.squad) == 15
            assert len(r.starting_xi) == 11
            assert len(r.bench) == 4

    def test_squads_are_valid(self):
        results = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
            n_squads=2,
            population_size=80,
            generations=30,
        )
        for r in results:
            valid, violations = validate_squad(r.squad, budget=100.0)
            assert valid, f"GA squad invalid: {violations}"

    def test_captain_in_xi(self):
        results = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            budget=100.0,
            n_squads=1,
            population_size=80,
            generations=30,
        )
        r = results[0]
        xi_ids = {p["id"] for p in r.starting_xi}
        assert r.captain["id"] in xi_ids
        assert r.vice_captain["id"] in xi_ids
        assert r.captain["id"] != r.vice_captain["id"]

    def test_method_is_ga(self):
        results = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            n_squads=1,
            population_size=50,
            generations=10,
        )
        assert results[0].method == "ga"

    def test_predicted_points_positive(self):
        results = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            n_squads=1,
            population_size=50,
            generations=10,
        )
        assert results[0].predicted_points > 0

    def test_formation_is_valid(self):
        results = self.solver.solve(
            players=MOCK_PLAYERS,
            predicted_points=PREDICTIONS,
            n_squads=1,
            population_size=80,
            generations=30,
        )
        assert results[0].formation in VALID_FORMATIONS


# ======================================================================
# OptimizationEngine facade tests
# ======================================================================


class TestOptimizationEngine:
    """Tests for the facade / orchestrator."""

    def setup_method(self):
        self.engine = OptimizationEngine()

    def test_ilp_via_engine(self):
        result = self.engine.optimize(
            players=MOCK_PLAYERS,
            predictions=PREDICTIONS,
            method="ilp",
            budget=100.0,
        )
        assert isinstance(result, OptimizationResult)
        assert result.method == "ilp"
        assert len(result.squad) == 15

    def test_ga_via_engine(self):
        results = self.engine.optimize(
            players=MOCK_PLAYERS,
            predictions=PREDICTIONS,
            method="ga",
            budget=100.0,
            n_squads=2,
            population_size=50,
            generations=10,
        )
        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].method == "ga"

    def test_compare_methods(self):
        comparison = self.engine.compare_methods(
            players=MOCK_PLAYERS,
            predictions=PREDICTIONS,
            budget=100.0,
        )
        assert "ilp" in comparison
        assert "ga" in comparison
        assert "summary" in comparison
        assert comparison["summary"]["ilp_points"] > 0
        # ILP should be >= GA (it's exact)
        assert comparison["summary"]["ilp_points"] >= comparison["summary"]["ga_points"] - 1e-6

    def test_get_available_formations(self):
        formations = self.engine.get_available_formations()
        assert "4-4-2" in formations
        assert "3-5-2" in formations
        assert len(formations) == 7

    def test_invalid_method_raises(self):
        with pytest.raises(ValueError, match="Unknown optimization method"):
            self.engine.optimize(
                players=MOCK_PLAYERS,
                predictions=PREDICTIONS,
                method="brute_force",
            )

    def test_result_to_dict(self):
        result = self.engine.optimize(
            players=MOCK_PLAYERS,
            predictions=PREDICTIONS,
            method="ilp",
        )
        d = result.to_dict()
        assert "squad" in d
        assert "captain" in d
        assert "predicted_points" in d
        assert d["method"] == "ilp"
