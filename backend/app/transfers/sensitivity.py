"""Sensitivity analysis for proposed transfers.

Perturbs the underlying point predictions by +/-10% and +/-20% and
re-evaluates each proposed transfer.  Transfers are classified by how
robust they are to prediction uncertainty:

- **strong** : recommended in >80% of perturbation scenarios
- **moderate**: recommended in 50-80% of scenarios
- **volatile**: recommended in <50% of scenarios

This helps FPL managers distinguish between "no-brainer" transfers and
those that depend heavily on predictions being exactly right.
"""

from __future__ import annotations

import logging
from copy import deepcopy

from app.transfers.models import (
    SensitivityResult,
    TransferClassification,
    TransferClassificationEntry,
)

logger = logging.getLogger(__name__)

# Perturbation multipliers applied to predictions
PERTURBATION_FACTORS: list[float] = [0.80, 0.90, 1.00, 1.10, 1.20]


class SensitivityAnalyzer:
    """Evaluate transfer robustness under prediction uncertainty."""

    def __init__(self) -> None:
        pass

    def analyze(
        self,
        current_squad: list[int],
        proposed_transfers: list[tuple[int, int]],
        predictions: dict[int, float],
        perturbation_factors: list[float] | None = None,
    ) -> SensitivityResult:
        """Run sensitivity analysis on proposed transfers.

        Parameters
        ----------
        current_squad : list[int]
            Current 15-player squad (player IDs).
        proposed_transfers : list[tuple[int, int]]
            List of (player_out_id, player_in_id) pairs.
        predictions : dict[int, float]
            Base predicted points for all relevant players.
        perturbation_factors : list[float] or None
            Custom perturbation multipliers.  Defaults to
            ``[0.80, 0.90, 1.00, 1.10, 1.20]``.

        Returns
        -------
        SensitivityResult
            Classification of each transfer and overall robustness score.
        """
        if not proposed_transfers:
            return SensitivityResult(robustness_score=1.0)

        factors = perturbation_factors or PERTURBATION_FACTORS
        n_scenarios = len(factors) * len(factors)

        classifications: list[TransferClassificationEntry] = []

        for out_id, in_id in proposed_transfers:
            recommended_count = 0

            for out_factor in factors:
                for in_factor in factors:
                    # Perturb the two involved players independently
                    perturbed = dict(predictions)
                    if out_id in perturbed:
                        perturbed[out_id] = predictions.get(out_id, 0.0) * out_factor
                    if in_id in perturbed:
                        perturbed[in_id] = predictions.get(in_id, 0.0) * in_factor
                    # Check if this transfer is still beneficial
                    if self._is_transfer_beneficial(out_id, in_id, perturbed):
                        recommended_count += 1

            rate = recommended_count / n_scenarios if n_scenarios > 0 else 0.0
            classification = self._classify(rate)

            classifications.append(
                TransferClassificationEntry(
                    player_out_id=out_id,
                    player_in_id=in_id,
                    classification=classification,
                    recommendation_rate=rate,
                )
            )

        # Overall robustness = average recommendation rate
        avg_rate = (
            sum(c.recommendation_rate for c in classifications) / len(classifications)
            if classifications
            else 0.0
        )

        return SensitivityResult(
            transfer_classifications=classifications,
            robustness_score=round(avg_rate, 4),
        )

    def analyze_detailed(
        self,
        current_squad: list[int],
        proposed_transfers: list[tuple[int, int]],
        predictions: dict[int, float],
    ) -> SensitivityResult:
        """Extended analysis with finer perturbation granularity.

        Uses 9 perturbation levels: -20%, -15%, -10%, -5%, 0%, +5%, +10%, +15%, +20%.
        """
        fine_factors = [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]
        return self.analyze(
            current_squad=current_squad,
            proposed_transfers=proposed_transfers,
            predictions=predictions,
            perturbation_factors=fine_factors,
        )

    def analyze_asymmetric(
        self,
        current_squad: list[int],
        proposed_transfers: list[tuple[int, int]],
        predictions: dict[int, float],
    ) -> SensitivityResult:
        """Asymmetric perturbation: perturb player_in and player_out separately.

        For each proposed transfer, independently perturb:
        - The player_out's prediction by each factor
        - The player_in's prediction by each factor

        This creates a grid of (5 x 5) = 25 scenarios per transfer,
        giving more granular insight into which direction drives volatility.
        """
        if not proposed_transfers:
            return SensitivityResult(robustness_score=1.0)

        factors = PERTURBATION_FACTORS
        n_scenarios = len(factors) * len(factors)
        classifications: list[TransferClassificationEntry] = []

        for out_id, in_id in proposed_transfers:
            recommended_count = 0

            for out_factor in factors:
                for in_factor in factors:
                    # Perturb only the two involved players differently
                    perturbed = dict(predictions)
                    if out_id in perturbed:
                        perturbed[out_id] = predictions.get(out_id, 0.0) * out_factor
                    if in_id in perturbed:
                        perturbed[in_id] = predictions.get(in_id, 0.0) * in_factor

                    if self._is_transfer_beneficial(out_id, in_id, perturbed):
                        recommended_count += 1

            rate = recommended_count / n_scenarios
            classification = self._classify(rate)

            classifications.append(
                TransferClassificationEntry(
                    player_out_id=out_id,
                    player_in_id=in_id,
                    classification=classification,
                    recommendation_rate=rate,
                )
            )

        avg_rate = (
            sum(c.recommendation_rate for c in classifications) / len(classifications)
            if classifications
            else 0.0
        )

        return SensitivityResult(
            transfer_classifications=classifications,
            robustness_score=round(avg_rate, 4),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_transfer_beneficial(
        out_id: int,
        in_id: int,
        predictions: dict[int, float],
    ) -> bool:
        """Return True if transferring in_id for out_id yields a point gain."""
        out_pts = predictions.get(out_id, 0.0)
        in_pts = predictions.get(in_id, 0.0)
        return in_pts > out_pts

    @staticmethod
    def _classify(rate: float) -> TransferClassification:
        """Map recommendation rate to classification tier."""
        if rate > 0.80:
            return TransferClassification.STRONG
        elif rate >= 0.50:
            return TransferClassification.MODERATE
        else:
            return TransferClassification.VOLATILE
