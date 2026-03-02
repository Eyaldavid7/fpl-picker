"""Data endpoints for player data, fixtures, teams, and gameweeks.

All endpoints proxy data from the FPL API via the ``FPLClient``, with
caching and optional derived-feature enrichment through the preprocessing
layer.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas.player import PlayerDetailResponse, PlayerListResponse, PlayerSummary
from app.data.fpl_client import get_fpl_client
from app.data.models import (
    Fixture,
    Gameweek,
    Player,
    PlayerHistory,
    Team,
)
from app.data.preprocessing import calculate_derived_features

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player_to_summary(player: Player) -> dict:
    """Convert a ``Player`` model to a dict matching ``PlayerSummary``."""
    return {
        "id": player.id,
        "web_name": player.web_name,
        "first_name": player.first_name,
        "second_name": player.second_name,
        "team": player.team,
        "team_id": player.team,
        "position": player.position.value,
        "now_cost": player.now_cost,
        "total_points": player.total_points,
        "form": player.form,
        "points_per_game": player.points_per_game,
        "selected_by_percent": player.selected_by_percent,
        "ict_index": player.ict_index,
        "minutes": player.minutes,
        "goals_scored": player.goals_scored,
        "assists": player.assists,
        "clean_sheets": player.clean_sheets,
        "bonus": player.bonus,
        "bps": player.bps,
        "expected_goals": player.expected_goals,
        "expected_assists": player.expected_assists,
        "expected_goal_involvements": player.expected_goal_involvements,
        "expected_goals_conceded": player.expected_goals_conceded,
        "transfers_in_event": player.transfers_in_event,
        "transfers_out_event": player.transfers_out_event,
        "chance_of_playing_next_round": player.chance_of_playing_next_round,
        "value_season": player.value_season,
        "status": player.status,
        "news": player.news,
        "points_per_million": player.points_per_million,
        "xgi_per_90": player.xgi_per_90,
    }


# ---------------------------------------------------------------------------
# GET /api/data/players
# ---------------------------------------------------------------------------

@router.get("/players", response_model=PlayerListResponse)
async def get_players(
    position: str | None = Query(None, description="Filter by position: GKP, DEF, MID, FWD"),
    team: int | None = Query(None, description="Filter by team ID"),
    min_price: float | None = Query(None, description="Minimum price (in millions)"),
    max_price: float | None = Query(None, description="Maximum price (in millions)"),
    sort_by: str = Query("total_points", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=500, description="Results per page"),
) -> PlayerListResponse:
    """Get all players with current stats and derived features.

    Supports filtering by position, team, and price range, plus
    pagination and sorting.
    """
    client = get_fpl_client()
    players: list[Player] = await client.get_players()

    # Enrich with derived features
    for p in players:
        calculate_derived_features(p)

    # ------ Filters ------
    filtered: list[Player] = []
    for p in players:
        if position and p.position.value != position.upper():
            continue
        if team and p.team != team:
            continue
        price_m = p.now_cost / 10.0
        if min_price is not None and price_m < min_price:
            continue
        if max_price is not None and price_m > max_price:
            continue
        filtered.append(p)

    # ------ Sort ------
    reverse = order.lower() == "desc"

    def _sort_key(p: Player) -> float:
        val = getattr(p, sort_by, 0)
        if val is None:
            return 0.0
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    filtered.sort(key=_sort_key, reverse=reverse)

    # ------ Paginate ------
    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    page_items = filtered[start:end]

    return PlayerListResponse(
        players=[_player_to_summary(p) for p in page_items],
        total=total,
        page=page,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /api/data/players/{player_id}
# ---------------------------------------------------------------------------

@router.get("/players/{player_id}", response_model=PlayerDetailResponse)
async def get_player(player_id: int) -> PlayerDetailResponse:
    """Get detailed player profile with historical gameweek data."""
    client = get_fpl_client()

    player = await client.get_player_by_id(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    # Fetch history
    summary = await client.get_player_summary(player_id)
    history_raw: list[dict] = summary.get("history", [])
    history: list[PlayerHistory] = [
        PlayerHistory.from_api_history(h) for h in history_raw
    ]

    # Enrich with derived features (including history-based form)
    calculate_derived_features(player, history)

    data = _player_to_summary(player)
    data["history"] = history_raw
    data["fixtures"] = summary.get("fixtures", [])

    return PlayerDetailResponse(**data)


# ---------------------------------------------------------------------------
# GET /api/data/teams
# ---------------------------------------------------------------------------

@router.get("/teams")
async def get_teams() -> dict:
    """Get all Premier League teams with strength ratings."""
    client = get_fpl_client()
    teams: list[Team] = await client.get_teams()
    return {"teams": [t.model_dump() for t in teams]}


# ---------------------------------------------------------------------------
# GET /api/data/fixtures
# ---------------------------------------------------------------------------

@router.get("/fixtures")
async def get_fixtures(
    gameweek: int | None = Query(None, description="Filter by gameweek"),
) -> dict:
    """Get fixtures with Fixture Difficulty Rating, optionally by gameweek."""
    client = get_fpl_client()
    fixtures: list[Fixture] = await client.get_typed_fixtures(gameweek=gameweek)
    return {"fixtures": [f.model_dump() for f in fixtures]}


# ---------------------------------------------------------------------------
# GET /api/data/gameweeks/current
# ---------------------------------------------------------------------------

@router.get("/gameweeks/current")
async def get_current_gameweek() -> dict:
    """Get the current gameweek info."""
    client = get_fpl_client()
    gw: Gameweek | None = await client.get_current_gameweek_info()
    if gw is None:
        raise HTTPException(status_code=404, detail="No current gameweek found")
    return {"gameweek": gw.model_dump()}


# ---------------------------------------------------------------------------
# GET /api/data/gameweeks
# ---------------------------------------------------------------------------

@router.get("/gameweeks")
async def get_gameweeks() -> dict:
    """Get all gameweeks with deadlines and scores."""
    client = get_fpl_client()
    gameweeks: list[Gameweek] = await client.get_gameweeks()
    return {"gameweeks": [gw.model_dump() for gw in gameweeks]}


# ---------------------------------------------------------------------------
# GET /api/data/live/{gameweek}
# ---------------------------------------------------------------------------

@router.get("/live/{gameweek}")
async def get_live_gameweek(gameweek: int) -> dict:
    """Get live gameweek scores (during matches)."""
    client = get_fpl_client()
    live_data = await client.get_live_gameweek(gameweek)
    return {"gameweek": gameweek, "elements": live_data.get("elements", [])}


# ---------------------------------------------------------------------------
# POST /api/data/refresh
# ---------------------------------------------------------------------------

@router.post("/refresh")
async def refresh_data() -> dict:
    """Force-refresh cached FPL data."""
    client = get_fpl_client()
    client.cache.invalidate_all()
    await client.get_bootstrap()
    return {"status": "refreshed"}
