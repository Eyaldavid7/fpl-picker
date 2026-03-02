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
