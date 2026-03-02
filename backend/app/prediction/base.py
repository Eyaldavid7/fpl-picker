"""Abstract base classes for all prediction models.

Provides two abstract interfaces:
1. ``BasePredictor`` -- time-series models that operate on a 1-D history of
   point values (ARIMA, weighted average, exponential smoothing, Monte Carlo).
2. ``BaseMLPredictor`` -- supervised ML models that operate on a feature matrix
   (Ridge + XGBoost hybrid).

Both share the ``PredictionResult`` dataclass for returning forecasts.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses for prediction outputs
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    """Result from a single prediction model for one player."""

    player_id: int = 0
    gameweek: int = 0
    predicted_points: float = 0.0
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    model_name: str = ""
    model_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class EnsemblePredictionResult:
    """Ensemble result containing both the combined forecast and per-model
    breakdown for a single player/gameweek pair."""

    player_id: int = 0
    gameweek: int = 0
    predicted_points: float = 0.0
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    model_breakdown: dict[str, float] = field(default_factory=dict)
    weights_used: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base for time-series predictors
# ---------------------------------------------------------------------------

class BasePredictor(ABC):
    """Abstract base class for time-series point predictors.

    Subclasses operate on a 1-D list of historical point values (floats)
    and produce forecasts for one or more future steps.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this model."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of the model."""
        return self.name

    def fit(self, history: list[float]) -> None:
        """Optional training step.  Most time-series models are stateless
        or fit on-the-fly inside ``predict``, so the default is a no-op."""
        pass  # noqa: WPS420

    @abstractmethod
    def predict(self, history: list[float], n_ahead: int = 1) -> list[float]:
        """Generate point forecasts for the next ``n_ahead`` time steps.

        Parameters
        ----------
        history : list[float]
            Historical total-points values ordered chronologically
            (oldest first).
        n_ahead : int
            Number of future steps to forecast (default 1).

        Returns
        -------
        list[float]
            Predicted values for the next ``n_ahead`` steps.  If the model
            cannot produce a forecast (e.g. insufficient data) it should
            return a list of 0.0 values.
        """
        ...

    # ------------------------------------------------------------------
    # Edge-case helpers available to all subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_fallback(n_ahead: int, fill: float = 0.0) -> list[float]:
        """Return a list of ``fill`` values -- used when there is not
        enough data to make a meaningful prediction."""
        return [fill] * n_ahead

    @staticmethod
    def _validate_history(history: list[float], min_length: int = 1) -> bool:
        """Return ``True`` if history has at least ``min_length`` values."""
        return len(history) >= min_length


# ---------------------------------------------------------------------------
# Abstract base for supervised ML predictors
# ---------------------------------------------------------------------------

class BaseMLPredictor(ABC):
    """Abstract base class for supervised ML predictors.

    These models operate on a feature matrix (``X``) rather than a plain
    1-D history, and require an explicit ``fit`` step before ``predict``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this model."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of the model."""
        return self.name

    @abstractmethod
    def fit(self, X_train: "list[list[float]]", y_train: list[float]) -> None:
        """Train the model on labelled data.

        Parameters
        ----------
        X_train : array-like of shape (n_samples, n_features)
        y_train : array-like of shape (n_samples,)
        """
        ...

    @abstractmethod
    def predict(self, X: "list[list[float]]") -> list[float]:
        """Generate point predictions for each row in ``X``.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)

        Returns
        -------
        list[float]
            Predicted total_points for each sample.
        """
        ...
