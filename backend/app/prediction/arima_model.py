"""ARIMA(1,0,0) predictor with rolling-window refit and automatic fallback.

Uses ``statsmodels.tsa.arima.model.ARIMA`` for the forecast.  If the model
fails to converge (which is common with short or flat FPL point series) the
predictor silently falls back to :class:`WeightedAveragePredictor`.
"""

from __future__ import annotations

import logging
import warnings

from app.prediction.base import BasePredictor
from app.prediction.weighted_average import WeightedAveragePredictor

logger = logging.getLogger(__name__)

# Minimum number of observations required for ARIMA fitting
_MIN_OBS = 5


class ARIMAPredictor(BasePredictor):
    """Rolling-window ARIMA(1,0,0) predictor.

    Parameters
    ----------
    window : int
        Number of most-recent observations to use when refitting the model
        on each call to ``predict``.  Default is 20.
    order : tuple[int, int, int]
        ARIMA order ``(p, d, q)``.  Default ``(1, 0, 0)`` -- essentially
        an AR(1) process, which works well for noisy weekly FPL data.
    """

    def __init__(
        self,
        window: int = 20,
        order: tuple[int, int, int] = (1, 0, 0),
    ) -> None:
        self._window = window
        self._order = order
        self._fallback = WeightedAveragePredictor(window=window)

    # ------------------------------------------------------------------
    # BasePredictor interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        p, d, q = self._order
        return f"arima_{p}{d}{q}"

    @property
    def description(self) -> str:
        p, d, q = self._order
        return (
            f"ARIMA({p},{d},{q}) with rolling window of {self._window} "
            f"observations; falls back to weighted average on convergence failure"
        )

    def predict(self, history: list[float], n_ahead: int = 1) -> list[float]:
        """Fit ARIMA on (at most) the last ``window`` observations and
        forecast ``n_ahead`` steps.

        Falls back to the weighted-average predictor when:
        - The history has fewer than ``_MIN_OBS`` data points.
        - ``statsmodels`` is not installed.
        - The ARIMA model fails to converge.
        """
        if not self._validate_history(history, min_length=_MIN_OBS):
            logger.debug(
                "ARIMA: insufficient history (%d < %d), using fallback",
                len(history),
                _MIN_OBS,
            )
            return self._fallback.predict(history, n_ahead)

        series = history[-self._window:] if len(history) > self._window else list(history)

        try:
            return self._fit_and_forecast(series, n_ahead)
        except Exception as exc:
            logger.warning("ARIMA convergence failure: %s -- using fallback", exc)
            return self._fallback.predict(history, n_ahead)

    # ------------------------------------------------------------------
    # Internal ARIMA fitting
    # ------------------------------------------------------------------

    def _fit_and_forecast(
        self, series: list[float], n_ahead: int
    ) -> list[float]:
        """Fit the ARIMA model and return the forecast.

        All statsmodels convergence warnings are suppressed to avoid
        cluttering logs during batch predictions.
        """
        from statsmodels.tsa.arima.model import ARIMA  # type: ignore[import-untyped]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ARIMA(series, order=self._order)
            fitted = model.fit(method_kwargs={"warn_convergence": False})
            forecast = fitted.forecast(steps=n_ahead)

        return [round(float(v), 4) for v in forecast]
