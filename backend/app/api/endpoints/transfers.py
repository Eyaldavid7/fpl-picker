"""Transfer planning endpoints.

Provides:
- POST /recommend  -- single-GW transfer recommendations
- POST /plan       -- multi-GW rolling-horizon transfer plan
- POST /evaluate   -- evaluate a proposed set of transfers
- GET  /effective-ownership -- effective ownership for all players
"""

from fastapi import APIRouter, Query

from app.api.schemas.transfer import (
    TransferRecommendRequest,
    TransferRecommendResponse,
    TransferPlanRequest,
    TransferPlanResponse,
    TransferEvaluateRequest,
    TransferEvaluateResponse,
    TransferMove,
    GameweekPlan,
)
from app.transfers.engine import get_transfer_engine

router = APIRouter()


@router.post("/recommend", response_model=TransferRecommendResponse)
async def recommend_transfers(
    request: TransferRecommendRequest,
) -> TransferRecommendResponse:
    """Recommend best transfers for the current gameweek.

    Considers available budget, free transfers, and multi-GW horizon
    to suggest optimal transfer moves.
    """
    engine = get_transfer_engine()
    moves = engine.recommend_transfers(
        current_squad=request.current_squad,
        bank=request.bank,
        free_transfers=request.free_transfers,
        horizon=request.horizon,
        max_hits=request.max_hits,
        predicted_points=None,  # Would come from prediction engine in production
    )

    transfer_schemas = [
        TransferMove(
            player_in_id=m.player_in_id,
            player_out_id=m.player_out_id,
            cost_delta=m.cost_delta,
            expected_point_gain=m.expected_point_gain,
        )
        for m in moves
    ]

    total_gain = sum(m.expected_point_gain for m in moves)
    hits = max(0, len(moves) - request.free_transfers)
    hit_cost = hits * 4

    return TransferRecommendResponse(
        transfers=transfer_schemas,
        total_gain=round(total_gain, 2),
        hits_taken=hits,
        net_gain=round(total_gain - hit_cost, 2),
    )


@router.post("/plan", response_model=TransferPlanResponse)
async def plan_transfers(request: TransferPlanRequest) -> TransferPlanResponse:
    """Create multi-gameweek transfer plan with rolling horizon optimization.

    Accepts a squad and produces an optimal sequence of transfers over
    the specified horizon, accounting for free-transfer accumulation
    and hit penalties.
    """
    engine = get_transfer_engine()
    gw_plans = engine.create_multi_gw_plan(
        current_squad=request.current_squad,
        bank=request.bank,
        free_transfers=request.free_transfers,
        horizon=request.horizon,
        max_hits_per_gw=request.max_hits_per_gw or 1,
    )

    plan_schemas = [
        GameweekPlan(
            gameweek=gp.gameweek,
            transfers=[
                TransferMove(
                    player_in_id=t.player_in_id,
                    player_out_id=t.player_out_id,
                    cost_delta=t.cost_delta,
                    expected_point_gain=t.expected_point_gain,
                )
                for t in gp.transfers
            ],
            hits=gp.hits,
            expected_points=gp.expected_points,
        )
        for gp in gw_plans
    ]

    total_gain = sum(gp.expected_points for gp in gw_plans)
    total_hits = sum(gp.hits for gp in gw_plans)

    return TransferPlanResponse(
        gameweek_plans=plan_schemas,
        total_gain_over_horizon=round(total_gain, 2),
        total_hits=total_hits,
    )


@router.post("/evaluate", response_model=TransferEvaluateResponse)
async def evaluate_transfers(
    request: TransferEvaluateRequest,
) -> TransferEvaluateResponse:
    """Evaluate a proposed set of transfers and estimate point impact.

    Returns validity, budget impact, expected gain, and a human-readable
    verdict on whether the transfer is worthwhile.
    """
    engine = get_transfer_engine()
    result = engine.evaluate_transfers(
        transfers_in=request.transfers_in,
        transfers_out=request.transfers_out,
        current_squad=request.current_squad,
        bank=request.bank,
    )
    return TransferEvaluateResponse(
        is_valid=result["is_valid"],
        cost=result["cost"],
        budget_remaining=result["budget_remaining"],
        expected_gain=result["expected_gain"],
        verdict=result["verdict"],
    )


@router.get("/effective-ownership")
async def get_effective_ownership():
    """Return effective ownership for all players.

    Computes EO = ownership% + captaincy% and classifies players as
    differential (EO < 10%) or template (EO > 50%).

    In production this fetches live player data from the FPL API.
    Returns an empty list when no data is available.
    """
    engine = get_transfer_engine()

    # In production, fetch players from FPL client
    # For now, return empty list (will be populated when data layer is wired)
    try:
        from app.data.fpl_client import get_fpl_client
        client = get_fpl_client()
        players = await client.get_players()
        player_dicts = [
            {
                "id": p.id,
                "web_name": p.web_name,
                "selected_by_percent": p.selected_by_percent,
            }
            for p in players
        ]
        eo_results = engine.get_effective_ownership(players=player_dicts)
        return [eo.to_dict() for eo in eo_results]
    except Exception:
        return []
