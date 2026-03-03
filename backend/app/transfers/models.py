"""Data models for the transfer strategy and chip timing module.

All models use dataclasses for lightweight, hashable representations that
integrate cleanly with the rest of the backend (optimisation models use
the same pattern).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ChipType(str, Enum):
    """FPL chip types."""

    WILDCARD = "wildcard"
    FREE_HIT = "free_hit"
    TRIPLE_CAPTAIN = "triple_captain"
    BENCH_BOOST = "bench_boost"


class TransferClassification(str, Enum):
    """Sensitivity-based classification of a proposed transfer."""

    STRONG = "strong"       # Recommended in >80% of perturbations
    MODERATE = "moderate"   # Recommended in 50-80% of perturbations
    VOLATILE = "volatile"   # Recommended in <50% of perturbations


# ---------------------------------------------------------------------------
# Transfer Planning
# ---------------------------------------------------------------------------

@dataclass
class TransferAction:
    """A single transfer action within a multi-GW plan."""

    gameweek: int
    player_out_id: int
    player_in_id: int
    cost_delta: float = 0.0          # budget change (positive = saved money)
    predicted_point_gain: float = 0.0  # expected point uplift from this move

    def to_dict(self) -> dict:
        return {
            "gameweek": self.gameweek,
            "player_out_id": self.player_out_id,
            "player_in_id": self.player_in_id,
            "cost_delta": self.cost_delta,
            "predicted_point_gain": self.predicted_point_gain,
        }


@dataclass
class TransferPlan:
    """Multi-gameweek transfer plan output."""

    actions: list[TransferAction] = field(default_factory=list)
    total_hits: int = 0              # total -4 penalties taken
    net_point_gain: float = 0.0      # sum of point gains minus hit costs
    gameweeks_covered: int = 0       # number of GWs in the planning horizon

    @property
    def total_hit_cost(self) -> int:
        """Total points lost to hits."""
        return self.total_hits * 4

    def to_dict(self) -> dict:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "total_hits": self.total_hits,
            "net_point_gain": self.net_point_gain,
            "gameweeks_covered": self.gameweeks_covered,
            "total_hit_cost": self.total_hit_cost,
        }


# ---------------------------------------------------------------------------
# Chip Strategy
# ---------------------------------------------------------------------------

@dataclass
class ChipRecommendation:
    """Recommendation for when to deploy a specific chip."""

    chip_type: ChipType
    recommended_gameweek: int
    expected_value: float = 0.0   # additional points expected from using the chip
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "chip_type": self.chip_type.value,
            "recommended_gameweek": self.recommended_gameweek,
            "expected_value": self.expected_value,
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# Sensitivity Analysis
# ---------------------------------------------------------------------------

@dataclass
class TransferClassificationEntry:
    """Classification of a single proposed transfer under perturbation."""

    player_out_id: int
    player_in_id: int
    classification: TransferClassification
    recommendation_rate: float  # fraction of perturbations that still recommend

    def to_dict(self) -> dict:
        return {
            "player_out_id": self.player_out_id,
            "player_in_id": self.player_in_id,
            "classification": self.classification.value,
            "recommendation_rate": round(self.recommendation_rate, 4),
        }


@dataclass
class SensitivityResult:
    """Aggregated result of sensitivity analysis on proposed transfers."""

    transfer_classifications: list[TransferClassificationEntry] = field(
        default_factory=list
    )
    robustness_score: float = 0.0  # average recommendation rate across all transfers

    def to_dict(self) -> dict:
        return {
            "transfer_classifications": [
                tc.to_dict() for tc in self.transfer_classifications
            ],
            "robustness_score": round(self.robustness_score, 4),
        }


# ---------------------------------------------------------------------------
# Effective Ownership
# ---------------------------------------------------------------------------

@dataclass
class PlayerEO:
    """Effective ownership data for a single player."""

    player_id: int
    ownership: float            # ownership percentage (0-100)
    captaincy_rate: float       # captaincy percentage (0-100)
    effective_ownership: float  # EO = ownership + captaincy (captain doubles points)
    is_differential: bool       # EO < 10% but high predicted points
    is_template: bool = False   # EO > 50%

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "ownership": round(self.ownership, 2),
            "captaincy_rate": round(self.captaincy_rate, 2),
            "effective_ownership": round(self.effective_ownership, 2),
            "is_differential": self.is_differential,
            "is_template": self.is_template,
        }
