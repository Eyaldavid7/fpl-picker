"""Optimization endpoints for squad selection, captain, bench, and formation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.optimization import (
    BenchOrderRequest,
    BenchOrderResponse,
    CaptainRequest,
    CaptainResponse,
    FormationRequest,
    FormationResponse,
    SensitivityRequest,
    SensitivityResponse,
    SquadOptimizationRequest,
    SquadOptimizationResponse,
    SquadPlayer,
    CompareRequest,
    CompareResponse,
)
from app.optimization.engine import OptimizationEngine
from app.optimization.models import OptimizationResult

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton engine instance (stateless, so safe to share)
_engine = OptimizationEngine()

# Map FPL element_type to position string the solver understands
_ELEMENT_TYPE_TO_POS: dict[int, str] = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player_dict_to_squad_player(
    p: dict,
    is_starter: bool,
    is_captain: bool,
    is_vice: bool,
    pred: float,
) -> SquadPlayer:
    """Convert a raw player dict to the API response model."""
    return SquadPlayer(
        player_id=p.get("id", 0),
        web_name=p.get("web_name", ""),
        position=p.get("position", ""),
        team_id=p.get("team") or p.get("team_id") or 0,
        cost=p.get("now_cost", 0),
        predicted_points=pred,
        is_starter=is_starter,
        is_captain=is_captain,
        is_vice_captain=is_vice,
        status=p.get("status", "a"),
        chance_of_playing=p.get("chance_of_playing"),
        news=p.get("news", ""),
    )


def _result_to_response(
    result: OptimizationResult,
    predictions: dict[int, float],
) -> SquadOptimizationResponse:
    """Map an OptimizationResult to the API response schema."""
    captain_id = result.captain["id"] if result.captain else None
    vc_id = result.vice_captain["id"] if result.vice_captain else None

    squad_players: list[SquadPlayer] = []
    xi_ids = {p["id"] for p in result.starting_xi}
    for p in result.squad:
        pid = p["id"]
        squad_players.append(
            _player_dict_to_squad_player(
                p,
                is_starter=pid in xi_ids,
                is_captain=pid == captain_id,
                is_vice=pid == vc_id,
                pred=predictions.get(pid, 0.0),
            )
        )

    return SquadOptimizationResponse(
        squad=squad_players,
        starting_xi=[p["id"] for p in result.starting_xi],
        bench=[p["id"] for p in result.bench],
        captain_id=captain_id,
        vice_captain_id=vc_id,
        total_predicted_points=result.predicted_points,
        total_cost=int(result.total_cost * 10),  # back to 0.1m units
        method=result.method,
        solve_time_ms=int(result.solve_time * 1000),
        formation=result.formation,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/squad", response_model=SquadOptimizationResponse)
async def optimize_squad(
    request: SquadOptimizationRequest,
) -> SquadOptimizationResponse:
    """Select optimal 15-player squad using ILP or GA solver.

    Maximizes expected points subject to FPL constraints:
    budget, formation, max 3 per club, position limits.

    If ``players`` and ``predictions`` are omitted, the endpoint fetches
    live data from the FPL API and uses each player's *form* stat
    (average points over the last ~5 gameweeks) as the prediction.
    """
    players = request.players
    predictions = request.predictions

    if not players or not predictions:
        # Auto-fetch live FPL data
        from app.data.fpl_client import get_fpl_client

        client = get_fpl_client()
        try:
            bootstrap = await client.get_bootstrap()
        except Exception as exc:
            logger.error("Failed to fetch FPL data: %s", exc)
            raise HTTPException(
                status_code=502,
                detail=f"Could not fetch live FPL data: {exc}",
            )

        raw_elements = bootstrap.get("elements", [])
        players = []
        predictions = {}

        for el in raw_elements:
            # Skip injured / suspended / unavailable players
            status = el.get("status", "a")
            if status in ("i", "s", "u"):
                continue
            # Skip players with 0 minutes (haven't played)
            if (el.get("minutes") or 0) == 0:
                continue
            # Skip players unlikely to play next round
            chance = el.get("chance_of_playing_next_round")
            if chance is not None and chance < 50:
                continue

            pid = el["id"]
            # Build a clean player dict for the solver (don't mutate cache)
            player = {
                "id": pid,
                "web_name": el.get("web_name", ""),
                "position": _ELEMENT_TYPE_TO_POS.get(
                    el.get("element_type", 3), "MID"
                ),
                "now_cost": el.get("now_cost", 0),
                "team": el.get("team", 0),
                "team_id": el.get("team", 0),
                "status": status,
                "chance_of_playing": chance,
                "news": el.get("news", ""),
            }
            players.append(player)

            # Use 'form' as predicted points; fall back to points_per_game
            form = float(el.get("form") or 0)
            ppg = float(el.get("points_per_game") or 0)
            pred = form if form > 0 else ppg

            # Discount prediction for doubtful players (75% chance = 75% of pts)
            if chance is not None and chance < 100:
                pred = round(pred * (chance / 100), 2)

            predictions[pid] = pred

        logger.info(
            "Auto-fetched %d eligible players from FPL API", len(players)
        )

    budget = request.budget / 10.0  # 0.1m units -> real money
    method = (request.method or "ilp").lower()

    try:
        result = _engine.optimize(
            players=players,
            predictions=predictions,
            method=method,
            budget=budget,
            formation=request.formation,
            locked_players=request.locked_players,
            excluded_players=request.excluded_players,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # For GA, take the best result
    if isinstance(result, list):
        if not result or not result[0].squad:
            raise HTTPException(
                status_code=422,
                detail="Optimisation produced no result. The budget or constraints may be too restrictive to form a valid squad.",
            )
        result = result[0]

    if not result.squad:
        raise HTTPException(
            status_code=422,
            detail="Optimisation produced no result. The budget or constraints may be too restrictive to form a valid squad.",
        )

    return _result_to_response(result, predictions)


@router.get("/formations")
async def list_formations() -> dict:
    """Return all valid FPL formations."""
    return {"formations": _engine.get_available_formations()}


@router.post("/compare", response_model=CompareResponse)
async def compare_methods(request: CompareRequest) -> CompareResponse:
    """Run both ILP and GA solvers and compare results."""
    if not request.players:
        raise HTTPException(status_code=400, detail="'players' list is required.")
    if not request.predictions:
        raise HTTPException(status_code=400, detail="'predictions' map is required.")

    budget = request.budget / 10.0
    comparison = _engine.compare_methods(
        players=request.players,
        predictions=request.predictions,
        budget=budget,
        formation=request.formation,
    )
    return CompareResponse(**comparison)


# ---------------------------------------------------------------------------
# Existing stubs (kept for backward compatibility)
# ---------------------------------------------------------------------------

@router.post("/captain", response_model=CaptainResponse)
async def select_captain(request: CaptainRequest) -> CaptainResponse:
    """Select optimal captain and vice-captain from given XI."""
    # TODO: Implement with CaptainSelector
    return CaptainResponse(
        captain_id=0,
        vice_captain_id=0,
        captain_xpts=0.0,
        vice_captain_xpts=0.0,
        rankings=[],
    )


@router.post("/bench", response_model=BenchOrderResponse)
async def optimize_bench(request: BenchOrderRequest) -> BenchOrderResponse:
    """Optimize bench order given starting XI and substitutes."""
    # TODO: Implement with BenchOptimizer
    return BenchOrderResponse(
        bench_order=request.bench_ids,
        expected_auto_sub_points=0.0,
    )


@router.post("/formation", response_model=FormationResponse)
async def optimize_formation(request: FormationRequest) -> FormationResponse:
    """Find optimal formation for a given squad."""
    # TODO: Implement
    return FormationResponse(
        formation="3-4-3",
        starting_xi=[],
        bench=[],
        total_predicted_points=0.0,
    )


@router.post("/sensitivity", response_model=SensitivityResponse)
async def sensitivity_analysis(request: SensitivityRequest) -> SensitivityResponse:
    """Analyze how much each swap would affect total expected points."""
    # TODO: Implement
    return SensitivityResponse(
        analyses=[],
        gameweek=request.gameweek,
    )
