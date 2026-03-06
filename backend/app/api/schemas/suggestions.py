"""Schemas for team suggestion endpoints (substitutes & transfers)."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Substitute suggestions
# ---------------------------------------------------------------------------


class SubstituteSuggestion(BaseModel):
    """A single bench-to-starter swap recommendation."""

    bench_player_id: int
    bench_player_name: str
    bench_player_position: str
    bench_predicted_points: float
    bench_next_opponent: str | None = None  # e.g. "Arsenal (A)"
    bench_fdr: int | None = None  # Fixture Difficulty Rating 1-5
    starter_player_id: int
    starter_player_name: str
    starter_player_position: str
    starter_predicted_points: float
    starter_next_opponent: str | None = None
    starter_fdr: int | None = None
    point_gain: float
    reason: str


class SubstituteRequest(BaseModel):
    """Request body for substitute suggestions."""

    squad_player_ids: list[int] = Field(..., min_length=11, max_length=15)
    formation: str = "4-4-2"


class SquadPlayerFixture(BaseModel):
    """Next-fixture context for a single squad player."""

    player_id: int
    web_name: str
    position: str
    is_starter: bool
    predicted_points: float
    next_opponent: str | None = None  # e.g. "Arsenal (A)"
    fdr: int | None = None  # Fixture Difficulty Rating 1-5


class SubstituteResponse(BaseModel):
    """Response containing ordered substitute swap suggestions."""

    suggestions: list[SubstituteSuggestion]
    squad_fixtures: list[SquadPlayerFixture] = []


# ---------------------------------------------------------------------------
# Transfer suggestions
# ---------------------------------------------------------------------------


class TransferSuggestion(BaseModel):
    """A single player-out / player-in transfer recommendation."""

    player_out_id: int
    player_out_name: str
    player_out_position: str
    player_out_price: int  # now_cost format (price * 10)
    player_out_predicted: float
    player_in_id: int
    player_in_name: str
    player_in_position: str
    player_in_price: int
    player_in_predicted: float
    player_in_team: str
    point_gain: float
    net_cost: int  # player_in_price - player_out_price
    reason: str
    is_hit: bool = False
    hit_cost: int = 0  # 0 for free transfers, 4 for hits
    net_gain_after_hit: float = 0.0


class TransferRequest(BaseModel):
    """Request body for transfer suggestions."""

    squad_player_ids: list[int] = Field(..., min_length=11, max_length=15)
    budget_remaining: int = Field(
        default=0,
        description="Budget remaining in now_cost format (price * 10)",
    )
    free_transfers: int = Field(default=1, ge=1, le=5)


class TransferResponse(BaseModel):
    """Response containing ranked transfer suggestions."""

    suggestions: list[TransferSuggestion]
    total_point_gain: float
    total_cost_change: int
    transfers_used: int
    hit_transfers_count: int = 0
    total_hit_cost: int = 0
    net_gain_after_hits: float = 0.0
