"""Exponential smoothing predictor using Holt-Winters.

Wraps ``statsmodels.tsa.holtwinters.ExponentialSmoothing`` with automatic
alpha/beta optimisation and graceful handling of short series.

For very short histories (< 4 observations) the model degrades to Simple
Exponential Smoothing (trend=None, seasonal=None).  For histories of at
least 4 observations an additive trend is used.  Seasonal components are
not applied because weekly FPL data has no strong within-season periodicity.
"""

from __future__ import annotations

import logging
import warnings

from app.prediction.base import BasePredictor

logger = logging.getLogger(__name__)

# Minimum observations for trend modelling
_MIN_FOR_TREND = 4
# Absolute minimum for any forecast
_MIN_OBS = 2


class ExpSmoothingPredictor(BasePredictor):
    """Holt-Winters exponential smoothing predictor.

    Parameters
    ----------
    damped_trend : bool
        Whether to dampen the trend component (default ``True``).
        Damping is generally safer for FPL data where trends rarely
        persist for many weeks.
    """

    def __init__(self, damped_trend: bool = True) -> None:
        self._damped_trend = damped_trend

    # ------------------------------------------------------------------
    # BasePredictor interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "exp_smoothing"

    @property
    def description(self) -> str:
        return (
            "Holt-Winters exponential smoothing with auto-optimised "
            "alpha/beta parameters and optional damped trend"
        )

    def predict(self, history: list[float], n_ahead: int = 1) -> list[float]:
        """Forecast ``n_ahead`` steps using exponential smoothing.

        Automatically selects the model complexity based on history length:
        - < 2 points  -> zero fallback
        - 2-3 points  -> Simple Exponential Smoothing (no trend)
        - >= 4 points -> Holt's linear trend (optionally damped)
        """
        if not self._validate_history(history, min_length=_MIN_OBS):
            logger.debug(
                "ExpSmoothing: insufficient history (%d < %d), returning zeros",
                len(history),
                _MIN_OBS,
            )
            return self._safe_fallback(n_ahead)

        try:
            return self._fit_and_forecast(history, n_ahead)
        except Exception as exc:
            logger.warning(
                "ExpSmoothing failed (%s), falling back to last-value carry-forward",
                exc,
            )
            # Ultimate fallback: repeat the last known value
            return [round(history[-1], 4)] * n_ahead

    # ------------------------------------------------------------------
    # Internal fitting
    # ------------------------------------------------------------------

    def _fit_and_forecast(
        self, history: list[float], n_ahead: int
    ) -> list[float]:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing  # type: ignore[import-untyped]

        use_trend: str | None = None
        use_damped = False

        if len(history) >= _MIN_FOR_TREND:
            use_trend = "add"
            use_damped = self._damped_trend

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ExponentialSmoothing(
                history,
                trend=use_trend,
                damped_trend=use_damped,
                seasonal=None,
                initialization_method="estimated",
            )
            fitted = model.fit(optimized=True)
            forecast = fitted.forecast(n_ahead)

        return [round(float(v), 4) for v in forecast]
