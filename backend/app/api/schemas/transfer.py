"""Pydantic models for transfer-related API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TransferMove(BaseModel):
    """A single transfer move (in/out).

    Attributes:
        player_in_id: FPL element ID of the incoming player.
        player_out_id: FPL element ID of the outgoing player.
        player_in_name: Display name of the incoming player.
        player_out_name: Display name of the outgoing player.
        cost_delta: Budget change in 0.1m units (positive = saved money).
        expected_point_gain: Expected point uplift from this transfer.
    """

    player_in_id: int
    player_out_id: int
    player_in_name: str = ""
    player_out_name: str = ""
    cost_delta: int = 0
    expected_point_gain: float = 0.0


class TransferRecommendRequest(BaseModel):
    """Request body for transfer recommendations.

    Attributes:
        current_squad: List of 15 player IDs in the current squad.
        bank: Available bank balance in 0.1m units (0-500).
        free_transfers: Number of free transfers available (1-5).
        horizon: Number of gameweeks to look ahead (1-10).
        max_hits: Maximum allowed transfer hits. None for no limit.

    Example:
        >>> request = TransferRecommendRequest(
        ...     current_squad=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        ...     bank=10,
        ...     free_transfers=1,
        ...     horizon=1,
        ... )
    """

    current_squad: list[int] = Field(
        ...,
        min_length=15,
        max_length=15,
        description="Current squad of exactly 15 player IDs",
    )
    bank: int = Field(
        default=0,
        ge=0,
        le=500,
        description="Available bank balance in 0.1m units",
    )
    free_transfers: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of free transfers available",
    )
    horizon: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of gameweeks to look ahead",
    )
    max_hits: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Maximum transfer hits allowed. None for no limit.",
    )


class TransferRecommendResponse(BaseModel):
    """Response for transfer recommendations."""

    transfers: list[TransferMove]
    total_gain: float
    hits_taken: int
    net_gain: float


class GameweekPlan(BaseModel):
    """Transfer plan for a single gameweek."""

    gameweek: int
    transfers: list[TransferMove]
    hits: int = 0
    expected_points: float = 0.0
    cumulative_gain: float = 0.0


class TransferPlanRequest(BaseModel):
    """Request body for multi-GW transfer plan.

    Attributes:
        current_squad: List of 15 player IDs in the current squad.
        bank: Available bank balance in 0.1m units (0-500).
        free_transfers: Number of free transfers available (1-5).
        horizon: Number of gameweeks to plan ahead (1-10).
        max_hits_per_gw: Maximum hits per gameweek. None for no limit.
    """

    current_squad: list[int] = Field(
        ...,
        min_length=15,
        max_length=15,
        description="Current squad of exactly 15 player IDs",
    )
    bank: int = Field(default=0, ge=0, le=500)
    free_transfers: int = Field(default=1, ge=1, le=5)
    horizon: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of gameweeks to plan ahead",
    )
    max_hits_per_gw: int | None = Field(
        default=1,
        ge=0,
        le=5,
        description="Maximum hits allowed per gameweek",
    )


class TransferPlanResponse(BaseModel):
    """Response for multi-GW transfer plan."""

    gameweek_plans: list[GameweekPlan]
    total_gain_over_horizon: float
    total_hits: int


class TransferEvaluateRequest(BaseModel):
    """Request body for transfer evaluation.

    Attributes:
        transfers_in: List of player IDs to bring in.
        transfers_out: List of player IDs to transfer out.
        current_squad: List of 15 player IDs in the current squad.
        bank: Available bank balance in 0.1m units.
    """

    transfers_in: list[int] = Field(min_length=1)
    transfers_out: list[int] = Field(min_length=1)
    current_squad: list[int] = Field(
        ...,
        min_length=15,
        max_length=15,
    )
    bank: int = Field(default=0, ge=0, le=500)


class TransferEvaluateResponse(BaseModel):
    """Response for transfer evaluation."""

    is_valid: bool
    cost: int
    budget_remaining: float
    expected_gain: float
    verdict: str
