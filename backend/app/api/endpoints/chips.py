"""Chip strategy endpoints.

Provides:
- POST /strategy  -- recommend optimal chip timing
- POST /simulate  -- simulate chip usage for a specific GW
"""

from fastapi import APIRouter

from app.api.schemas.chip import (
    ChipStrategyRequest,
    ChipStrategyResponse,
    ChipSimulateRequest,
    ChipSimulateResponse,
    ChipRecommendation,
)
from app.transfers.engine import get_transfer_engine

router = APIRouter()


@router.post("/strategy", response_model=ChipStrategyResponse)
async def chip_strategy(request: ChipStrategyRequest) -> ChipStrategyResponse:
    """Recommend optimal chip usage over remaining gameweeks.

    Analyzes fixture difficulty, double gameweeks, and team form
    to suggest when to deploy each available chip.

    Requires:
    - current_squad: 15 player IDs
    - available_chips: list of chip names still available
    - current_gw: current gameweek number

    In production, predictions_by_gw would be fetched from the
    prediction engine.  When unavailable, returns a summary noting
    that predictions are needed.
    """
    engine = get_transfer_engine()

    # In production, build predictions_by_gw from PredictionEngine
    # For now, try to build a minimal predictions dict
    try:
        from app.data.fpl_client import get_fpl_client
        from app.prediction.engine import get_prediction_engine

        get_fpl_client()
        pred_engine = get_prediction_engine()

        # Build predictions for upcoming GWs
        predictions_by_gw: dict[int, dict[int, float]] = {}
        for gw_offset in range(6):
            gw = request.current_gw + gw_offset
            results = await pred_engine.predict_all_players(
                gameweek=gw, player_ids=request.current_squad
            )
            predictions_by_gw[gw] = {
                r.player_id: r.predicted_points for r in results
            }

        recommendations = engine.recommend_chips(
            squad=request.current_squad,
            predictions_by_gw=predictions_by_gw,
            chips_available=request.available_chips,
        )

        rec_schemas = [
            ChipRecommendation(
                chip=r.chip_type.value,
                recommended_gameweek=r.recommended_gameweek,
                expected_gain=r.expected_value,
                reasoning=r.reasoning,
            )
            for r in recommendations
        ]

        return ChipStrategyResponse(
            recommendations=rec_schemas,
            analysis_summary=(
                f"Analyzed {len(request.available_chips)} chips across "
                f"GW{request.current_gw}-GW{request.current_gw + 5}. "
                f"Top recommendation: {rec_schemas[0].chip} in GW{rec_schemas[0].recommended_gameweek}"
                if rec_schemas
                else "No chip recommendations available"
            ),
        )
    except Exception as exc:
        # Graceful fallback: return empty recommendations
        return ChipStrategyResponse(
            recommendations=[],
            analysis_summary=(
                f"Chip strategy requires prediction data. "
                f"Available chips: {', '.join(request.available_chips)}. "
                f"Error: {str(exc)}"
            ),
        )


@router.post("/simulate", response_model=ChipSimulateResponse)
async def simulate_chip(request: ChipSimulateRequest) -> ChipSimulateResponse:
    """Simulate using a specific chip in a specific gameweek.

    Returns the projected point impact of using the chip vs. not using it.
    """
    engine = get_transfer_engine()

    try:
        from app.prediction.engine import get_prediction_engine

        pred_engine = get_prediction_engine()

        # Get predictions for the target GW
        results = await pred_engine.predict_all_players(
            gameweek=request.gameweek, player_ids=request.current_squad
        )
        predictions_by_gw = {
            request.gameweek: {r.player_id: r.predicted_points for r in results}
        }

        sim = engine.simulate_chip(
            chip_type=request.chip,
            gameweek=request.gameweek,
            squad=request.current_squad,
            predictions_by_gw=predictions_by_gw,
        )

        return ChipSimulateResponse(
            chip=sim["chip"],
            gameweek=sim["gameweek"],
            projected_points_with_chip=sim["projected_points_with_chip"],
            projected_points_without_chip=sim["projected_points_without_chip"],
            point_delta=sim["point_delta"],
            recommended_squad=request.current_squad,
        )
    except Exception:
        return ChipSimulateResponse(
            chip=request.chip,
            gameweek=request.gameweek,
            projected_points_with_chip=0.0,
            projected_points_without_chip=0.0,
            point_delta=0.0,
            recommended_squad=request.current_squad,
        )
