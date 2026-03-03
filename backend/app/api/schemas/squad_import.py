"""Schemas for screenshot-based squad import."""

from pydantic import BaseModel


class MatchedPlayer(BaseModel):
    """A player extracted from a screenshot and matched to FPL data."""

    extracted_name: str
    player_id: int | None = None
    web_name: str | None = None
    position: str | None = None
    team_name: str | None = None
    confidence: float = 0.0


class ScreenshotImportResponse(BaseModel):
    """Response from the screenshot import endpoint."""

    players: list[MatchedPlayer]
    extracted_count: int
    matched_count: int


# ---------------------------------------------------------------------------
# Team-ID import schemas
# ---------------------------------------------------------------------------


class TeamIdImportRequest(BaseModel):
    """Request body for importing a squad by FPL team ID."""

    team_id: int


class TeamIdImportResult(BaseModel):
    """Response from the team-ID import endpoint."""

    team_name: str
    manager_name: str
    gameweek: int
    players: list[MatchedPlayer]
    starting_xi: list[int]
    bench: list[int]
    captain_id: int | None = None
    vice_captain_id: int | None = None
    overall_points: int
    overall_rank: int
    bank: float
    team_value: float
