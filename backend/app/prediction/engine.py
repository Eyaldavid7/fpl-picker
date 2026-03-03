"""Prediction engine facade.

Orchestrates the full prediction pipeline for FPL players:

1. Fetch player history from the FPL API via ``FPLClient``.
2. Extract time-series (total_points per GW) and ML feature vectors.
3. Run all models through the ``EnsemblePredictor``.
4. Cache results per gameweek for fast repeated lookups.
5. Expose ``predict_player`` and ``predict_all_players`` entry points
   consumed by the API layer.
"""

from __future__ import annotations

import logging
from typing import Any

from app.prediction.arima_model import ARIMAPredictor
from app.prediction.base import PredictionResult
from app.prediction.ensemble import EnsemblePredictor
from app.prediction.exp_smoothing import ExpSmoothingPredictor
from app.prediction.hybrid_ml import HybridMLPredictor, HYBRID_FEATURES
from app.prediction.monte_carlo import MonteCarloPredictor
from app.prediction.weighted_average import WeightedAveragePredictor

logger = logging.getLogger(__name__)


class PredictionEngine:
    """High-level orchestrator for player point prediction.

    Typical usage::

        engine = PredictionEngine()
        result = await engine.predict_player(player_id=123, gameweek=28)
    """

    def __init__(self) -> None:
        # Build the ensemble with all models
        self._ensemble = EnsemblePredictor()

        # Register time-series models
        self._ensemble.register_ts_model(ARIMAPredictor())
        self._ensemble.register_ts_model(WeightedAveragePredictor())
        self._ensemble.register_ts_model(ExpSmoothingPredictor())
        self._ensemble.register_ts_model(MonteCarloPredictor())

        # The hybrid ML model starts unfitted; it will be fitted when
        # training data is supplied via ``fit_ml_model``.
        self._hybrid = HybridMLPredictor()
        self._ensemble.register_ml_model(self._hybrid)

        # Per-gameweek prediction cache:  (player_id, gameweek) -> PredictionResult
        self._cache: dict[tuple[int, int], PredictionResult] = {}

        self._ml_fitted = False

    # ------------------------------------------------------------------
    # ML model training
    # ------------------------------------------------------------------

    def fit_ml_model(
        self, X_train: list[list[float]], y_train: list[float]
    ) -> None:
        """Fit the hybrid ML model on historical labelled data.

        This must be called once before ``predict_player`` can include ML
        predictions in the ensemble.
        """
        self._hybrid.fit(X_train, y_train)
        self._ml_fitted = True
        logger.info("PredictionEngine: hybrid ML model fitted")

    # ------------------------------------------------------------------
    # Core prediction
    # ------------------------------------------------------------------

    async def predict_player(
        self,
        player_id: int,
        gameweek: int,
        n_ahead: int = 1,
        model: str | None = None,
    ) -> PredictionResult:
        """Predict total points for a single player.

        Parameters
        ----------
        player_id : int
            FPL element ID.
        gameweek : int
            Target gameweek number.
        n_ahead : int
            How many future GWs to forecast (default 1).
        model : str or None
            If specified, use only this model instead of the ensemble.
            Pass ``"ensemble"`` or ``None`` for the full ensemble.

        Returns
        -------
        PredictionResult
        """
        cache_key = (player_id, gameweek)
        if model is None and cache_key in self._cache:
            return self._cache[cache_key]

        # Fetch player history from FPL API
        from app.data.fpl_client import get_fpl_client

        client = get_fpl_client()
        history_records = await client.get_player_history(player_id)
        history = [float(h.total_points) for h in history_records]

        # Build ML feature vector from the player's current stats
        ml_features: list[float] | None = None
        if self._ml_fitted:
            player = await client.get_player_by_id(player_id)
            if player is not None:
                ml_features = self._extract_features(player)

        # If a specific model was requested, use only that model
        if model and model != "ensemble":
            preds = self._predict_single_model(
                model, history, n_ahead, ml_features
            )
            result = PredictionResult(
                player_id=player_id,
                gameweek=gameweek,
                predicted_points=preds[0] if preds else 0.0,
                model_name=model,
            )
            return result

        # Full ensemble prediction
        preds = self._ensemble.predict(history, n_ahead, ml_features)
        breakdown = self._ensemble.get_all_predictions(
            history, n_ahead, ml_features
        )
        breakdown_first_step = {
            name: vals[0] if vals else 0.0
            for name, vals in breakdown.items()
        }

        # Confidence interval from Monte Carlo
        mc = MonteCarloPredictor()
        if len(history) >= 3:
            mc_result = mc.simulate(history)
            ci_lower = mc_result.ci_lower
            ci_upper = mc_result.ci_upper
        else:
            ci_lower = 0.0
            ci_upper = preds[0] * 2 if preds else 0.0

        result = PredictionResult(
            player_id=player_id,
            gameweek=gameweek,
            predicted_points=preds[0] if preds else 0.0,
            confidence_lower=ci_lower,
            confidence_upper=ci_upper,
            model_name="ensemble",
            model_breakdown=breakdown_first_step,
        )

        # Cache the ensemble result
        self._cache[cache_key] = result
        return result

    async def predict_all_players(
        self, gameweek: int, player_ids: list[int] | None = None
    ) -> list[PredictionResult]:
        """Predict points for all (or selected) players for a gameweek.

        Parameters
        ----------
        gameweek : int
            Target gameweek.
        player_ids : list[int] or None
            Specific player IDs to predict.  If ``None``, fetches all
            players from the FPL API.
        """
        from app.data.fpl_client import get_fpl_client

        client = get_fpl_client()

        if player_ids is None:
            players = await client.get_players()
            player_ids = [p.id for p in players]

        results: list[PredictionResult] = []
        for pid in player_ids:
            try:
                result = await self.predict_player(pid, gameweek)
                results.append(result)
            except Exception as exc:
                logger.warning(
                    "Failed to predict player %d for GW%d: %s",
                    pid, gameweek, exc,
                )
        return results

    # ------------------------------------------------------------------
    # Model comparison
    # ------------------------------------------------------------------

    async def compare_models(
        self, player_id: int, gameweek: int
    ) -> dict[str, float]:
        """Return per-model predictions for a player (for the compare endpoint)."""
        from app.data.fpl_client import get_fpl_client

        client = get_fpl_client()
        history_records = await client.get_player_history(player_id)
        history = [float(h.total_points) for h in history_records]

        ml_features: list[float] | None = None
        if self._ml_fitted:
            player = await client.get_player_by_id(player_id)
            if player is not None:
                ml_features = self._extract_features(player)

        breakdown = self._ensemble.get_all_predictions(
            history, n_ahead=1, ml_features=ml_features
        )
        return {
            name: round(vals[0], 4) if vals else 0.0
            for name, vals in breakdown.items()
        }

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def available_models(self) -> list[dict[str, str]]:
        """Return metadata about all registered models."""
        return self._ensemble.model_info()

    def clear_cache(self) -> int:
        """Clear the prediction cache.  Returns the number of entries removed."""
        n = len(self._cache)
        self._cache.clear()
        return n

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _predict_single_model(
        self,
        model_name: str,
        history: list[float],
        n_ahead: int,
        ml_features: list[float] | None,
    ) -> list[float]:
        """Dispatch to a single model by name."""
        # Check TS models
        for name, m in self._ensemble._ts_models.items():
            if name == model_name:
                return m.predict(history, n_ahead)

        # Check ML models
        if ml_features is not None:
            for name, m in self._ensemble._ml_models.items():
                if name == model_name:
                    pred = m.predict([ml_features])
                    return pred * n_ahead

        return [0.0] * n_ahead

    @staticmethod
    def _extract_features(player: Any) -> list[float]:
        """Extract the HYBRID_FEATURES vector from a Player model."""
        return [
            float(getattr(player, feat, 0.0))
            for feat in HYBRID_FEATURES
        ]


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_engine_instance: PredictionEngine | None = None


def get_prediction_engine() -> PredictionEngine:
    """Return a singleton PredictionEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PredictionEngine()
    return _engine_instance
