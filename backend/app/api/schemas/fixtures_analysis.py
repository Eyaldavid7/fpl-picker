"""Pydantic models for fixtures-analysis API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SquadFixturesRequest(BaseModel):
    """Request body for squad fixtures analysis.

    Attributes:
        player_ids: List of FPL player element IDs to look up fixtures for.
        num_gameweeks: Number of upcoming gameweeks to include (1-10, default 5).
    """

    player_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=25,
        description="List of FPL player element IDs",
        json_schema_extra={"examples": [[1, 2, 3]]},
    )
    num_gameweeks: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of upcoming gameweeks to include (1-10)",
    )


class PlayerFixtureItem(BaseModel):
    """A single upcoming fixture for a player.

    Attributes:
        gameweek: The gameweek (event) number.
        opponent_team_id: The opponent team's numeric ID.
        opponent_name: Full name of the opponent team.
        opponent_short_name: Three-letter short name (e.g. 'ARS').
        is_home: Whether the player's team plays at home.
        difficulty: FDR rating 1-5 for this fixture from the player's perspective.
        kickoff_time: ISO-8601 kickoff datetime string, if available.
    """

    gameweek: int
    opponent_team_id: int
    opponent_name: str
    opponent_short_name: str
    is_home: bool
    difficulty: int
    kickoff_time: str | None = None


class TeamInfo(BaseModel):
    """Minimal team info for the teams lookup dict.

    Attributes:
        name: Full team name.
        short_name: Three-letter abbreviation.
    """

    name: str
    short_name: str


class SquadFixturesResponse(BaseModel):
    """Response for squad fixtures analysis.

    Attributes:
        fixtures: Mapping of player_id (as string key) to list of upcoming fixtures.
        teams: Mapping of team_id (as string key) to team info.
        current_gameweek: The current gameweek number used as the baseline.
    """

    fixtures: dict[str, list[PlayerFixtureItem]]
    teams: dict[str, TeamInfo]
    current_gameweek: int
