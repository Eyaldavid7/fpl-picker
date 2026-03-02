"""Comprehensive tests for the FPL prediction engine.

Tests cover:
1. Each individual model with synthetic history data
2. Ensemble combination logic
3. PredictionEngine orchestration
4. API endpoints returning 200
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Shared synthetic data
# ---------------------------------------------------------------------------

SYNTHETIC_HISTORY: list[float] = [2, 4, 6, 8, 10, 6, 3, 7, 5, 8]

# Shorter histories for edge-case testing
SINGLE_POINT: list[float] = [5.0]
EMPTY_HISTORY: list[float] = []
TWO_POINTS: list[float] = [3.0, 7.0]
CONSTANT_HISTORY: list[float] = [5.0, 5.0, 5.0, 5.0, 5.0]


# ===================================================================
# 1. Weighted Average Predictor
# ===================================================================

class TestWeightedAveragePredictor:
    """Tests for the recency-weighted average predictor."""

    def test_basic_prediction(self):
        from app.prediction.weighted_average import WeightedAveragePredictor

        model = WeightedAveragePredictor()
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] > 0
        # Weighted average of [2,4,6,8,10,6,3,7,5,8] with linear weights
        # More recent values (right side) should pull prediction upward
        # compared to a simple average of 5.9
        assert isinstance(preds[0], float)

    def test_multi_step_prediction(self):
        from app.prediction.weighted_average import WeightedAveragePredictor

        model = WeightedAveragePredictor()
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=3)

        assert len(preds) == 3
        # Flat forecast: all steps should be identical
        assert preds[0] == preds[1] == preds[2]

    def test_with_window(self):
        from app.prediction.weighted_average import WeightedAveragePredictor

        model = WeightedAveragePredictor(window=3)
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=1)

        # Uses only last 3 values: [7, 5, 8]
        # Weights: w1=1, w2=2, w3=3, sum=6
        # WA = (1*7 + 2*5 + 3*8) / 6 = (7 + 10 + 24) / 6 = 41/6 ~ 6.8333
        assert len(preds) == 1
        assert abs(preds[0] - 6.8333) < 0.01

    def test_empty_history(self):
        from app.prediction.weighted_average import WeightedAveragePredictor

        model = WeightedAveragePredictor()
        preds = model.predict(EMPTY_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] == 0.0

    def test_single_point(self):
        from app.prediction.weighted_average import WeightedAveragePredictor

        model = WeightedAveragePredictor()
        preds = model.predict(SINGLE_POINT, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] == 5.0

    def test_name_property(self):
        from app.prediction.weighted_average import WeightedAveragePredictor

        model = WeightedAveragePredictor()
        assert model.name == "weighted_avg"


# ===================================================================
# 2. ARIMA Predictor
# ===================================================================

class TestARIMAPredictor:
    """Tests for the ARIMA(1,0,0) predictor."""

    def test_basic_prediction(self):
        from app.prediction.arima_model import ARIMAPredictor

        model = ARIMAPredictor()
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] > 0

    def test_multi_step_forecast(self):
        from app.prediction.arima_model import ARIMAPredictor

        model = ARIMAPredictor()
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=3)

        assert len(preds) == 3
        for p in preds:
            assert isinstance(p, float)

    def test_short_history_uses_fallback(self):
        from app.prediction.arima_model import ARIMAPredictor

        model = ARIMAPredictor()
        preds = model.predict(TWO_POINTS, n_ahead=1)

        # Should fallback to weighted average
        assert len(preds) == 1
        assert preds[0] > 0

    def test_empty_history(self):
        from app.prediction.arima_model import ARIMAPredictor

        model = ARIMAPredictor()
        preds = model.predict(EMPTY_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] == 0.0

    def test_constant_history(self):
        from app.prediction.arima_model import ARIMAPredictor

        model = ARIMAPredictor()
        preds = model.predict(CONSTANT_HISTORY, n_ahead=1)

        assert len(preds) == 1
        # For a constant series, prediction should be close to that constant
        assert abs(preds[0] - 5.0) < 1.0

    def test_name_property(self):
        from app.prediction.arima_model import ARIMAPredictor

        model = ARIMAPredictor()
        assert model.name == "arima_100"


# ===================================================================
# 3. Exponential Smoothing Predictor
# ===================================================================

class TestExpSmoothingPredictor:
    """Tests for the Holt-Winters exponential smoothing predictor."""

    def test_basic_prediction(self):
        from app.prediction.exp_smoothing import ExpSmoothingPredictor

        model = ExpSmoothingPredictor()
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] > 0

    def test_multi_step_forecast(self):
        from app.prediction.exp_smoothing import ExpSmoothingPredictor

        model = ExpSmoothingPredictor()
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=3)

        assert len(preds) == 3
        for p in preds:
            assert isinstance(p, float)

    def test_short_history_no_trend(self):
        from app.prediction.exp_smoothing import ExpSmoothingPredictor

        model = ExpSmoothingPredictor()
        preds = model.predict(TWO_POINTS, n_ahead=1)

        # With only 2 points, should use SES (no trend)
        assert len(preds) == 1
        assert preds[0] > 0

    def test_empty_history(self):
        from app.prediction.exp_smoothing import ExpSmoothingPredictor

        model = ExpSmoothingPredictor()
        preds = model.predict(EMPTY_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] == 0.0

    def test_single_point_returns_zero(self):
        from app.prediction.exp_smoothing import ExpSmoothingPredictor

        model = ExpSmoothingPredictor()
        preds = model.predict(SINGLE_POINT, n_ahead=1)

        # Single point is below the _MIN_OBS=2 threshold
        assert len(preds) == 1
        assert preds[0] == 0.0

    def test_name_property(self):
        from app.prediction.exp_smoothing import ExpSmoothingPredictor

        model = ExpSmoothingPredictor()
        assert model.name == "exp_smoothing"


# ===================================================================
# 4. Monte Carlo Predictor
# ===================================================================

class TestMonteCarloPredictor:
    """Tests for the Monte Carlo simulation predictor."""

    def test_basic_prediction(self):
        from app.prediction.monte_carlo import MonteCarloPredictor

        model = MonteCarloPredictor(seed=42)
        preds = model.predict(SYNTHETIC_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] > 0

    def test_simulation_returns_confidence_intervals(self):
        from app.prediction.monte_carlo import MonteCarloPredictor

        model = MonteCarloPredictor(seed=42)
        result = model.simulate(SYNTHETIC_HISTORY)

        assert result.mean > 0
        assert result.ci_lower <= result.mean <= result.ci_upper
        assert result.simulations == 1000

    def test_constant_history_zero_ci_width(self):
        from app.prediction.monte_carlo import MonteCarloPredictor

        model = MonteCarloPredictor(seed=42)
        result = model.simulate(CONSTANT_HISTORY)

        assert result.mean == 5.0
        assert result.ci_lower == 5.0
        assert result.ci_upper == 5.0
        assert result.std == 0.0

    def test_empty_history(self):
        from app.prediction.monte_carlo import MonteCarloPredictor

        model = MonteCarloPredictor()
        preds = model.predict(EMPTY_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] == 0.0

    def test_short_history(self):
        from app.prediction.monte_carlo import MonteCarloPredictor

        model = MonteCarloPredictor()
        preds = model.predict(TWO_POINTS, n_ahead=1)

        # 2 points < _MIN_OBS=3, should return zeros
        assert preds[0] == 0.0

    def test_name_property(self):
        from app.prediction.monte_carlo import MonteCarloPredictor

        model = MonteCarloPredictor()
        assert model.name == "monte_carlo"


# ===================================================================
# 5. Hybrid ML Predictor
# ===================================================================

class TestHybridMLPredictor:
    """Tests for the Ridge + XGBoost hybrid predictor."""

    def _make_training_data(self):
        """Create simple synthetic training data."""
        import numpy as np

        np.random.seed(42)
        n_samples = 50
        n_features = 8
        X = np.random.rand(n_samples, n_features).tolist()
        # Target: roughly correlated with feature sum
        y = [sum(row) + np.random.normal(0, 0.5) for row in X]
        return X, y

    def test_fit_and_predict(self):
        from app.prediction.hybrid_ml import HybridMLPredictor

        model = HybridMLPredictor()
        X_train, y_train = self._make_training_data()
        model.fit(X_train, y_train)
        preds = model.predict(X_train[:5])

        assert len(preds) == 5
        for p in preds:
            assert isinstance(p, float)

    def test_predict_single(self):
        from app.prediction.hybrid_ml import HybridMLPredictor

        model = HybridMLPredictor()
        X_train, y_train = self._make_training_data()
        model.fit(X_train, y_train)
        pred = model.predict_single(X_train[0])

        assert isinstance(pred, float)

    def test_unfitted_returns_zeros(self):
        from app.prediction.hybrid_ml import HybridMLPredictor

        model = HybridMLPredictor()
        preds = model.predict([[1.0] * 8, [2.0] * 8])

        assert preds == [0.0, 0.0]

    def test_blend_weights(self):
        from app.prediction.hybrid_ml import HybridMLPredictor

        # Pure Ridge
        model_ridge = HybridMLPredictor(lambda_=0.0)
        X_train, y_train = self._make_training_data()
        model_ridge.fit(X_train, y_train)
        ridge_preds = model_ridge.predict(X_train[:3])

        # Pure XGBoost
        model_xgb = HybridMLPredictor(lambda_=1.0)
        model_xgb.fit(X_train, y_train)
        xgb_preds = model_xgb.predict(X_train[:3])

        # Default blend (2/3 XGBoost)
        model_blend = HybridMLPredictor()
        model_blend.fit(X_train, y_train)
        blend_preds = model_blend.predict(X_train[:3])

        # Blend should be between Ridge and XGBoost (or close)
        for i in range(3):
            lo = min(ridge_preds[i], xgb_preds[i])
            hi = max(ridge_preds[i], xgb_preds[i])
            # Allow some floating-point tolerance
            assert lo - 0.1 <= blend_preds[i] <= hi + 0.1

    def test_feature_names(self):
        from app.prediction.hybrid_ml import HybridMLPredictor, HYBRID_FEATURES

        model = HybridMLPredictor()
        assert model.feature_names == HYBRID_FEATURES
        assert len(model.feature_names) == 8

    def test_name_property(self):
        from app.prediction.hybrid_ml import HybridMLPredictor

        model = HybridMLPredictor()
        assert model.name == "hybrid_ml"


# ===================================================================
# 6. Ensemble Combiner
# ===================================================================

class TestEnsemblePredictor:
    """Tests for the ensemble combiner."""

    def _build_ensemble(self):
        from app.prediction.arima_model import ARIMAPredictor
        from app.prediction.ensemble import EnsemblePredictor
        from app.prediction.exp_smoothing import ExpSmoothingPredictor
        from app.prediction.monte_carlo import MonteCarloPredictor
        from app.prediction.weighted_average import WeightedAveragePredictor

        ensemble = EnsemblePredictor()
        ensemble.register_ts_model(ARIMAPredictor())
        ensemble.register_ts_model(WeightedAveragePredictor())
        ensemble.register_ts_model(ExpSmoothingPredictor())
        ensemble.register_ts_model(MonteCarloPredictor(seed=42))
        return ensemble

    def test_ensemble_produces_prediction(self):
        ensemble = self._build_ensemble()
        preds = ensemble.predict(SYNTHETIC_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] > 0

    def test_ensemble_multi_step(self):
        ensemble = self._build_ensemble()
        preds = ensemble.predict(SYNTHETIC_HISTORY, n_ahead=3)

        assert len(preds) == 3

    def test_get_all_predictions_returns_all_models(self):
        ensemble = self._build_ensemble()
        breakdown = ensemble.get_all_predictions(SYNTHETIC_HISTORY, n_ahead=1)

        assert "arima_100" in breakdown
        assert "weighted_avg" in breakdown
        assert "exp_smoothing" in breakdown
        assert "monte_carlo" in breakdown

        for name, vals in breakdown.items():
            assert len(vals) == 1
            assert isinstance(vals[0], float)

    def test_custom_weights(self):
        from app.prediction.ensemble import EnsemblePredictor
        from app.prediction.weighted_average import WeightedAveragePredictor
        from app.prediction.monte_carlo import MonteCarloPredictor

        # Give all weight to weighted_avg
        ensemble = EnsemblePredictor(weights={"weighted_avg": 1.0, "monte_carlo": 0.0})
        ensemble.register_ts_model(WeightedAveragePredictor())
        ensemble.register_ts_model(MonteCarloPredictor(seed=42))

        ensemble_pred = ensemble.predict(SYNTHETIC_HISTORY, n_ahead=1)
        wa_pred = WeightedAveragePredictor().predict(SYNTHETIC_HISTORY, n_ahead=1)

        # Ensemble should equal the weighted average when it gets all the weight
        assert abs(ensemble_pred[0] - wa_pred[0]) < 0.01

    def test_empty_history(self):
        ensemble = self._build_ensemble()
        preds = ensemble.predict(EMPTY_HISTORY, n_ahead=1)

        assert len(preds) == 1
        assert preds[0] == 0.0

    def test_model_info(self):
        ensemble = self._build_ensemble()
        info = ensemble.model_info()

        assert len(info) == 4
        names = {m["name"] for m in info}
        assert "arima_100" in names
        assert "weighted_avg" in names

    def test_model_names(self):
        ensemble = self._build_ensemble()
        names = ensemble.model_names

        assert len(names) == 4
        assert "arima_100" in names


# ===================================================================
# 7. Prediction Engine
# ===================================================================

class TestPredictionEngine:
    """Tests for the PredictionEngine facade."""

    def test_engine_creates_with_all_models(self):
        from app.prediction.engine import PredictionEngine

        engine = PredictionEngine()
        models = engine.available_models()

        # Should have 4 TS models + 1 ML model = 5
        assert len(models) == 5
        names = {m["name"] for m in models}
        assert "arima_100" in names
        assert "weighted_avg" in names
        assert "exp_smoothing" in names
        assert "monte_carlo" in names
        assert "hybrid_ml" in names

    def test_cache_clear(self):
        from app.prediction.engine import PredictionEngine

        engine = PredictionEngine()
        assert engine.clear_cache() == 0

    def test_fit_ml_model(self):
        import numpy as np
        from app.prediction.engine import PredictionEngine

        engine = PredictionEngine()
        np.random.seed(42)
        X = np.random.rand(30, 8).tolist()
        y = [sum(row) for row in X]
        engine.fit_ml_model(X, y)

        assert engine._ml_fitted is True


# ===================================================================
# 8. API Endpoint Tests
# ===================================================================

@pytest.fixture
def anyio_backend():
    return "asyncio"


def _mock_fpl_client():
    """Create a mock FPL client that returns synthetic data."""
    mock_client = AsyncMock()
    mock_client.get_current_gameweek.return_value = 27

    # Mock player history
    mock_history = []
    for i, pts in enumerate(SYNTHETIC_HISTORY):
        record = MagicMock()
        record.total_points = pts
        mock_history.append(record)

    mock_client.get_player_history.return_value = mock_history

    # Mock player
    mock_player = MagicMock()
    mock_player.id = 1
    mock_player.ict_index = 50.0
    mock_player.expected_goal_involvements = 3.0
    mock_player.expected_goals = 2.0
    mock_player.expected_assists = 1.0
    mock_player.form = 5.0
    mock_player.minutes = 900
    mock_player.bps = 100
    mock_player.selected_by_percent = 15.0
    mock_client.get_player_by_id.return_value = mock_player

    # Mock players list
    mock_client.get_players.return_value = [mock_player]

    return mock_client


@pytest.mark.anyio
async def test_predict_models_endpoint():
    """Test GET /api/predict/models returns 200 with model list."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/predict/models")

    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) > 0

    names = {m["name"] for m in data["models"]}
    assert "arima_100" in names
    assert "weighted_avg" in names


@pytest.mark.anyio
async def test_predict_points_endpoint():
    """Test POST /api/predict/points returns 200."""
    from app.main import app

    mock_client = _mock_fpl_client()

    with patch("app.data.fpl_client.get_fpl_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/predict/points",
                json={
                    "player_ids": [1],
                    "gameweeks": [28],
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert "predictions" in data
    assert data["model"] == "ensemble"


@pytest.mark.anyio
async def test_predict_player_endpoint():
    """Test GET /api/predict/players/{player_id} returns 200."""
    from app.main import app

    mock_client = _mock_fpl_client()

    with patch(
        "app.data.fpl_client.get_fpl_client", return_value=mock_client
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/predict/players/1")

    assert response.status_code == 200
    data = response.json()
    assert data["player_id"] == 1
    assert "ensemble_prediction" in data
    assert "model_breakdown" in data


@pytest.mark.anyio
async def test_compare_models_endpoint():
    """Test POST /api/predict/compare returns 200."""
    from app.main import app

    mock_client = _mock_fpl_client()

    with patch("app.data.fpl_client.get_fpl_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/predict/compare",
                json={
                    "player_ids": [1],
                    "gameweek": 28,
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert "comparisons" in data
    assert data["gameweek"] == 28


# ===================================================================
# 9. Base class edge case tests
# ===================================================================

class TestBasePredictor:
    """Test base class helper methods."""

    def test_safe_fallback(self):
        from app.prediction.base import BasePredictor

        result = BasePredictor._safe_fallback(3)
        assert result == [0.0, 0.0, 0.0]

    def test_safe_fallback_with_fill(self):
        from app.prediction.base import BasePredictor

        result = BasePredictor._safe_fallback(2, fill=5.0)
        assert result == [5.0, 5.0]

    def test_validate_history(self):
        from app.prediction.base import BasePredictor

        assert BasePredictor._validate_history([1, 2, 3], min_length=3) is True
        assert BasePredictor._validate_history([1, 2], min_length=3) is False
        assert BasePredictor._validate_history([], min_length=1) is False
