"""Prediction endpoints for player point forecasts.

Provides four main endpoints:
- POST /api/predict/points   -- predict points for next GW (with optional model selection)
- GET  /api/predict/players/{player_id} -- per-player prediction with model breakdown
- GET  /api/predict/models   -- list available models with descriptions
- POST /api/predict/compare  -- compare model predictions side by side
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.prediction import (
    BacktestRequest,
    BacktestResponse,
    BatchPredictRequest,
    BatchPredictResponse,
    CompareModelsRequest,
    CompareModelsResponse,
    ModelBreakdown,
    ModelInfo,
    ModelListResponse,
    PlayerPredictionResponse,
    PointPrediction,
    PredictPointsRequest,
    PredictPointsResponse,
)
from app.prediction.engine import get_prediction_engine

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/predict/points
# ---------------------------------------------------------------------------

@router.post("/points", response_model=PredictPointsResponse)
async def predict_points(request: PredictPointsRequest) -> PredictPointsResponse:
    """Predict expected points for specified players across gameweeks.

    Uses the selected model (default: ensemble) to generate point forecasts
    with confidence intervals.  If ``player_ids`` is omitted, predictions
    are generated for all available players.
    """
    engine = get_prediction_engine()
    model_name = request.model or "ensemble"
    predictions: list[PointPrediction] = []

    for gw in request.gameweeks:
        if request.player_ids:
            for pid in request.player_ids:
                try:
                    result = await engine.predict_player(
                        player_id=pid,
                        gameweek=gw,
                        model=model_name if model_name != "ensemble" else None,
                    )
                    predictions.append(
                        PointPrediction(
                            player_id=result.player_id,
                            gameweek=result.gameweek,
                            predicted_points=round(result.predicted_points, 2),
                            confidence_lower=round(result.confidence_lower, 2),
                            confidence_upper=round(result.confidence_upper, 2),
                            model=result.model_name or model_name,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "Prediction failed for player %d GW%d: %s",
                        pid, gw, exc,
                    )
        else:
            # Predict all players for this gameweek
            try:
                results = await engine.predict_all_players(gw)
                for result in results:
                    predictions.append(
                        PointPrediction(
                            player_id=result.player_id,
                            gameweek=result.gameweek,
                            predicted_points=round(result.predicted_points, 2),
                            confidence_lower=round(result.confidence_lower, 2),
                            confidence_upper=round(result.confidence_upper, 2),
                            model=result.model_name or model_name,
                        )
                    )
            except Exception as exc:
                logger.error("Batch prediction failed for GW%d: %s", gw, exc)

    return PredictPointsResponse(
        predictions=predictions,
        model=model_name,
        gameweeks=request.gameweeks,
    )


# ---------------------------------------------------------------------------
# GET /api/predict/players/{player_id}
# ---------------------------------------------------------------------------

@router.get(
    "/players/{player_id}",
    response_model=PlayerPredictionResponse,
)
async def get_player_predictions(player_id: int) -> PlayerPredictionResponse:
    """Get the ensemble prediction for a single player with per-model breakdown.

    Predicts for the next gameweek (determined from FPL API).
    """
    engine = get_prediction_engine()

    # Determine next gameweek
    try:
        from app.data.fpl_client import get_fpl_client

        client = get_fpl_client()
        current_gw = await client.get_current_gameweek()
        next_gw = current_gw + 1
    except Exception:
        next_gw = 1

    try:
        result = await engine.predict_player(player_id, next_gw)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed for player {player_id}: {exc}",
        )

    return PlayerPredictionResponse(
        player_id=result.player_id,
        gameweek=result.gameweek,
        ensemble_prediction=round(result.predicted_points, 2),
        confidence_lower=round(result.confidence_lower, 2),
        confidence_upper=round(result.confidence_upper, 2),
        model_breakdown={
            name: round(val, 2)
            for name, val in result.model_breakdown.items()
        },
    )


# ---------------------------------------------------------------------------
# GET /api/predict/models
# ---------------------------------------------------------------------------

@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """List all registered prediction models with descriptions and weights."""
    engine = get_prediction_engine()
    models = engine.available_models()
    return ModelListResponse(
        models=[
            ModelInfo(
                name=m["name"],
                type=m["type"],
                description=m["description"],
                weight=m["weight"],
            )
            for m in models
        ]
    )


# ---------------------------------------------------------------------------
# POST /api/predict/compare
# ---------------------------------------------------------------------------

@router.post("/compare", response_model=CompareModelsResponse)
async def compare_models(request: CompareModelsRequest) -> CompareModelsResponse:
    """Compare per-model predictions for one or more players side-by-side."""
    engine = get_prediction_engine()
    comparisons: list[ModelBreakdown] = []

    for pid in request.player_ids:
        try:
            breakdown = await engine.compare_models(pid, request.gameweek)
            comparisons.append(
                ModelBreakdown(
                    player_id=pid,
                    gameweek=request.gameweek,
                    predictions={
                        name: round(val, 2)
                        for name, val in breakdown.items()
                    },
                )
            )
        except Exception as exc:
            logger.warning(
                "Model comparison failed for player %d: %s", pid, exc,
            )

    return CompareModelsResponse(
        comparisons=comparisons,
        gameweek=request.gameweek,
    )


# ---------------------------------------------------------------------------
# POST /api/predict/batch  (kept for backwards compatibility)
# ---------------------------------------------------------------------------

@router.post("/batch", response_model=BatchPredictResponse)
async def batch_predict(request: BatchPredictRequest) -> BatchPredictResponse:
    """Bulk prediction for all players for specified gameweeks."""
    engine = get_prediction_engine()
    model_name = request.model or "ensemble"
    predictions: list[PointPrediction] = []

    for gw in request.gameweeks:
        try:
            results = await engine.predict_all_players(gw)
            for result in results:
                predictions.append(
                    PointPrediction(
                        player_id=result.player_id,
                        gameweek=result.gameweek,
                        predicted_points=round(result.predicted_points, 2),
                        confidence_lower=round(result.confidence_lower, 2),
                        confidence_upper=round(result.confidence_upper, 2),
                        model=result.model_name or model_name,
                    )
                )
        except Exception as exc:
            logger.error("Batch prediction failed for GW%d: %s", gw, exc)

    return BatchPredictResponse(
        predictions=predictions,
        model=model_name,
        gameweeks=request.gameweeks,
        total_players=len({p.player_id for p in predictions}),
    )


# ---------------------------------------------------------------------------
# POST /api/predict/backtest  (stub -- retained for future implementation)
# ---------------------------------------------------------------------------

@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """Run backtest of a model over historical gameweeks."""
    # Full backtesting requires downloading historical data; this is a
    # placeholder that returns zeros until the backtest pipeline is wired up.
    return BacktestResponse(
        model=request.model,
        gw_start=request.gw_start,
        gw_end=request.gw_end,
        mae=0.0,
        cumulative_points=0.0,
        results=[],
    )
