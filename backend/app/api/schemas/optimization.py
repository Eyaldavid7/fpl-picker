"""Pydantic models for optimization-related API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.optimization.constraints import VALID_FORMATIONS


class SquadPlayer(BaseModel):
    """Player in an optimized squad result.

    Attributes:
        player_id: The FPL element ID.
        web_name: The player's display name.
        position: Position code (GK, DEF, MID, FWD).
        team_id: The team's numeric ID.
        cost: Player cost in 0.1m units.
        predicted_points: Predicted points for the target gameweek.
        is_starter: Whether the player is in the starting XI.
        is_captain: Whether the player is the captain.
        is_vice_captain: Whether the player is the vice-captain.
        next_opponent: Next fixture opponent, e.g. "Arsenal (A)" or "Chelsea (H)".
        fdr: Fixture Difficulty Rating 1-5 for the next match.
    """

    player_id: int
    web_name: str = ""
    position: str = ""
    team_id: int = 0
    cost: int = 0
    predicted_points: float = 0.0
    is_starter: bool = True
    is_captain: bool = False
    is_vice_captain: bool = False
    status: str = "a"  # a=available, d=doubtful, i=injured, s=suspended, u=unavailable
    chance_of_playing: int | None = None  # 0-100 or null
    news: str = ""  # Injury/availability news string
    next_opponent: str | None = None  # e.g. "Arsenal (A)" or "Chelsea (H)"
    fdr: int | None = None  # Fixture Difficulty Rating 1-5


class SquadOptimizationRequest(BaseModel):
    """Request body for squad optimization.

    Attributes:
        players: Raw player dicts from the FPL API.
        predictions: Mapping of player_id to predicted points.
        budget: Total budget in 0.1m units (500-1500, default 1000 = 100.0m).
        formation: Formation string such as '4-4-2'. None for flexible.
        method: Optimization method, either 'ilp' or 'ga'.
        locked_players: Player IDs that must be included in the squad.
        excluded_players: Player IDs that must not be included.
        gameweek: Target gameweek number (1-38).
        horizon: Planning horizon in gameweeks (1-10).
        objective: Optimization objective function name.

    Example:
        >>> request = SquadOptimizationRequest(
        ...     budget=1000,
        ...     formation="4-4-2",
        ...     method="ilp",
        ...     gameweek=28,
        ... )
    """

    players: list[dict[str, Any]] = []
    predictions: dict[int, float] = {}
    budget: int = Field(
        default=1000,
        ge=500,
        le=1500,
        description="Total budget in 0.1m units (e.g. 1000 = 100.0m)",
        json_schema_extra={"examples": [1000]},
    )
    formation: str | None = Field(
        default=None,
        description=f"Formation string. Valid: {', '.join(VALID_FORMATIONS)}",
        json_schema_extra={"examples": ["4-4-2"]},
    )
    method: str | None = Field(
        default="ilp",
        description="Optimization method: 'ilp' (exact) or 'ga' (heuristic)",
        json_schema_extra={"examples": ["ilp"]},
    )
    locked_players: list[int] = []
    excluded_players: list[int] = []
    gameweek: int = Field(
        default=1,
        ge=1,
        le=38,
        description="Target gameweek number (1-38)",
    )
    horizon: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Planning horizon in gameweeks",
    )
    objective: str = "maximize_points"

    @field_validator("formation")
    @classmethod
    def validate_formation(cls, v: str | None) -> str | None:
        """Validate that formation is one of the allowed formations.

        Args:
            v: The formation string to validate, or None.

        Returns:
            The validated formation string or None.

        Raises:
            ValueError: If the formation is not in VALID_FORMATIONS.
        """
        if v is not None and v not in VALID_FORMATIONS:
            raise ValueError(
                f"Invalid formation '{v}'. "
                f"Must be one of: {', '.join(VALID_FORMATIONS)}"
            )
        return v

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str | None) -> str | None:
        """Validate that method is either 'ilp' or 'ga'.

        Args:
            v: The method string to validate, or None.

        Returns:
            The validated method string or None.

        Raises:
            ValueError: If the method is not 'ilp' or 'ga'.
        """
        if v is not None and v not in ("ilp", "ga"):
            raise ValueError(f"Method must be 'ilp' or 'ga', got '{v}'")
        return v


class SquadOptimizationResponse(BaseModel):
    """Response for squad optimization."""

    squad: list[SquadPlayer]
    starting_xi: list[int]
    bench: list[int]
    captain_id: int | None
    vice_captain_id: int | None
    total_predicted_points: float
    total_cost: int
    method: str
    solve_time_ms: int
    formation: str = ""


class CaptainRequest(BaseModel):
    """Request body for captain selection.

    Attributes:
        player_ids: List of player IDs to consider for captaincy.
        gameweek: Target gameweek number (1-38). If omitted, defaults to next GW.
        differential: If True, prefer low-ownership captains (legacy, use mode instead).
        mode: Captain selection mode — "safe" | "differential" | "aggressive".
    """

    player_ids: list[int]
    gameweek: int | None = Field(default=None, ge=1, le=38)
    differential: bool = False
    mode: str = "safe"  # "safe" | "differential" | "aggressive"


class CaptainRanking(BaseModel):
    """Captain ranking entry with fixture context."""

    player_id: int
    web_name: str = ""
    position: str = ""
    team_name: str = ""
    predicted_points: float = 0.0
    effective_ownership: float = 0.0
    opponent: str = ""
    fdr: int | None = None
    reasoning: str = ""
    ceiling_score: float = 0.0


class CaptainResponse(BaseModel):
    """Response for captain selection."""

    captain_id: int
    vice_captain_id: int
    captain_xpts: float
    vice_captain_xpts: float
    rankings: list[CaptainRanking]


class BenchOrderRequest(BaseModel):
    """Request body for bench order optimization.

    Attributes:
        xi_ids: Starting XI player IDs (11 players).
        bench_ids: Bench player IDs (4 players).
        gameweek: Target gameweek number (1-38). If omitted, defaults to next GW.
    """

    xi_ids: list[int]
    bench_ids: list[int]
    gameweek: int | None = Field(default=None, ge=1, le=38)


class BenchPlayerDetail(BaseModel):
    """Bench player with scoring details."""

    player_id: int
    web_name: str = ""
    position: str = ""
    final_score: float = 0.0
    opponent: str = ""
    reasoning: str = ""


class BenchOrderResponse(BaseModel):
    """Response for bench order optimization."""

    bench_order: list[int]
    expected_auto_sub_points: float
    bench_players: list[BenchPlayerDetail] = []


class FormationRequest(BaseModel):
    """Request body for formation optimization.

    Attributes:
        player_ids: The 15 squad player IDs.
        gameweek: Target gameweek number (1-38).
    """

    player_ids: list[int]
    gameweek: int = Field(ge=1, le=38)


class FormationResponse(BaseModel):
    """Response for formation optimization."""

    formation: str
    starting_xi: list[int]
    bench: list[int]
    total_predicted_points: float


class SensitivityEntry(BaseModel):
    """Sensitivity analysis for a single player swap."""

    player_out_id: int
    player_in_id: int
    point_delta: float
    cost_delta: int


class SensitivityRequest(BaseModel):
    """Request body for sensitivity analysis.

    Attributes:
        squad_ids: The 15 squad player IDs to analyze.
        gameweek: Target gameweek number (1-38).
    """

    squad_ids: list[int]
    gameweek: int = Field(ge=1, le=38)


class SensitivityResponse(BaseModel):
    """Response for sensitivity analysis."""

    analyses: list[SensitivityEntry]
    gameweek: int


# ---------------------------------------------------------------------------
# Compare methods
# ---------------------------------------------------------------------------


class CompareRequest(BaseModel):
    """Request body for comparing ILP vs GA optimisation.

    Attributes:
        players: Raw player dicts from the FPL API.
        predictions: Mapping of player_id to predicted points.
        budget: Total budget in 0.1m units (500-1500).
        formation: Optional formation string.
    """

    players: list[dict[str, Any]]
    predictions: dict[int, float]
    budget: int = Field(
        default=1000,
        ge=500,
        le=1500,
        description="Total budget in 0.1m units",
    )
    formation: str | None = None

    @field_validator("formation")
    @classmethod
    def validate_formation(cls, v: str | None) -> str | None:
        """Validate formation string if provided.

        Args:
            v: The formation string to validate, or None.

        Returns:
            The validated formation string or None.

        Raises:
            ValueError: If the formation is not in VALID_FORMATIONS.
        """
        if v is not None and v not in VALID_FORMATIONS:
            raise ValueError(
                f"Invalid formation '{v}'. "
                f"Must be one of: {', '.join(VALID_FORMATIONS)}"
            )
        return v


class CompareSummary(BaseModel):
    """Summary stats when comparing ILP vs GA."""

    ilp_points: float = 0.0
    ga_points: float = 0.0
    point_difference: float = 0.0
    ilp_solve_time: float = 0.0
    ga_solve_time: float = 0.0
    ilp_cost: float = 0.0
    ga_cost: float = 0.0
    ilp_formation: str = ""
    ga_formation: str = ""


class CompareResponse(BaseModel):
    """Response for the compare endpoint."""

    ilp: dict[str, Any] = {}
    ga: dict[str, Any] = {}
    summary: CompareSummary = CompareSummary()
