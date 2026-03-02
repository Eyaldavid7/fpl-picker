"""Hybrid ML predictor: Ridge regression + XGBoost blend.

Combines a regularised linear model (Ridge) with a gradient-boosted tree
(XGBoost) to get the best of both worlds -- the stability and
interpretability of Ridge with the non-linear capacity of XGBoost.

Blend formula:
    y_hat = (1 - lambda_) * ridge_pred + lambda_ * xgb_pred

Default lambda_ = 2/3  (XGBoost gets twice the weight of Ridge).

Expected features (column order matters):
    ict_index, expected_goal_involvements, expected_goals, expected_assists,
    form, minutes, bps, selected_by_percent
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.prediction.base import BaseMLPredictor

logger = logging.getLogger(__name__)

# Features the hybrid model expects (in order)
HYBRID_FEATURES: list[str] = [
    "ict_index",
    "expected_goal_involvements",
    "expected_goals",
    "expected_assists",
    "form",
    "minutes",
    "bps",
    "selected_by_percent",
]


class HybridMLPredictor(BaseMLPredictor):
    """Blended Ridge + XGBoost predictor.

    Parameters
    ----------
    lambda_ : float
        XGBoost blend weight.  ``0.0`` = pure Ridge, ``1.0`` = pure XGBoost.
        Default ``2/3``.
    ridge_alpha : float
        Regularisation strength for Ridge regression (default 1.0).
    xgb_kwargs : dict, optional
        Extra keyword arguments forwarded to ``xgboost.XGBRegressor``.
    """

    def __init__(
        self,
        lambda_: float = 2 / 3,
        ridge_alpha: float = 1.0,
        xgb_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._lambda = lambda_
        self._ridge_alpha = ridge_alpha
        self._xgb_kwargs = xgb_kwargs or {}
        self._ridge: Any = None
        self._xgb: Any = None
        self._fitted = False

    # ------------------------------------------------------------------
    # BaseMLPredictor interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "hybrid_ml"

    @property
    def description(self) -> str:
        return (
            f"Ridge + XGBoost blend (lambda={self._lambda:.2f}). "
            f"Features: {', '.join(HYBRID_FEATURES)}"
        )

    def fit(self, X_train: list[list[float]], y_train: list[float]) -> None:
        """Train both Ridge and XGBoost on the same training data."""
        from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
        from xgboost import XGBRegressor  # type: ignore[import-untyped]

        X = np.asarray(X_train, dtype=np.float64)
        y = np.asarray(y_train, dtype=np.float64)

        if X.shape[0] == 0:
            logger.warning("HybridML: empty training set, skipping fit")
            return

        # --- Ridge ---
        self._ridge = Ridge(alpha=self._ridge_alpha)
        self._ridge.fit(X, y)

        # --- XGBoost ---
        xgb_defaults: dict[str, Any] = {
            "n_estimators": 100,
            "max_depth": 4,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "objective": "reg:squarederror",
            "random_state": 42,
            "verbosity": 0,
        }
        xgb_defaults.update(self._xgb_kwargs)
        self._xgb = XGBRegressor(**xgb_defaults)
        self._xgb.fit(X, y)

        self._fitted = True
        logger.info(
            "HybridML fitted on %d samples x %d features",
            X.shape[0],
            X.shape[1],
        )

    def predict(self, X: list[list[float]]) -> list[float]:
        """Return blended predictions for each row in ``X``.

        If the model has not been fitted, returns zeros.
        """
        if not self._fitted or self._ridge is None or self._xgb is None:
            logger.warning("HybridML: predict called before fit, returning zeros")
            return [0.0] * len(X)

        X_arr = np.asarray(X, dtype=np.float64)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)

        ridge_preds = self._ridge.predict(X_arr)
        xgb_preds = self._xgb.predict(X_arr)

        blended = (
            (1 - self._lambda) * ridge_preds + self._lambda * xgb_preds
        )
        return [round(float(v), 4) for v in blended]

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def predict_single(self, features: list[float]) -> float:
        """Predict a single sample (convenience wrapper)."""
        results = self.predict([features])
        return results[0] if results else 0.0

    @property
    def feature_names(self) -> list[str]:
        """Return the expected feature column names in order."""
        return list(HYBRID_FEATURES)
