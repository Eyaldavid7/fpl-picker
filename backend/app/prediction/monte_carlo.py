"""Monte Carlo simulation predictor.

Estimates the mean and standard deviation of a player's historical point
series, then runs ``B`` parametric simulations to produce:
- A point forecast (mean of simulated means)
- Confidence intervals (percentile-based)

This is useful for capturing the inherent *variance* in FPL points --
a player who averages 5 pts/GW with std=4 is very different from one
who averages 5 pts/GW with std=1, and the confidence interval reflects
that.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from app.prediction.base import BasePredictor

logger = logging.getLogger(__name__)

# Minimum history length for meaningful estimation
_MIN_OBS = 3


@dataclass
class MonteCarloResult:
    """Extended result from Monte Carlo simulation including CI."""

    mean: float
    std: float
    ci_lower: float  # 5th percentile
    ci_upper: float  # 95th percentile
    simulations: int


class MonteCarloPredictor(BasePredictor):
    """Parametric Monte Carlo simulator for FPL points.

    Parameters
    ----------
    n_simulations : int
        Number of simulation iterations (default 1000).
    ci_level : float
        Confidence interval width as a fraction.  ``0.90`` (default)
        produces a 90% CI (5th and 95th percentiles).
    seed : int or None
        Random seed for reproducibility.
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        ci_level: float = 0.90,
        seed: int | None = 42,
    ) -> None:
        self._B = n_simulations
        self._ci_level = ci_level
        self._rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # BasePredictor interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "monte_carlo"

    @property
    def description(self) -> str:
        return (
            f"Parametric Monte Carlo simulation (B={self._B}) with "
            f"{self._ci_level*100:.0f}% confidence intervals"
        )

    def predict(self, history: list[float], n_ahead: int = 1) -> list[float]:
        """Return the mean predicted value for each of the next ``n_ahead``
        steps.  The prediction is the same for all steps (flat forecast)
        since the Monte Carlo method has no trend component.
        """
        if not self._validate_history(history, min_length=_MIN_OBS):
            logger.debug(
                "MonteCarlo: insufficient history (%d < %d), returning zeros",
                len(history),
                _MIN_OBS,
            )
            return self._safe_fallback(n_ahead)

        result = self.simulate(history)
        return [round(result.mean, 4)] * n_ahead

    # ------------------------------------------------------------------
    # Extended simulation (returns CI alongside mean)
    # ------------------------------------------------------------------

    def simulate(self, history: list[float]) -> MonteCarloResult:
        """Run the full Monte Carlo simulation and return detailed results.

        The simulation draws ``B`` independent samples of size ``len(history)``
        from a Normal distribution parameterised by the sample mean and
        standard deviation.  The mean of each sample is recorded, giving a
        distribution of plausible *expected* points.
        """
        arr = np.asarray(history, dtype=np.float64)
        mu = float(arr.mean())
        sigma = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0

        # Guard against zero variance
        if sigma < 1e-9:
            return MonteCarloResult(
                mean=mu,
                std=0.0,
                ci_lower=mu,
                ci_upper=mu,
                simulations=self._B,
            )

        # Simulate B sample-means
        sim_means = np.empty(self._B, dtype=np.float64)
        n = len(arr)
        for i in range(self._B):
            sample = self._rng.normal(loc=mu, scale=sigma, size=n)
            sim_means[i] = sample.mean()

        # Percentiles for confidence interval
        alpha = (1 - self._ci_level) / 2
        lo = float(np.percentile(sim_means, alpha * 100))
        hi = float(np.percentile(sim_means, (1 - alpha) * 100))

        return MonteCarloResult(
            mean=round(float(sim_means.mean()), 4),
            std=round(float(sim_means.std()), 4),
            ci_lower=round(lo, 4),
            ci_upper=round(hi, 4),
            simulations=self._B,
        )
