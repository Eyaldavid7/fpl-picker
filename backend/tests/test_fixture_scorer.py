"""Tests for the fixture-aware scoring module."""

import pytest

from app.data.models import Player, Position, Team
from app.prediction.fixture_scorer import (
    FixtureAwareScorer,
    FixtureLookup,
    build_fixture_lookup,
    FDR_FACTORS,
    MULTIPLIER_MIN,
    MULTIPLIER_MAX,
    OPP_STRENGTH_MIN,
    OPP_STRENGTH_MAX,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(**overrides) -> Player:
    """Create a Player with sensible defaults, overridable."""
    defaults = {
        "id": 1,
        "web_name": "TestPlayer",
        "team": 1,
        "element_type": 4,  # FWD
        "form": 5.0,
        "points_per_game": 4.0,
        "minutes": 1800,  # ~20 appearances
        "expected_goals": 7.0,  # 0.39 per 90 (above FWD baseline 0.35)
        "expected_assists": 2.4,  # 0.13 per 90 (above FWD baseline 0.12)
        "expected_goals_conceded": 0.0,
        "selected_by_percent": 15.0,
        "chance_of_playing_next_round": 100,
        "now_cost": 80,
        "status": "a",
    }
    defaults.update(overrides)
    return Player(**defaults)


def _make_defender(**overrides) -> Player:
    """Create a DEF player."""
    defaults = {
        "id": 10,
        "web_name": "TestDef",
        "team": 2,
        "element_type": 2,  # DEF
        "form": 4.0,
        "points_per_game": 3.5,
        "minutes": 2700,  # 30 appearances
        "expected_goals": 1.5,
        "expected_assists": 2.0,
        "expected_goals_conceded": 36.0,  # 1.2 per 90 = baseline
        "now_cost": 55,
        "status": "a",
    }
    defaults.update(overrides)
    return Player(**defaults)


def _make_team(id: int, name: str = "Team", **overrides) -> Team:
    """Create a Team with even strength metrics."""
    defaults = {
        "id": id,
        "name": name,
        "short_name": name[:3].upper(),
        "strength": 3,
        "strength_overall_home": 1200,
        "strength_overall_away": 1200,
        "strength_attack_home": 1200,
        "strength_attack_away": 1200,
        "strength_defence_home": 1200,
        "strength_defence_away": 1200,
    }
    defaults.update(overrides)
    return Team(**defaults)


def _make_teams_map(n: int = 20) -> dict[int, Team]:
    """Create a league of n teams with average strength 1200."""
    teams = {}
    for i in range(1, n + 1):
        teams[i] = _make_team(i, f"Team{i}")
    return teams


def _make_fixture_lookup(
    team_id: int,
    opponent_id: int,
    is_home: bool = True,
    fdr: int = 3,
    opponent_name: str = "Opponent",
) -> FixtureLookup:
    """Build a simple single-fixture lookup."""
    return {
        team_id: [{
            "opponent_name": opponent_name,
            "opponent_id": opponent_id,
            "is_home": is_home,
            "fdr": fdr,
        }]
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHomeAwayBoost:
    """test_home_boost: Same player, same opponent — home score > away score."""

    def test_home_scores_higher_than_away(self):
        scorer = FixtureAwareScorer()
        player = _make_player()
        teams = _make_teams_map()

        home_lookup = _make_fixture_lookup(1, 5, is_home=True, fdr=3)
        away_lookup = _make_fixture_lookup(1, 5, is_home=False, fdr=3)

        home_result = scorer.score_player(player, home_lookup, teams)
        away_result = scorer.score_player(player, away_lookup, teams)

        assert home_result.final_score > away_result.final_score


class TestFDRRange:
    """test_fdr_range: FDR 1 > FDR 5 by at least 15%."""

    def test_fdr1_vs_fdr5_minimum_difference(self):
        scorer = FixtureAwareScorer()
        player = _make_player()
        teams = _make_teams_map()

        # FDR 1 at home vs FDR 5 away
        easy_lookup = _make_fixture_lookup(1, 5, is_home=True, fdr=1)
        hard_lookup = _make_fixture_lookup(1, 5, is_home=False, fdr=5)

        easy = scorer.score_player(player, easy_lookup, teams)
        hard = scorer.score_player(player, hard_lookup, teams)

        ratio = easy.final_score / hard.final_score
        assert ratio >= 1.15, f"Expected >= 15% difference, got {ratio:.3f}x"

    def test_fdr2_home_vs_fdr4_away(self):
        scorer = FixtureAwareScorer()
        player = _make_player()
        teams = _make_teams_map()

        easy_lookup = _make_fixture_lookup(1, 5, is_home=True, fdr=2)
        hard_lookup = _make_fixture_lookup(1, 5, is_home=False, fdr=4)

        easy = scorer.score_player(player, easy_lookup, teams)
        hard = scorer.score_player(player, hard_lookup, teams)

        assert easy.final_score > hard.final_score


class TestPositionalScoringAttacker:
    """test_positional_scoring_attacker: Above-average xG/90 gets higher factor."""

    def test_high_xg_attacker_scores_higher(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=3)

        # Above-average xG attacker
        good = _make_player(id=1, expected_goals=10.0, expected_assists=4.0)
        # Below-average xG attacker
        weak = _make_player(id=2, expected_goals=2.0, expected_assists=0.5)

        good_score = scorer.score_player(good, fixture, teams)
        weak_score = scorer.score_player(weak, fixture, teams)

        assert good_score.final_score > weak_score.final_score


class TestPositionalScoringDefender:
    """test_positional_scoring_defender: DEF vs weak attack scores >= 5% higher."""

    def test_defender_vs_weak_attack_scores_higher(self):
        scorer = FixtureAwareScorer()

        # Build teams: 3 weak attack, 3 strong attack, rest average
        teams = _make_teams_map()
        # Weak attack team (id=5)
        teams[5] = _make_team(5, "Weak", strength_attack_home=900, strength_attack_away=900)
        # Strong attack team (id=6)
        teams[6] = _make_team(6, "Strong", strength_attack_home=1400, strength_attack_away=1400)

        defender = _make_defender(team=2)

        weak_opp = _make_fixture_lookup(2, 5, is_home=True, fdr=2, opponent_name="Weak")
        strong_opp = _make_fixture_lookup(2, 6, is_home=True, fdr=4, opponent_name="Strong")

        vs_weak = scorer.score_player(defender, weak_opp, teams)
        vs_strong = scorer.score_player(defender, strong_opp, teams)

        ratio = vs_weak.final_score / vs_strong.final_score
        assert ratio >= 1.05, f"Expected >= 5% difference, got {ratio:.3f}x"


class TestMultiplierBounds:
    """test_multiplier_bounds: Total fixture multiplier within [0.75, 1.35]."""

    def test_extreme_best_case(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        # Very weak opponent
        teams[5] = _make_team(5, "VeryWeak", strength_defence_away=800)

        player = _make_player()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=1)

        result = scorer.score_player(player, fixture, teams)
        # fixture_multiplier should be clamped
        assert result.fixtures[0].fixture_multiplier <= MULTIPLIER_MAX
        assert result.fixtures[0].fixture_multiplier >= MULTIPLIER_MIN

    def test_extreme_worst_case(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        teams[5] = _make_team(5, "VeryStrong", strength_defence_home=1600)

        player = _make_player()
        fixture = _make_fixture_lookup(1, 5, is_home=False, fdr=5)

        result = scorer.score_player(player, fixture, teams)
        assert result.fixtures[0].fixture_multiplier >= MULTIPLIER_MIN
        assert result.fixtures[0].fixture_multiplier <= MULTIPLIER_MAX


class TestOpponentStrengthRange:
    """test_opponent_strength_factor_range: Factor within [0.90, 1.10]."""

    def test_factor_clamped(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        # Extremely weak
        teams[5] = _make_team(5, "ExWeak", strength_defence_away=600)

        player = _make_player()
        league_avgs = scorer._precompute_league_avgs(teams)

        factor = scorer._compute_opponent_strength_factor(
            player, teams[5], is_home=True, league_avgs=league_avgs
        )
        assert OPP_STRENGTH_MIN <= factor <= OPP_STRENGTH_MAX


class TestDGW:
    """test_dgw_scores_higher: DGW >= 1.5x SGW for similar difficulty."""

    def test_dgw_higher_than_sgw(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        player = _make_player()

        sgw_lookup: FixtureLookup = {
            1: [{"opponent_name": "A", "opponent_id": 5, "is_home": True, "fdr": 3}]
        }
        dgw_lookup: FixtureLookup = {
            1: [
                {"opponent_name": "A", "opponent_id": 5, "is_home": True, "fdr": 3},
                {"opponent_name": "B", "opponent_id": 6, "is_home": False, "fdr": 3},
            ]
        }

        sgw = scorer.score_player(player, sgw_lookup, teams)
        dgw = scorer.score_player(player, dgw_lookup, teams)

        ratio = dgw.final_score / sgw.final_score
        assert ratio >= 1.5, f"Expected DGW >= 1.5x SGW, got {ratio:.3f}x"

    def test_dgw_has_two_fixture_details(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        player = _make_player()

        dgw_lookup: FixtureLookup = {
            1: [
                {"opponent_name": "A", "opponent_id": 5, "is_home": True, "fdr": 2},
                {"opponent_name": "B", "opponent_id": 6, "is_home": False, "fdr": 4},
            ]
        }

        result = scorer.score_player(player, dgw_lookup, teams)
        assert len(result.fixtures) == 2
        assert "Double gameweek" in result.reasoning[0]


class TestBGW:
    """test_bgw_scores_zero: Player with 0 fixtures returns 0.0."""

    def test_bgw_final_score_zero(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        player = _make_player()

        empty_lookup: FixtureLookup = {}  # no fixtures for player's team

        result = scorer.score_player(player, empty_lookup, teams)
        assert result.final_score == 0.0
        assert len(result.fixtures) == 0
        assert any("BGW" in r for r in result.reasoning)


class TestScorerConsistency:
    """test_scorer_consistency: Same inputs produce same outputs."""

    def test_deterministic(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        player = _make_player()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=2)

        r1 = scorer.score_player(player, fixture, teams)
        r2 = scorer.score_player(player, fixture, teams)

        assert r1.final_score == r2.final_score
        assert r1.base_score == r2.base_score


class TestFormRegressionWeighting:
    """test_form_regression_weighting: base uses 0.5/0.5, not 0.65/0.35."""

    def test_weighting(self):
        scorer = FixtureAwareScorer()
        player = _make_player(form=6.0, points_per_game=4.0)

        base = scorer._compute_base_score(player)
        expected = round(0.5 * 6.0 + 0.5 * 4.0, 2)  # 5.0
        assert base == expected

        # Verify it's NOT the old weighting
        old = round(0.65 * 6.0 + 0.35 * 4.0, 2)  # 5.3
        assert base != old


class TestBuildFixtureLookup:
    """Test the DGW-aware fixture lookup builder."""

    def test_sgw_single_entry(self):
        from app.data.models import Fixture

        fixtures = [
            Fixture(id=1, event=10, team_h=1, team_a=2,
                    team_h_difficulty=3, team_a_difficulty=3)
        ]
        names = {1: "HOM", 2: "AWY"}
        lookup = build_fixture_lookup(fixtures, names)

        assert len(lookup[1]) == 1
        assert len(lookup[2]) == 1
        assert lookup[1][0]["is_home"] is True
        assert lookup[2][0]["is_home"] is False

    def test_dgw_two_entries(self):
        from app.data.models import Fixture

        fixtures = [
            Fixture(id=1, event=10, team_h=1, team_a=2,
                    team_h_difficulty=2, team_a_difficulty=4),
            Fixture(id=2, event=10, team_h=1, team_a=3,
                    team_h_difficulty=3, team_a_difficulty=3),
        ]
        names = {1: "HOM", 2: "AWY1", 3: "AWY2"}
        lookup = build_fixture_lookup(fixtures, names)

        # Team 1 has 2 home fixtures (DGW)
        assert len(lookup[1]) == 2
        assert lookup[1][0]["opponent_id"] == 2
        assert lookup[1][1]["opponent_id"] == 3
