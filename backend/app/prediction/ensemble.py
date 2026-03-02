"""Ensemble combiner for FPL prediction models.

Combines time-series and (optionally) ML-based predictors via a weighted
average.  Default weights are based on empirical backtest performance:

    ARIMA            = 0.35
    weighted_avg     = 0.25
    hybrid_ml        = 0.20
    exp_smoothing    = 0.10
    monte_carlo      = 0.10

The ensemble also provides ``get_all_predictions()`` for per-model
breakdowns exposed through the API.
"""

from __future__ import annotations

import logging
from typing import Any

from app.prediction.base import BasePredictor, BaseMLPredictor, PredictionResult

logger = logging.getLogger(__name__)

# Research-based default weights
DEFAULT_WEIGHTS: dict[str, float] = {
    "arima_100": 0.35,
    "weighted_avg": 0.25,
    "hybrid_ml": 0.20,
    "exp_smoothing": 0.10,
    "monte_carlo": 0.10,
}


class EnsemblePredictor:
    """Weighted ensemble of time-series and ML predictors.

    Parameters
    ----------
    weights : dict[str, float] or None
        Model name -> weight mapping.  If ``None`` the ``DEFAULT_WEIGHTS``
        are used.  Weights are automatically normalised to sum to 1.0.
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._ts_models: dict[str, BasePredictor] = {}
        self._ml_models: dict[str, BaseMLPredictor] = {}
        self._weights = dict(weights) if weights else dict(DEFAULT_WEIGHTS)
        self._normalise_weights()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_ts_model(self, model: BasePredictor) -> None:
        """Register a time-series predictor."""
        self._ts_models[model.name] = model
        logger.info("Ensemble: registered TS model '%s'", model.name)

    def register_ml_model(self, model: BaseMLPredictor) -> None:
        """Register an ML predictor."""
        self._ml_models[model.name] = model
        logger.info("Ensemble: registered ML model '%s'", model.name)

    # ------------------------------------------------------------------
    # Weight management
    # ------------------------------------------------------------------

    def set_weights(self, weights: dict[str, float]) -> None:
        """Update model weights and re-normalise."""
        self._weights = dict(weights)
        self._normalise_weights()

    def _normalise_weights(self) -> None:
        """Ensure weights sum to 1.0 (only over registered models)."""
        total = sum(self._weights.values())
        if total > 0:
            self._weights = {k: v / total for k, v in self._weights.items()}

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    # ------------------------------------------------------------------
    # Core prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        history: list[float],
        n_ahead: int = 1,
        ml_features: list[float] | None = None,
    ) -> list[float]:
        """Return the ensemble weighted prediction for ``n_ahead`` steps.

        Parameters
        ----------
        history : list[float]
            Historical total_points for the player.
        n_ahead : int
            Number of steps to forecast.
        ml_features : list[float] or None
            Single-row feature vector for ML models.  If ``None``, ML
            models are excluded from the ensemble (their weight is
            redistributed).
        """
        per_model = self.get_all_predictions(history, n_ahead, ml_features)
        if not per_model:
            return [0.0] * n_ahead

        # Build weighted average per step
        result = [0.0] * n_ahead
        total_weight = 0.0

        for model_name, preds in per_model.items():
            w = self._weights.get(model_name, 0.0)
            if w <= 0.0:
                continue
            total_weight += w
            for step in range(n_ahead):
                if step < len(preds):
                    result[step] += w * preds[step]

        if total_weight > 0:
            result = [round(v / total_weight, 4) for v in result]

        return result

    def get_all_predictions(
        self,
        history: list[float],
        n_ahead: int = 1,
        ml_features: list[float] | None = None,
    ) -> dict[str, list[float]]:
        """Return per-model predictions (for the API breakdown endpoint).

        Returns
        -------
        dict mapping model name -> list of predicted values (length ``n_ahead``).
        """
        per_model: dict[str, list[float]] = {}

        # Time-series models
        for name, model in self._ts_models.items():
            try:
                preds = model.predict(history, n_ahead)
                per_model[name] = preds
            except Exception as exc:
                logger.warning("Ensemble: TS model '%s' failed: %s", name, exc)

        # ML models (only if features provided)
        if ml_features is not None:
            for name, model in self._ml_models.items():
                try:
                    single_pred = model.predict([ml_features])
                    # ML models produce a single value; replicate for n_ahead
                    per_model[name] = [single_pred[0]] * n_ahead
                except Exception as exc:
                    logger.warning("Ensemble: ML model '%s' failed: %s", name, exc)

        return per_model

    # ------------------------------------------------------------------
    # Info helpers
    # ------------------------------------------------------------------

    @property
    def model_names(self) -> list[str]:
        """Return all registered model names."""
        return list(self._ts_models.keys()) + list(self._ml_models.keys())

    def model_info(self) -> list[dict[str, str]]:
        """Return metadata about all registered models."""
        info = []
        for name, m in self._ts_models.items():
            info.append({
                "name": name,
                "type": "time_series",
                "description": m.description,
                "weight": str(round(self._weights.get(name, 0.0), 4)),
            })
        for name, m in self._ml_models.items():
            info.append({
                "name": name,
                "type": "ml",
                "description": m.description,
                "weight": str(round(self._weights.get(name, 0.0), 4)),
            })
        return info
