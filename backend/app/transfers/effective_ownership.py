"""Effective ownership (EO) calculator for FPL players.

Effective ownership captures the *true* exposure to a player across the
league.  Because captaincy doubles a player's score, EO is:

    EO = ownership% + captaincy%

For example, a player owned by 30% of managers and captained by 10%
has EO = 40% (30% get 1x, 10% of those get an additional 1x).

Key outputs:
- **Differential picks**: EO < 10% but high predicted points
  (potential rank-gaining punts).
- **Template picks**: EO > 50% (risky *not* to own; losing ground if
  they haul).
"""

from __future__ import annotations

import logging

from app.transfers.models import PlayerEO

logger = logging.getLogger(__name__)

# Thresholds for classification
DIFFERENTIAL_EO_THRESHOLD = 10.0   # EO below this = differential
TEMPLATE_EO_THRESHOLD = 50.0       # EO above this = template
DIFFERENTIAL_POINTS_THRESHOLD = 4.0  # minimum predicted pts to qualify as differential


class EffectiveOwnership:
    """Calculate effective ownership and classify players."""

    def __init__(self) -> None:
        pass

    def calculate(
        self,
        players: list[dict],
        captaincy_rates: dict[int, float] | None = None,
        predicted_points: dict[int, float] | None = None,
    ) -> list[PlayerEO]:
        """Compute EO for a list of players.

        Parameters
        ----------
        players : list[dict]
            Player dicts, each containing at least:
            - ``id`` (int)
            - ``selected_by_percent`` (float, 0-100)
            Optionally: ``captaincy_rate`` (float, 0-100).
        captaincy_rates : dict[int, float] or None
            Override captaincy rates keyed by player id (0-100).
            If not provided, captaincy is estimated from ownership
            using a simple heuristic.
        predicted_points : dict[int, float] or None
            Predicted points per player.  Used to identify differentials
            (high predicted points despite low EO).

        Returns
        -------
        list[PlayerEO]
            Sorted by effective_ownership descending.
        """
        results: list[PlayerEO] = []

        for player in players:
            pid = player.get("id", 0)
            ownership = float(player.get("selected_by_percent", 0.0))

            # Captaincy rate: from explicit dict > from player dict > estimate
            if captaincy_rates and pid in captaincy_rates:
                cap_rate = captaincy_rates[pid]
            elif "captaincy_rate" in player:
                cap_rate = float(player["captaincy_rate"])
            else:
                cap_rate = self._estimate_captaincy_rate(ownership)

            eo = ownership + cap_rate

            # Differential classification
            pts = (predicted_points or {}).get(pid, 0.0)
            is_differential = (
                eo < DIFFERENTIAL_EO_THRESHOLD
                and pts >= DIFFERENTIAL_POINTS_THRESHOLD
            )
            is_template = eo >= TEMPLATE_EO_THRESHOLD

            results.append(
                PlayerEO(
                    player_id=pid,
                    ownership=ownership,
                    captaincy_rate=cap_rate,
                    effective_ownership=round(eo, 2),
                    is_differential=is_differential,
                    is_template=is_template,
                )
            )

        # Sort by EO descending
        results.sort(key=lambda x: x.effective_ownership, reverse=True)
        return results

    def get_differentials(
        self,
        players: list[dict],
        captaincy_rates: dict[int, float] | None = None,
        predicted_points: dict[int, float] | None = None,
        eo_threshold: float = DIFFERENTIAL_EO_THRESHOLD,
        min_predicted_pts: float = DIFFERENTIAL_POINTS_THRESHOLD,
    ) -> list[PlayerEO]:
        """Return only differential picks (low EO, high predicted points).

        Parameters
        ----------
        eo_threshold : float
            Maximum EO to qualify as a differential.
        min_predicted_pts : float
            Minimum predicted points to be an interesting differential.
        """
        all_eo = self.calculate(players, captaincy_rates, predicted_points)
        return [
            p for p in all_eo
            if p.effective_ownership < eo_threshold
            and (predicted_points or {}).get(p.player_id, 0.0) >= min_predicted_pts
        ]

    def get_template_picks(
        self,
        players: list[dict],
        captaincy_rates: dict[int, float] | None = None,
        predicted_points: dict[int, float] | None = None,
        eo_threshold: float = TEMPLATE_EO_THRESHOLD,
    ) -> list[PlayerEO]:
        """Return template picks (EO above threshold)."""
        all_eo = self.calculate(players, captaincy_rates, predicted_points)
        return [p for p in all_eo if p.effective_ownership >= eo_threshold]

    # ------------------------------------------------------------------
    # Captaincy estimation heuristic
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_captaincy_rate(ownership: float) -> float:
        """Estimate captaincy rate from ownership percentage.

        Heuristic based on FPL patterns:
        - Very high ownership players (>40%) are captained by ~15-25%
        - Medium ownership (20-40%) captained by ~5-10%
        - Low ownership (<20%) captained by ~0-3%

        This is a rough power-law approximation calibrated against
        historical FPL captaincy data.
        """
        if ownership <= 0:
            return 0.0
        if ownership >= 50.0:
            # Top-tier premiums: Haaland, Salah type
            return min(ownership * 0.4, 40.0)
        if ownership >= 30.0:
            return ownership * 0.25
        if ownership >= 15.0:
            return ownership * 0.12
        if ownership >= 5.0:
            return ownership * 0.05
        return ownership * 0.01
