"""Tests for the fixture-aware scoring module."""

import pytest

from app.data.models import Player, Position, Team
from app.prediction.fixture_scorer import (
    FixtureAwareScorer,
    FixtureLookup,
    build_fixture_lookup,
    FDR_FACTORS,
    FDR_FACTORS_ATTACK,
    FDR_FACTORS_DEFENCE,
    MULTIPLIER_MIN,
    MULTIPLIER_MAX,
    MULTIPLIER_MIN_DEF,
    MULTIPLIER_MAX_DEF,
    OPP_STRENGTH_MIN,
    OPP_STRENGTH_MAX,
    OPP_STRENGTH_MIN_DEF,
    OPP_STRENGTH_MAX_DEF,
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
        "threat": 700.0,  # 35.0 per 90 = FWD baseline
        "creativity": 400.0,  # 20.0 per 90 = FWD baseline
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
        "clean_sheets": 10,  # ~0.33 per 90 = baseline
        "threat": 100.0,
        "creativity": 100.0,
        "now_cost": 55,
        "status": "a",
        "chance_of_playing_next_round": 100,
    }
    defaults.update(overrides)
    return Player(**defaults)


def _make_gkp(**overrides) -> Player:
    """Create a GKP player."""
    defaults = {
        "id": 20,
        "web_name": "TestGK",
        "team": 2,
        "element_type": 1,  # GKP
        "form": 4.0,
        "points_per_game": 3.5,
        "minutes": 2700,  # 30 appearances
        "expected_goals": 0.0,
        "expected_assists": 0.5,
        "expected_goals_conceded": 36.0,
        "clean_sheets": 10,
        "threat": 0.0,
        "creativity": 30.0,
        "now_cost": 50,
        "status": "a",
        "chance_of_playing_next_round": 100,
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
    """test_positional_scoring_defender: DEF vs weak attack scores >= 10% higher."""

    def test_defender_vs_weak_attack_bigger_boost(self):
        """DEF vs bottom-3 attack scores ≥10% higher than vs top-3."""
        scorer = FixtureAwareScorer()

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
        assert ratio >= 1.10, f"Expected >= 10% difference, got {ratio:.3f}x"


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
    """Dynamic form/PPG weighting: in-form 65/35, out-of-form 55/45, equal 50/50."""

    def test_in_form_weighting(self):
        """form > ppg → 0.65 * form + 0.35 * ppg."""
        scorer = FixtureAwareScorer()
        player = _make_player(form=6.0, points_per_game=4.0)
        base = scorer._compute_base_score(player)
        expected = round(0.65 * 6.0 + 0.35 * 4.0, 2)  # 5.3
        assert base == expected

    def test_out_of_form_weighting(self):
        """form < ppg → 0.55 * form + 0.45 * ppg."""
        scorer = FixtureAwareScorer()
        player = _make_player(form=3.0, points_per_game=6.0)
        base = scorer._compute_base_score(player)
        expected = round(0.55 * 3.0 + 0.45 * 6.0, 2)  # 4.35
        assert base == expected

    def test_equal_form_ppg_weighting(self):
        """form == ppg → 0.5 * form + 0.5 * ppg."""
        scorer = FixtureAwareScorer()
        player = _make_player(form=5.0, points_per_game=5.0)
        base = scorer._compute_base_score(player)
        expected = round(0.5 * 5.0 + 0.5 * 5.0, 2)  # 5.0
        assert base == expected


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


# ---------------------------------------------------------------------------
# Enhanced Defensive Scoring Tests
# ---------------------------------------------------------------------------

class TestDefenderFDRSteeperThanAttacker:
    """DEF FDR 1 vs FDR 5 spread should be wider than FWD."""

    def test_defender_fdr_steeper_than_attacker(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()

        # Same base stats, different positions
        fwd = _make_player(id=1, team=1)
        defender = _make_defender(id=2, team=1)

        easy = _make_fixture_lookup(1, 5, is_home=True, fdr=1)
        hard = _make_fixture_lookup(1, 5, is_home=True, fdr=5)

        fwd_easy = scorer.score_player(fwd, easy, teams)
        fwd_hard = scorer.score_player(fwd, hard, teams)
        fwd_spread = fwd_easy.final_score / fwd_hard.final_score

        def_easy = scorer.score_player(defender, easy, teams)
        def_hard = scorer.score_player(defender, hard, teams)
        def_spread = def_easy.final_score / def_hard.final_score

        assert def_spread > fwd_spread, (
            f"DEF spread ({def_spread:.3f}) should be wider than "
            f"FWD spread ({fwd_spread:.3f})"
        )


class TestGKPCleanSheetFactor:
    """GKP with high CS rate scores higher than GKP with low CS rate."""

    def test_high_cs_gkp_scores_higher(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(2, 5, is_home=True, fdr=3)

        # High CS rate GKP: 15 CS in 30 appearances (0.50 per 90)
        high_cs = _make_gkp(id=20, team=2, clean_sheets=15)
        # Low CS rate GKP: 3 CS in 30 appearances (0.10 per 90)
        low_cs = _make_gkp(id=21, team=2, clean_sheets=3)

        high_result = scorer.score_player(high_cs, fixture, teams)
        low_result = scorer.score_player(low_cs, fixture, teams)

        assert high_result.final_score > low_result.final_score, (
            f"High CS GKP ({high_result.final_score}) should score higher "
            f"than low CS GKP ({low_result.final_score})"
        )


class TestDefenderMultiplierBounds:
    """Total multiplier within [0.70, 1.45] for DEF/GKP."""

    def test_extreme_best_case_def(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        # Very weak attack opponent
        teams[5] = _make_team(5, "VeryWeak", strength_attack_away=800)

        defender = _make_defender(team=2)
        fixture = _make_fixture_lookup(2, 5, is_home=True, fdr=1)

        result = scorer.score_player(defender, fixture, teams)
        mult = result.fixtures[0].fixture_multiplier
        assert mult <= MULTIPLIER_MAX_DEF, f"DEF multiplier {mult} > {MULTIPLIER_MAX_DEF}"
        assert mult >= MULTIPLIER_MIN_DEF, f"DEF multiplier {mult} < {MULTIPLIER_MIN_DEF}"

    def test_extreme_worst_case_def(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        # Very strong attack opponent
        teams[5] = _make_team(5, "VeryStrong", strength_attack_home=1600)

        defender = _make_defender(team=2)
        fixture = _make_fixture_lookup(2, 5, is_home=False, fdr=5)

        result = scorer.score_player(defender, fixture, teams)
        mult = result.fixtures[0].fixture_multiplier
        assert mult >= MULTIPLIER_MIN_DEF, f"DEF multiplier {mult} < {MULTIPLIER_MIN_DEF}"
        assert mult <= MULTIPLIER_MAX_DEF, f"DEF multiplier {mult} > {MULTIPLIER_MAX_DEF}"

    def test_gkp_bounds(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        teams[5] = _make_team(5, "VeryWeak", strength_attack_away=800)

        gkp = _make_gkp(team=2)
        fixture = _make_fixture_lookup(2, 5, is_home=True, fdr=1)

        result = scorer.score_player(gkp, fixture, teams)
        mult = result.fixtures[0].fixture_multiplier
        assert MULTIPLIER_MIN_DEF <= mult <= MULTIPLIER_MAX_DEF


class TestMinutesFactor:
    """Test minutes/availability probability factor."""

    def test_unavailable_player_scores_zero(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=3)

        injured = _make_player(status="i")
        result = scorer.score_player(injured, fixture, teams)
        assert result.final_score == 0.0

    def test_doubtful_low_chance_penalized(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=3)

        # 50% chance, low minutes = penalized
        doubtful = _make_player(chance_of_playing_next_round=50, minutes=900)
        full = _make_player(chance_of_playing_next_round=100, minutes=2700)

        doubtful_score = scorer.score_player(doubtful, fixture, teams)
        full_score = scorer.score_player(full, fixture, teams)

        assert doubtful_score.final_score < full_score.final_score

    def test_very_low_chance_filtered_out(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=3)

        # 0% chance = filtered out
        zero_chance = _make_player(chance_of_playing_next_round=0)
        result = scorer.score_player(zero_chance, fixture, teams)
        assert result.final_score == 0.0

    def test_nailed_player_no_penalty(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=3)

        # 100% chance, high minutes = no penalty
        nailed = _make_player(chance_of_playing_next_round=100, minutes=2700)
        result = scorer.score_player(nailed, fixture, teams)
        assert "nailedness" not in " ".join(result.reasoning).lower()


class TestICTFactors:
    """Test ICT threat/creativity integration for attackers."""

    def test_high_threat_fwd_scores_higher(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=3)

        # High threat FWD
        high_threat = _make_player(id=1, threat=1400.0, creativity=400.0)
        # Low threat FWD
        low_threat = _make_player(id=2, threat=200.0, creativity=400.0)

        high_result = scorer.score_player(high_threat, fixture, teams)
        low_result = scorer.score_player(low_threat, fixture, teams)

        assert high_result.final_score > low_result.final_score

    def test_high_creativity_mid_scores_higher(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        fixture = _make_fixture_lookup(1, 5, is_home=True, fdr=3)

        # High creativity MID
        creative = _make_player(id=1, element_type=3, threat=400.0, creativity=1200.0)
        # Low creativity MID
        uncreative = _make_player(id=2, element_type=3, threat=400.0, creativity=100.0)

        creative_result = scorer.score_player(creative, fixture, teams)
        uncreative_result = scorer.score_player(uncreative, fixture, teams)

        assert creative_result.final_score > uncreative_result.final_score


class TestCSProbabilityIndependent:
    """Test that CS factor is independently computed, not double-counted."""

    def test_cs_factor_vs_weak_attack_boosts_defender(self):
        scorer = FixtureAwareScorer()
        teams = _make_teams_map()
        # Very weak attack
        teams[5] = _make_team(5, "Weak", strength_attack_home=800, strength_attack_away=800)
        # Very strong attack
        teams[6] = _make_team(6, "Strong", strength_attack_home=1500, strength_attack_away=1500)

        defender = _make_defender(team=2)

        weak_fix = _make_fixture_lookup(2, 5, is_home=True, fdr=3)
        strong_fix = _make_fixture_lookup(2, 6, is_home=True, fdr=3)

        vs_weak = scorer.score_player(defender, weak_fix, teams)
        vs_strong = scorer.score_player(defender, strong_fix, teams)

        # With same FDR, the CS probability factor should still differentiate
        ratio = vs_weak.final_score / vs_strong.final_score
        assert ratio > 1.05, f"Expected > 5% CS boost vs weak attack, got {ratio:.3f}x"
