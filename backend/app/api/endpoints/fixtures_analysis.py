"""Fixtures analysis endpoints for squad opponent lookup."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.fixtures_analysis import (
    PlayerFixtureItem,
    SquadFixturesRequest,
    SquadFixturesResponse,
    TeamInfo,
)
from app.data.fpl_client import get_fpl_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/squad-fixtures", response_model=SquadFixturesResponse)
async def get_squad_fixtures(
    request: SquadFixturesRequest,
) -> SquadFixturesResponse:
    """Return upcoming fixtures for each player in the provided list.

    For every player ID, the endpoint resolves the player's team and then
    finds the next *N* gameweek fixtures for that team.  Each fixture
    entry includes the opponent name, whether the match is home/away, and
    the FPL Fixture Difficulty Rating (FDR).

    Args:
        request: The request body containing player IDs and gameweek horizon.

    Returns:
        A response containing per-player fixture lists and a teams lookup.

    Raises:
        HTTPException 502: If the upstream FPL API is unreachable.
        HTTPException 404: If any requested player ID is not found.
    """
    client = get_fpl_client()

    # ------------------------------------------------------------------
    # Fetch all required data from the FPL API (uses cache internally)
    # ------------------------------------------------------------------
    try:
        players = await client.get_players()
        fixtures = await client.get_typed_fixtures()
        teams = await client.get_teams()
        current_gw_info = await client.get_current_gameweek_info()
    except Exception as exc:
        logger.error("Failed to fetch FPL data: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch live FPL data: {exc}",
        )

    current_gw: int = current_gw_info.id if current_gw_info else 1

    # ------------------------------------------------------------------
    # Build lookup dicts
    # ------------------------------------------------------------------

    # player_id -> team_id
    player_team_map: dict[int, int] = {p.id: p.team for p in players}

    # team_id -> Team model
    team_map: dict[int, object] = {t.id: t for t in teams}

    # ------------------------------------------------------------------
    # Pre-filter fixtures to only future gameweeks within the horizon
    # ------------------------------------------------------------------
    max_gw = current_gw + request.num_gameweeks
    future_fixtures = [
        f
        for f in fixtures
        if f.event is not None and f.event > current_gw and f.event <= max_gw
    ]

    # Group fixtures by team_id for efficient lookup.
    # A team can appear as either team_h or team_a in a fixture.
    team_fixtures: dict[int, list] = {}
    for fx in future_fixtures:
        team_fixtures.setdefault(fx.team_h, []).append(fx)
        team_fixtures.setdefault(fx.team_a, []).append(fx)

    # ------------------------------------------------------------------
    # Build per-player fixture lists
    # ------------------------------------------------------------------
    result_fixtures: dict[str, list[PlayerFixtureItem]] = {}
    missing_ids: list[int] = []

    for pid in request.player_ids:
        team_id = player_team_map.get(pid)
        if team_id is None:
            missing_ids.append(pid)
            continue

        player_fxs = team_fixtures.get(team_id, [])
        # Sort by gameweek so they appear in chronological order
        player_fxs.sort(key=lambda f: (f.event, f.kickoff_time or ""))

        items: list[PlayerFixtureItem] = []
        for fx in player_fxs:
            is_home = fx.team_h == team_id
            opponent_id = fx.team_a if is_home else fx.team_h
            difficulty = fx.team_h_difficulty if is_home else fx.team_a_difficulty

            opp_team = team_map.get(opponent_id)
            opponent_name = opp_team.name if opp_team else f"Team {opponent_id}"
            opponent_short = opp_team.short_name if opp_team else "???"

            items.append(
                PlayerFixtureItem(
                    gameweek=fx.event,
                    opponent_team_id=opponent_id,
                    opponent_name=opponent_name,
                    opponent_short_name=opponent_short,
                    is_home=is_home,
                    difficulty=difficulty,
                    kickoff_time=fx.kickoff_time,
                )
            )

        result_fixtures[str(pid)] = items

    if missing_ids:
        logger.warning("Player IDs not found in FPL data: %s", missing_ids)

    # ------------------------------------------------------------------
    # Build teams lookup dict
    # ------------------------------------------------------------------
    teams_lookup: dict[str, TeamInfo] = {
        str(t.id): TeamInfo(name=t.name, short_name=t.short_name)
        for t in teams
    }

    return SquadFixturesResponse(
        fixtures=result_fixtures,
        teams=teams_lookup,
        current_gameweek=current_gw,
    )
