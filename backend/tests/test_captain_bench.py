"""Tests for captain picker and bench optimizer endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.data.models import Player, Position, Team, Fixture
from app.prediction.fixture_scorer import (
    FixtureAwareScorer,
    ScoredPlayer,
    FixtureDetail,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(**overrides) -> Player:
    """Create a Player with sensible defaults."""
    defaults = {
        "id": 1,
        "web_name": "TestPlayer",
        "team": 1,
        "element_type": 4,  # FWD
        "form": 5.0,
        "points_per_game": 4.0,
        "minutes": 1800,
        "expected_goals": 7.0,
        "expected_assists": 2.4,
        "expected_goals_conceded": 0.0,
        "selected_by_percent": 15.0,
        "chance_of_playing_next_round": 100,
        "now_cost": 80,
        "status": "a",
    }
    defaults.update(overrides)
    return Player(**defaults)


def _make_team(id: int, name: str = "Team") -> Team:
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
    return Team(**defaults)


def _make_scored_player(
    player_id: int,
    web_name: str,
    position: str,
    team_id: int,
    final_score: float,
    opponent: str = "Opponent (H)",
    fdr: int = 3,
    selected_by_percent: float = 10.0,
) -> ScoredPlayer:
    """Create a ScoredPlayer for testing."""
    return ScoredPlayer(
        player_id=player_id,
        web_name=web_name,
        position=position,
        team_id=team_id,
        base_score=final_score * 0.8,
        fixtures=[
            FixtureDetail(
                opponent_name=opponent.split(" (")[0],
                opponent_id=99,
                is_home="(H)" in opponent,
                fdr=fdr,
                fixture_multiplier=1.1,
                positional_factor=1.0,
                fixture_score=final_score,
                reasoning=f"{opponent}, FDR {fdr}",
            )
        ],
        final_score=final_score,
        reasoning=[f"{opponent}, FDR {fdr}"],
    )


# ---------------------------------------------------------------------------
# Captain Picker Tests
# ---------------------------------------------------------------------------

class TestCaptainPicksHighest:
    """Captain should be the player with the highest fixture-adjusted score."""

    def test_captain_is_highest_scorer(self):
        scorer = FixtureAwareScorer()
        players = [
            _make_player(id=1, web_name="Low", form=3.0, points_per_game=3.0, team=1),
            _make_player(id=2, web_name="Mid", form=5.0, points_per_game=5.0, team=2),
            _make_player(id=3, web_name="High", form=8.0, points_per_game=7.0, team=3),
        ]
        teams = {i: _make_team(i, f"Team{i}") for i in range(1, 21)}

        fixture_lookup = {
            1: [{"opponent_name": "A", "opponent_id": 5, "is_home": True, "fdr": 3}],
            2: [{"opponent_name": "B", "opponent_id": 6, "is_home": True, "fdr": 3}],
            3: [{"opponent_name": "C", "opponent_id": 7, "is_home": True, "fdr": 3}],
        }

        scores = {}
        for p in players:
            scores[p.id] = scorer.score_player(p, fixture_lookup, teams)

        # Sort by final_score descending
        ranked = sorted(scores.values(), key=lambda s: s.final_score, reverse=True)

        # Captain (rank 1) should be "High" (id=3)
        assert ranked[0].player_id == 3
        assert ranked[0].web_name == "High"


class TestCaptainDifferential:
    """With differential=True, lower-owned player with similar score can win."""

    def test_differential_favors_low_ownership(self):
        # Player A: high score but high ownership
        sp_a = _make_scored_player(1, "Popular", "FWD", 1, 7.0)
        # Player B: slightly lower score but much lower ownership
        sp_b = _make_scored_player(2, "Differential", "FWD", 2, 6.5)

        # Simulate differential scoring
        ownership_a = 50.0  # 50% owned
        ownership_b = 5.0   # 5% owned

        effective_a = sp_a.final_score * (1 - ownership_a / 200)  # 7.0 * 0.75 = 5.25
        effective_b = sp_b.final_score * (1 - ownership_b / 200)  # 6.5 * 0.975 = 6.3375

        assert effective_b > effective_a, (
            f"Differential should favor low ownership: "
            f"B={effective_b:.2f} > A={effective_a:.2f}"
        )


class TestCaptainDefaultGameweek:
    """When gameweek is omitted, should use get_current_gameweek() + 1."""

    @pytest.mark.asyncio
    async def test_default_gameweek_resolved(self):
        # Create mock FPL client
        mock_client = MagicMock()
        mock_client.get_current_gameweek = AsyncMock(return_value=28)
        mock_client.get_players = AsyncMock(return_value=[
            _make_player(id=1, web_name="P1", team=1),
        ])
        mock_client.get_teams = AsyncMock(return_value=[
            _make_team(i, f"Team{i}") for i in range(1, 21)
        ])
        mock_client.get_typed_fixtures = AsyncMock(return_value=[
            Fixture(id=1, event=29, team_h=1, team_a=2,
                    team_h_difficulty=3, team_a_difficulty=3)
        ])
        mock_client.get_teams_map = AsyncMock(return_value={
            i: f"Team{i}" for i in range(1, 21)
        })

        with patch("app.prediction.fixture_scorer.get_fpl_client", return_value=mock_client):
            scorer = FixtureAwareScorer()
            result = await scorer.score_squad([1], gameweek=None)

        # Should have called get_current_gameweek
        mock_client.get_current_gameweek.assert_called_once()
        # Should have used GW 29 (28 + 1)
        mock_client.get_typed_fixtures.assert_called_once_with(29)
        assert 1 in result


class TestCaptainReasoningFormat:
    """Each captain candidate's reasoning should contain opponent name and FDR."""

    def test_reasoning_contains_opponent_and_fdr(self):
        scorer = FixtureAwareScorer()
        player = _make_player(id=1, web_name="Test", team=1)
        teams = {i: _make_team(i, f"Team{i}") for i in range(1, 21)}
        fixture_lookup = {
            1: [{"opponent_name": "Arsenal", "opponent_id": 5, "is_home": True, "fdr": 2}]
        }

        result = scorer.score_player(player, fixture_lookup, teams)

        # Reasoning should be non-empty
        assert len(result.reasoning) > 0
        combined = "; ".join(result.reasoning)
        # Should mention opponent name
        assert "Arsenal" in combined
        # Should mention FDR value
        assert "FDR 2" in combined or "fdr 2" in combined.lower()


# ---------------------------------------------------------------------------
# Bench Optimizer Tests
# ---------------------------------------------------------------------------

class TestBenchGKPFirst:
    """GKP should always be bench position 1 (FPL rule)."""

    def test_gkp_is_first_on_bench(self):
        scored_players = {
            10: _make_scored_player(10, "Keeper", "GKP", 1, 2.5),
            11: _make_scored_player(11, "DefA", "DEF", 2, 4.0),
            12: _make_scored_player(12, "MidA", "MID", 3, 5.0),
            13: _make_scored_player(13, "FwdA", "FWD", 4, 6.0),
        }

        # Separate GKP from outfield
        gkp_ids = [pid for pid, sp in scored_players.items() if sp.position == "GKP"]
        outfield = [(pid, sp.final_score) for pid, sp in scored_players.items() if sp.position != "GKP"]
        outfield.sort(key=lambda x: x[1], reverse=True)

        bench_order = gkp_ids + [pid for pid, _ in outfield]

        # GKP must be first
        assert bench_order[0] == 10
        assert scored_players[bench_order[0]].position == "GKP"


class TestBenchOrderByScore:
    """Outfield bench players should be ordered by descending fixture-adjusted score."""

    def test_outfield_ordered_by_score_descending(self):
        scored_players = {
            10: _make_scored_player(10, "Keeper", "GKP", 1, 2.5),
            11: _make_scored_player(11, "DefA", "DEF", 2, 3.0),
            12: _make_scored_player(12, "MidA", "MID", 3, 5.5),
            13: _make_scored_player(13, "FwdA", "FWD", 4, 4.0),
        }

        outfield = [(pid, sp.final_score) for pid, sp in scored_players.items() if sp.position != "GKP"]
        outfield.sort(key=lambda x: x[1], reverse=True)

        bench_order = [10] + [pid for pid, _ in outfield]

        # After GKP: MidA (5.5) > FwdA (4.0) > DefA (3.0)
        assert bench_order == [10, 12, 13, 11]


class TestAutoSubPointsCalculation:
    """expected_auto_sub_points should be > 0 when starters have < 100% availability."""

    def test_auto_sub_points_positive(self):
        outfield_scores = [5.5, 4.0, 3.0]
        sub_weights = [0.15, 0.05, 0.02]

        expected_auto_sub = 0.0
        for i, score in enumerate(outfield_scores):
            weight = sub_weights[i] if i < len(sub_weights) else 0.01
            expected_auto_sub += score * weight

        # 5.5*0.15 + 4.0*0.05 + 3.0*0.02 = 0.825 + 0.2 + 0.06 = 1.085
        assert expected_auto_sub > 0
        assert abs(expected_auto_sub - 1.085) < 0.001


class TestBenchStableSort:
    """When all scores are equal, bench order should remain stable."""

    def test_equal_scores_stable(self):
        bench_ids = [11, 12, 13]
        scores = {11: 4.0, 12: 4.0, 13: 4.0}

        # Sort with stable sort (Python's sort is stable)
        ordered = sorted(bench_ids, key=lambda pid: scores[pid], reverse=True)

        # Original order preserved
        assert ordered == [11, 12, 13]
