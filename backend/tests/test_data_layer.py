"""Comprehensive tests for the FPL data layer.

Covers:
- FileCache: get/set/TTL expiry/invalidation/cleanup/stats
- Pydantic model validation: Player, Team, Fixture, Gameweek, PlayerHistory
- Preprocessing helpers: calculate_derived_features, handle_missing_data,
  normalize_features, get_feature_matrix
- DataPipeline: build_player_features, create_target, handle_missing_data,
  normalize_features
- Data API endpoints (mocked FPL client): /api/data/players, /api/data/teams,
  /api/data/fixtures, /api/data/gameweeks/current, /api/data/refresh
- FPLClient: singleton accessor, endpoint helpers
- historical_loader: _download_csv, load_season, clear_historical_cache
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.data.models import (
    Fixture,
    Gameweek,
    Player,
    PlayerHistory,
    Position,
    POSITION_MAP,
    Team,
)
from app.data.preprocessing import (
    DataPipeline,
    ML_FEATURES,
    calculate_derived_features,
    calculate_fixture_difficulty_weighted_points,
    handle_missing_data,
    normalize_features,
    get_feature_matrix,
)


# ======================================================================
# FileCache tests
# ======================================================================


class TestFileCache:
    """Tests for the file-based cache with TTL support."""

    def _make_cache(self, tmpdir: str):
        """Create a FileCache pointing at a temporary directory."""
        from app.data.cache import FileCache
        with patch("app.data.cache.get_settings") as mock_settings:
            settings = MagicMock()
            settings.cache_dir = tmpdir
            settings.cache_bootstrap_ttl = 3600
            settings.cache_element_ttl = 7200
            settings.cache_fixtures_ttl = 86400
            settings.cache_live_ttl = 60
            mock_settings.return_value = settings
            return FileCache(cache_dir=tmpdir)

    def test_set_and_get(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        cache.set("test_key", {"foo": "bar"}, ttl=3600)
        result = cache.get("test_key")
        assert result == {"foo": "bar"}

    def test_get_missing_key_returns_none(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        # Set with TTL of 1 second
        cache.set("expiring", "value", ttl=1)
        assert cache.get("expiring") == "value"

        # Manually expire the entry by modifying the file
        path = cache._key_to_path("expiring")
        with open(path, "r") as f:
            entry = json.load(f)
        entry["expires_at"] = time.time() - 10  # expired 10 seconds ago
        with open(path, "w") as f:
            json.dump(entry, f)

        assert cache.get("expiring") is None

    def test_ttl_zero_never_expires(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        cache.set("permanent", "data", ttl=0)
        result = cache.get("permanent")
        assert result == "data"

    def test_invalidate_existing_key(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        cache.set("to_remove", "value", ttl=3600)
        assert cache.invalidate("to_remove") is True
        assert cache.get("to_remove") is None

    def test_invalidate_missing_key(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        assert cache.invalidate("does_not_exist") is False

    def test_invalidate_all(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        cache.set("a", 1, ttl=3600)
        cache.set("b", 2, ttl=3600)
        cache.set("c", 3, ttl=3600)
        count = cache.invalidate_all()
        assert count == 3
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_cleanup_expired(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        cache.set("fresh", "ok", ttl=3600)
        cache.set("stale", "old", ttl=1)

        # Manually expire "stale"
        path = cache._key_to_path("stale")
        with open(path, "r") as f:
            entry = json.load(f)
        entry["expires_at"] = time.time() - 10
        with open(path, "w") as f:
            json.dump(entry, f)

        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.get("fresh") == "ok"
        assert cache.get("stale") is None

    def test_stats(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        cache.set("key1", "val1", ttl=3600)
        cache.set("key2", "val2", ttl=3600)
        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0
        assert stats["total_size_bytes"] > 0
        assert str(tmp_path) in stats["cache_dir"]

    def test_ttl_for_known_category(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        assert cache.ttl_for("live") == 60

    def test_ttl_for_unknown_category(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        assert cache.ttl_for("completely_unknown") == 3600

    def test_key_to_path_sanitises_special_chars(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        path = cache._key_to_path("foo/bar:baz?qux")
        assert "/" not in path.name.replace(".json", "")
        assert ":" not in path.name
        assert "?" not in path.name

    def test_corrupt_json_returns_none(self, tmp_path):
        cache = self._make_cache(str(tmp_path))
        path = cache._key_to_path("corrupt")
        path.write_text("not valid json{{{{", encoding="utf-8")
        assert cache.get("corrupt") is None


# ======================================================================
# Pydantic model tests
# ======================================================================


class TestPlayerModel:
    """Tests for the Player Pydantic model."""

    def _make_api_element(self, **overrides) -> dict:
        base = {
            "id": 100,
            "web_name": "TestPlayer",
            "first_name": "Test",
            "second_name": "Player",
            "team": 5,
            "element_type": 3,
            "now_cost": 80,
            "total_points": 120,
            "form": "6.5",
            "points_per_game": "5.2",
            "minutes": 1800,
            "goals_scored": 8,
            "assists": 4,
            "clean_sheets": 0,
            "bonus": 12,
            "bps": 200,
            "ict_index": "105.3",
            "influence": "50.0",
            "creativity": "30.0",
            "threat": "25.3",
            "expected_goals": "5.5",
            "expected_assists": "3.2",
            "expected_goal_involvements": "8.7",
            "expected_goals_conceded": "0.0",
            "selected_by_percent": "15.0",
            "news": "",
            "chance_of_playing_next_round": 100,
            "transfers_in_event": 500,
            "transfers_out_event": 200,
            "value_season": "12.0",
            "status": "a",
        }
        base.update(overrides)
        return base

    def test_from_api_element_valid(self):
        el = self._make_api_element()
        player = Player.from_api_element(el)
        assert player.id == 100
        assert player.web_name == "TestPlayer"
        assert player.team == 5
        assert player.position == Position.MID  # element_type=3

    def test_position_derived_from_element_type(self):
        for et, expected_pos in POSITION_MAP.items():
            player = Player.from_api_element(
                self._make_api_element(element_type=et)
            )
            assert player.position == expected_pos

    def test_string_floats_coerced(self):
        player = Player.from_api_element(
            self._make_api_element(form="7.3", ict_index="99.9")
        )
        assert player.form == 7.3
        assert player.ict_index == 99.9

    def test_none_floats_default_to_zero(self):
        player = Player.from_api_element(
            self._make_api_element(form=None, ict_index=None)
        )
        assert player.form == 0.0
        assert player.ict_index == 0.0

    def test_price_property(self):
        player = Player.from_api_element(
            self._make_api_element(now_cost=80)
        )
        assert player.price == 8.0

    def test_missing_id_raises(self):
        el = self._make_api_element()
        del el["id"]
        with pytest.raises((ValidationError, KeyError)):
            Player.from_api_element(el)

    def test_defaults_when_minimal_data(self):
        player = Player(id=1, web_name="Min", team=1)
        assert player.total_points == 0
        assert player.minutes == 0
        assert player.form == 0.0


class TestPlayerHistoryModel:
    """Tests for the PlayerHistory Pydantic model."""

    def _make_api_history(self, **overrides) -> dict:
        base = {
            "round": 10,
            "total_points": 8,
            "minutes": 90,
            "goals_scored": 1,
            "assists": 1,
            "clean_sheets": 0,
            "bonus": 2,
            "bps": 35,
            "ict_index": "12.5",
            "influence": "5.0",
            "creativity": "4.0",
            "threat": "3.5",
            "expected_goals": "0.5",
            "expected_assists": "0.3",
            "expected_goal_involvements": "0.8",
            "expected_goals_conceded": "1.2",
            "value": 80,
            "opponent_team": 3,
            "was_home": True,
            "fixture": 55,
        }
        base.update(overrides)
        return base

    def test_from_api_history_valid(self):
        h = self._make_api_history()
        ph = PlayerHistory.from_api_history(h)
        assert ph.round == 10
        assert ph.total_points == 8
        assert ph.was_home is True

    def test_string_float_coercion(self):
        ph = PlayerHistory.from_api_history(
            self._make_api_history(ict_index="99.9")
        )
        assert ph.ict_index == 99.9

    def test_none_float_coercion(self):
        ph = PlayerHistory.from_api_history(
            self._make_api_history(ict_index=None, expected_goals=None)
        )
        assert ph.ict_index == 0.0
        assert ph.expected_goals == 0.0

    def test_defaults_on_minimal(self):
        ph = PlayerHistory(round=1)
        assert ph.total_points == 0
        assert ph.minutes == 0


class TestTeamModel:
    """Tests for the Team Pydantic model."""

    def test_from_api_team(self):
        team_data = {
            "id": 1,
            "name": "Arsenal",
            "short_name": "ARS",
            "strength": 5,
            "strength_overall_home": 1350,
            "strength_overall_away": 1300,
            "strength_attack_home": 1400,
            "strength_attack_away": 1350,
            "strength_defence_home": 1300,
            "strength_defence_away": 1250,
        }
        team = Team.from_api_team(team_data)
        assert team.id == 1
        assert team.name == "Arsenal"
        assert team.short_name == "ARS"
        assert team.strength == 5

    def test_defaults(self):
        team = Team(id=1, name="Test", short_name="TST")
        assert team.strength == 0
        assert team.strength_attack_home == 0


class TestFixtureModel:
    """Tests for the Fixture Pydantic model."""

    def test_from_api_fixture(self):
        fix = {
            "id": 10,
            "event": 28,
            "team_h": 1,
            "team_a": 5,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
            "kickoff_time": "2025-03-15T15:00:00Z",
            "finished": False,
            "team_h_score": None,
            "team_a_score": None,
        }
        fixture = Fixture.from_api_fixture(fix)
        assert fixture.id == 10
        assert fixture.event == 28
        assert fixture.team_h == 1
        assert fixture.finished is False

    def test_defaults(self):
        fixture = Fixture(id=1, team_h=1, team_a=2)
        assert fixture.event is None
        assert fixture.team_h_difficulty == 3
        assert fixture.finished is False


class TestGameweekModel:
    """Tests for the Gameweek Pydantic model."""

    def test_from_api_event(self):
        ev = {
            "id": 28,
            "name": "Gameweek 28",
            "deadline_time": "2025-03-15T11:30:00Z",
            "finished": False,
            "is_current": True,
            "is_next": False,
            "is_previous": False,
            "average_entry_score": 52,
            "highest_score": 120,
            "most_captained": 233,
            "most_vice_captained": 128,
        }
        gw = Gameweek.from_api_event(ev)
        assert gw.id == 28
        assert gw.is_current is True
        assert gw.average_score == 52

    def test_defaults(self):
        gw = Gameweek(id=1)
        assert gw.finished is False
        assert gw.is_current is False
        assert gw.average_score == 0


# ======================================================================
# Preprocessing tests
# ======================================================================


class TestCalculateDerivedFeatures:
    """Tests for calculate_derived_features."""

    def _make_player(self, **kwargs) -> Player:
        defaults = {
            "id": 1,
            "web_name": "Test",
            "team": 1,
            "element_type": 3,
            "now_cost": 80,
            "total_points": 120,
            "minutes": 1800,
            "expected_goal_involvements": 8.0,
        }
        defaults.update(kwargs)
        return Player(**defaults)

    def test_points_per_million(self):
        player = self._make_player(total_points=120, now_cost=80)
        result = calculate_derived_features(player)
        assert result.points_per_million == round(120 / 8.0, 2)

    def test_xgi_per_90(self):
        player = self._make_player(
            expected_goal_involvements=9.0, minutes=900
        )
        result = calculate_derived_features(player)
        assert result.xgi_per_90 == round(9.0 / 900 * 90, 3)

    def test_zero_minutes_xgi(self):
        player = self._make_player(minutes=0)
        result = calculate_derived_features(player)
        assert result.xgi_per_90 == 0.0

    def test_zero_cost_ppm(self):
        player = self._make_player(now_cost=0)
        result = calculate_derived_features(player)
        assert result.points_per_million == 0.0

    def test_form_from_history(self):
        player = self._make_player()
        history = [
            PlayerHistory(round=i, total_points=pts)
            for i, pts in enumerate([3, 5, 7, 9, 11, 2, 4], start=1)
        ]
        result = calculate_derived_features(player, history)
        # Last 5 by round (sorted desc): round 7=4, 6=2, 5=11, 4=9, 3=7
        expected_form = round((4 + 2 + 11 + 9 + 7) / 5, 1)
        assert result.form == expected_form


class TestCalculateFixtureDifficultyWeightedPoints:
    """Tests for fixture difficulty weighted points."""

    def test_empty_history(self):
        assert calculate_fixture_difficulty_weighted_points([]) == 0.0

    def test_default_difficulty(self):
        history = [PlayerHistory(round=1, total_points=6, fixture=1)]
        result = calculate_fixture_difficulty_weighted_points(history)
        # With default difficulty 3, weight = 3/3 = 1.0 -> result = 6.0
        assert result == 6.0

    def test_custom_difficulty(self):
        history = [
            PlayerHistory(round=1, total_points=6, fixture=1),
            PlayerHistory(round=2, total_points=2, fixture=2),
        ]
        diff_map = {1: 5, 2: 1}
        result = calculate_fixture_difficulty_weighted_points(
            history, fixture_difficulty_map=diff_map
        )
        # fixture 1: 6 * (5/3) = 10.0, weight 5/3
        # fixture 2: 2 * (1/3) = 0.6667, weight 1/3
        expected = round((10.0 + 0.6667) / (5 / 3 + 1 / 3), 2)
        assert abs(result - expected) < 0.01


class TestHandleMissingData:
    """Tests for handle_missing_data."""

    def test_zero_minutes_filled(self):
        player = Player(id=1, web_name="Zero", team=1, element_type=4, minutes=0)
        results = handle_missing_data([player])
        # FWD defaults: expected_goals=6.0
        assert results[0].expected_goals == 6.0

    def test_nonzero_minutes_not_filled(self):
        player = Player(
            id=1, web_name="Active", team=1, element_type=4,
            minutes=900, expected_goals=0.0,
        )
        results = handle_missing_data([player])
        assert results[0].expected_goals == 0.0  # Not overwritten

    def test_multiple_players(self):
        players = [
            Player(id=1, web_name="A", team=1, element_type=1, minutes=0),
            Player(id=2, web_name="B", team=1, element_type=2, minutes=0),
        ]
        results = handle_missing_data(players)
        # GKP defaults
        assert results[0].expected_goals == 0.0
        assert results[0].expected_goals_conceded == 30.0
        # DEF defaults
        assert results[1].expected_goals == 1.0


class TestNormalizeFeatures:
    """Tests for normalize_features."""

    def test_basic_normalization(self):
        players = [
            Player(id=1, web_name="A", team=1, ict_index=0.0, minutes=0),
            Player(id=2, web_name="B", team=1, ict_index=100.0, minutes=1800),
            Player(id=3, web_name="C", team=1, ict_index=50.0, minutes=900),
        ]
        result = normalize_features(players, features=["ict_index", "minutes"])
        assert len(result) == 3
        # Player B should be 1.0 for both features
        assert result[1]["ict_index"] == 1.0
        assert result[1]["minutes"] == 1.0
        # Player A should be 0.0
        assert result[0]["ict_index"] == 0.0
        # Player C should be 0.5 for ict_index
        assert abs(result[2]["ict_index"] - 0.5) < 0.01

    def test_constant_feature_returns_zero(self):
        players = [
            Player(id=1, web_name="A", team=1, ict_index=5.0),
            Player(id=2, web_name="B", team=1, ict_index=5.0),
        ]
        result = normalize_features(players, features=["ict_index"])
        assert result[0]["ict_index"] == 0.0
        assert result[1]["ict_index"] == 0.0

    def test_single_player(self):
        players = [Player(id=1, web_name="A", team=1, ict_index=50.0)]
        result = normalize_features(players, features=["ict_index"])
        assert result[0]["ict_index"] == 0.0  # max == min


class TestGetFeatureMatrix:
    """Tests for get_feature_matrix."""

    def test_shape(self):
        players = [
            Player(id=1, web_name="A", team=1),
            Player(id=2, web_name="B", team=1),
        ]
        matrix = get_feature_matrix(players)
        assert matrix.shape == (2, len(ML_FEATURES))

    def test_values_populated(self):
        player = Player(
            id=1, web_name="A", team=1,
            ict_index=50.0, minutes=900, form=6.0, bps=100,
        )
        matrix = get_feature_matrix([player])
        assert matrix.shape == (1, len(ML_FEATURES))
        # ict_index is the first feature
        assert matrix[0, ML_FEATURES.index("ict_index")] == 50.0
        assert matrix[0, ML_FEATURES.index("minutes")] == 900

    def test_custom_features(self):
        player = Player(id=1, web_name="A", team=1, ict_index=10.0, form=5.0)
        matrix = get_feature_matrix([player], features=["ict_index", "form"])
        assert matrix.shape == (1, 2)
        assert matrix[0, 0] == 10.0
        assert matrix[0, 1] == 5.0

    def test_empty_players(self):
        matrix = get_feature_matrix([])
        assert matrix.shape == (0, len(ML_FEATURES))


# ======================================================================
# DataPipeline tests
# ======================================================================


class TestDataPipeline:
    """Tests for the DataPipeline class."""

    def setup_method(self):
        self.pipeline = DataPipeline()

    def _make_raw_data(self, n=20):
        """Create synthetic per-GW player data."""
        np.random.seed(42)
        data = {
            "element": list(range(1, n + 1)),
            "minutes": np.random.randint(0, 90, n),
            "goals_scored": np.random.randint(0, 3, n),
            "assists": np.random.randint(0, 2, n),
            "clean_sheets": np.random.randint(0, 2, n),
            "bonus": np.random.randint(0, 4, n),
            "bps": np.random.randint(0, 50, n),
            "total_points": np.random.randint(0, 15, n),
            "ict_index": np.random.uniform(0, 20, n).round(1),
            "influence": np.random.uniform(0, 10, n).round(1),
            "creativity": np.random.uniform(0, 10, n).round(1),
            "threat": np.random.uniform(0, 10, n).round(1),
            "expected_goals": np.random.uniform(0, 1, n).round(2),
            "expected_assists": np.random.uniform(0, 0.5, n).round(2),
            "expected_goal_involvements": np.random.uniform(0, 1.5, n).round(2),
            "expected_goals_conceded": np.random.uniform(0, 2, n).round(2),
            "value": np.random.randint(40, 130, n),
        }
        return pd.DataFrame(data)

    def test_build_player_features_adds_columns(self):
        raw = self._make_raw_data()
        result = self.pipeline.build_player_features(raw)
        # Should have added rolling features and derived columns
        assert "pts_rolling_3" in result.columns
        assert "pts_rolling_5" in result.columns
        assert "pts_rolling_10" in result.columns
        assert "minutes_ratio" in result.columns
        assert "points_per_million" in result.columns
        assert "xgi_per_90" in result.columns

    def test_build_preserves_original_columns(self):
        raw = self._make_raw_data()
        result = self.pipeline.build_player_features(raw)
        assert "total_points" in result.columns
        assert "minutes" in result.columns

    def test_create_target_shift(self):
        df = pd.DataFrame({"total_points": [2, 4, 6, 8, 10]})
        target = self.pipeline.create_target(df, horizon=1)
        # Shifted by 1: [4, 6, 8, 10, NaN]
        assert target.iloc[0] == 4
        assert target.iloc[3] == 10
        assert pd.isna(target.iloc[4])

    def test_create_target_horizon_2(self):
        df = pd.DataFrame({"total_points": [2, 4, 6, 8, 10]})
        target = self.pipeline.create_target(df, horizon=2)
        assert target.iloc[0] == 6
        assert pd.isna(target.iloc[3])

    def test_handle_missing_data_fills_nan(self):
        df = pd.DataFrame({
            "total_points": [1.0, np.nan, 3.0],
            "minutes": [90, np.nan, 45],
        })
        result = self.pipeline.handle_missing_data(df)
        assert result["total_points"].isna().sum() == 0
        assert result["minutes"].isna().sum() == 0

    def test_normalize_features_range(self):
        df = pd.DataFrame({
            "feat_a": [0.0, 50.0, 100.0],
            "feat_b": [10.0, 20.0, 30.0],
        })
        result = self.pipeline.normalize_features(df, columns=["feat_a", "feat_b"])
        assert result["feat_a"].min() == 0.0
        assert result["feat_a"].max() == 1.0
        assert result["feat_b"].min() == 0.0
        assert result["feat_b"].max() == 1.0

    def test_normalize_constant_column(self):
        df = pd.DataFrame({"feat": [5.0, 5.0, 5.0]})
        result = self.pipeline.normalize_features(df, columns=["feat"])
        assert (result["feat"] == 0.0).all()

    def test_form_trend_computed(self):
        raw = self._make_raw_data(n=30)
        result = self.pipeline.build_player_features(raw)
        if "form_trend" in result.columns:
            # form_trend = pts_rolling_3 - pts_rolling_10
            assert not result["form_trend"].isna().all()


# ======================================================================
# FPLClient tests (singleton and helpers)
# ======================================================================


class TestFPLClientSingleton:
    """Tests for the FPLClient singleton accessor."""

    def test_get_fpl_client_returns_same_instance(self):
        from app.data.fpl_client import get_fpl_client

        # Clear the lru_cache to ensure a fresh start
        get_fpl_client.cache_clear()
        c1 = get_fpl_client()
        c2 = get_fpl_client()
        assert c1 is c2

    def test_client_has_base_url(self):
        from app.data.fpl_client import get_fpl_client

        get_fpl_client.cache_clear()
        client = get_fpl_client()
        assert "fantasy.premierleague.com" in client.base_url

    def test_client_has_cache(self):
        from app.data.fpl_client import get_fpl_client
        from app.data.cache import FileCache

        get_fpl_client.cache_clear()
        client = get_fpl_client()
        assert isinstance(client.cache, FileCache)

    def test_endpoints_defined(self):
        from app.data.fpl_client import FPLClient

        assert "bootstrap" in FPLClient.ENDPOINTS
        assert "fixtures" in FPLClient.ENDPOINTS
        assert "element_summary" in FPLClient.ENDPOINTS


# ======================================================================
# Data API endpoint tests (mocked FPL client)
# ======================================================================


def _mock_bootstrap():
    """Return a mock bootstrap-static response."""
    return {
        "elements": [
            {
                "id": 1,
                "web_name": "Saka",
                "first_name": "Bukayo",
                "second_name": "Saka",
                "team": 1,
                "element_type": 3,
                "now_cost": 100,
                "total_points": 150,
                "form": "7.0",
                "points_per_game": "6.0",
                "minutes": 2000,
                "goals_scored": 10,
                "assists": 8,
                "clean_sheets": 0,
                "bonus": 15,
                "bps": 300,
                "ict_index": "200.0",
                "influence": "100.0",
                "creativity": "60.0",
                "threat": "40.0",
                "expected_goals": "8.0",
                "expected_assists": "5.0",
                "expected_goal_involvements": "13.0",
                "expected_goals_conceded": "0.0",
                "selected_by_percent": "35.0",
                "news": "",
                "chance_of_playing_next_round": 100,
                "transfers_in_event": 1000,
                "transfers_out_event": 200,
                "value_season": "15.0",
                "status": "a",
            },
        ],
        "teams": [
            {
                "id": 1,
                "name": "Arsenal",
                "short_name": "ARS",
                "strength": 5,
                "strength_overall_home": 1350,
                "strength_overall_away": 1300,
                "strength_attack_home": 1400,
                "strength_attack_away": 1350,
                "strength_defence_home": 1300,
                "strength_defence_away": 1250,
            },
        ],
        "events": [
            {
                "id": 28,
                "name": "Gameweek 28",
                "deadline_time": "2025-03-15T11:30:00Z",
                "finished": False,
                "is_current": True,
                "is_next": False,
                "is_previous": False,
                "average_entry_score": 52,
                "highest_score": 120,
                "most_captained": 1,
                "most_vice_captained": 2,
            },
        ],
    }


def _mock_fpl_client():
    """Create a mock FPL client returning structured data."""
    mock = AsyncMock()
    bootstrap = _mock_bootstrap()

    mock.get_bootstrap.return_value = bootstrap
    mock.get_players.return_value = [
        Player.from_api_element(el) for el in bootstrap["elements"]
    ]
    mock.get_player_by_id.return_value = Player.from_api_element(
        bootstrap["elements"][0]
    )
    mock.get_player_summary.return_value = {
        "history": [
            {"round": i, "total_points": 5 + i, "minutes": 90}
            for i in range(1, 6)
        ],
        "fixtures": [],
    }
    mock.get_teams.return_value = [
        Team.from_api_team(t) for t in bootstrap["teams"]
    ]
    mock.get_teams_map.return_value = {1: "ARS"}
    mock.get_typed_fixtures.return_value = [
        Fixture(id=1, team_h=1, team_a=2, event=28),
    ]
    mock.get_gameweeks.return_value = [
        Gameweek.from_api_event(ev) for ev in bootstrap["events"]
    ]
    mock.get_current_gameweek_info.return_value = Gameweek.from_api_event(
        bootstrap["events"][0]
    )
    mock.get_current_gameweek.return_value = 28
    mock.get_live_gameweek.return_value = {"elements": []}
    mock.cache = MagicMock()
    mock.cache.invalidate_all.return_value = 1

    return mock


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class TestDataAPIEndpoints:
    """Tests for data API endpoints with mocked FPL client."""

    def test_get_players_endpoint(self, client):
        mock = _mock_fpl_client()
        with patch("app.api.endpoints.data.get_fpl_client", return_value=mock):
            response = client.get("/api/data/players")
        assert response.status_code == 200
        data = response.json()
        assert "players" in data
        assert data["total"] >= 1

    def test_get_players_filter_position(self, client):
        mock = _mock_fpl_client()
        with patch("app.api.endpoints.data.get_fpl_client", return_value=mock):
            response = client.get("/api/data/players?position=MID")
        assert response.status_code == 200

    def test_get_teams_endpoint(self, client):
        mock = _mock_fpl_client()
        with patch("app.api.endpoints.data.get_fpl_client", return_value=mock):
            response = client.get("/api/data/teams")
        assert response.status_code == 200
        data = response.json()
        assert "teams" in data
        assert len(data["teams"]) == 1

    def test_get_fixtures_endpoint(self, client):
        mock = _mock_fpl_client()
        with patch("app.api.endpoints.data.get_fpl_client", return_value=mock):
            response = client.get("/api/data/fixtures")
        assert response.status_code == 200
        data = response.json()
        assert "fixtures" in data

    def test_get_current_gameweek_endpoint(self, client):
        mock = _mock_fpl_client()
        with patch("app.api.endpoints.data.get_fpl_client", return_value=mock):
            response = client.get("/api/data/gameweeks/current")
        assert response.status_code == 200
        data = response.json()
        assert data["gameweek"]["id"] == 28

    def test_get_gameweeks_endpoint(self, client):
        mock = _mock_fpl_client()
        with patch("app.api.endpoints.data.get_fpl_client", return_value=mock):
            response = client.get("/api/data/gameweeks")
        assert response.status_code == 200
        data = response.json()
        assert "gameweeks" in data

    def test_refresh_endpoint(self, client):
        mock = _mock_fpl_client()
        with patch("app.api.endpoints.data.get_fpl_client", return_value=mock):
            response = client.post("/api/data/refresh")
        assert response.status_code == 200
        assert response.json()["status"] == "refreshed"


# ======================================================================
# Historical loader tests (mocked HTTP)
# ======================================================================


class TestHistoricalLoader:
    """Tests for historical data loader with mocked HTTP."""

    @pytest.mark.anyio
    async def test_download_csv_success(self):
        from app.data.historical_loader import _download_csv

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "name,goals,assists\nSaka,10,8\n"

        with patch("app.data.historical_loader.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await _download_csv("http://example.com/test.csv")

        assert result is not None
        assert "Saka" in result

    @pytest.mark.anyio
    async def test_download_csv_404(self):
        from app.data.historical_loader import _download_csv

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("app.data.historical_loader.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await _download_csv("http://example.com/missing.csv")

        assert result is None

    def test_clear_historical_cache(self, tmp_path):
        from app.data.historical_loader import clear_historical_cache

        with patch("app.data.historical_loader._cache_dir", return_value=tmp_path):
            # Create some fake cached files
            (tmp_path / "2024-25_gw1.csv").write_text("data", encoding="utf-8")
            (tmp_path / "2024-25_gw2.csv").write_text("data", encoding="utf-8")

            count = clear_historical_cache()
            assert count == 2


@pytest.fixture
def anyio_backend():
    return "asyncio"
