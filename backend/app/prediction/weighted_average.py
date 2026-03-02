"""Weighted average predictor with linear recency bias.

Uses linearly increasing weights so that more recent observations carry
more influence on the forecast:

    w_t = t / sum(1..T)

where *t* is the 1-based position in the window (oldest=1, newest=T).
"""

from __future__ import annotations

import logging

from app.prediction.base import BasePredictor

logger = logging.getLogger(__name__)


class WeightedAveragePredictor(BasePredictor):
    """Recency-weighted average predictor for FPL total points.

    Parameters
    ----------
    window : int or None
        Number of most-recent observations to use.  ``None`` (default)
        means "use the entire history".
    """

    def __init__(self, window: int | None = None) -> None:
        self._window = window

    # ------------------------------------------------------------------
    # BasePredictor interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "weighted_avg"

    @property
    def description(self) -> str:
        w = self._window or "all"
        return f"Linearly recency-weighted average (window={w})"

    def predict(self, history: list[float], n_ahead: int = 1) -> list[float]:
        """Return the weighted average repeated for ``n_ahead`` steps.

        The forecast is *flat* -- the same value is used for every future
        step because the model has no trend component.
        """
        if not self._validate_history(history, min_length=1):
            logger.warning("WeightedAvg: empty history, returning zeros")
            return self._safe_fallback(n_ahead)

        series = self._apply_window(history)
        T = len(series)

        # weights: 1, 2, ..., T
        weight_sum = T * (T + 1) / 2
        weighted_total = sum(
            (t + 1) * val for t, val in enumerate(series)
        )
        prediction = weighted_total / weight_sum
        return [round(prediction, 4)] * n_ahead

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_window(self, history: list[float]) -> list[float]:
        """Trim history to the configured window size."""
        if self._window is not None and len(history) > self._window:
            return history[-self._window:]
        return history
