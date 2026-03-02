"""Pydantic models for chip strategy API schemas."""

from typing import Literal

from pydantic import BaseModel


ChipType = Literal["wildcard", "triple_captain", "bench_boost", "free_hit"]


class ChipRecommendation(BaseModel):
    """Recommendation for when to use a specific chip."""

    chip: str
    recommended_gameweek: int
    expected_gain: float = 0.0
    reasoning: str = ""
    confidence: float = 0.0


class ChipStrategyRequest(BaseModel):
    """Request body for chip strategy recommendations."""

    current_squad: list[int]
    available_chips: list[str]
    current_gw: int
    bank: int = 0
    free_transfers: int = 1


class ChipStrategyResponse(BaseModel):
    """Response for chip strategy recommendations."""

    recommendations: list[ChipRecommendation]
    analysis_summary: str


class ChipSimulateRequest(BaseModel):
    """Request body for chip simulation."""

    chip: ChipType
    gameweek: int
    current_squad: list[int]


class ChipSimulateResponse(BaseModel):
    """Response for chip simulation."""

    chip: str
    gameweek: int
    projected_points_with_chip: float
    projected_points_without_chip: float
    point_delta: float
    recommended_squad: list[int]
