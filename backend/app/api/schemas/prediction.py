"""Pydantic models for prediction-related API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PointPrediction(BaseModel):
    """Single point prediction for a player in a gameweek.

    Attributes:
        player_id: The FPL element ID.
        gameweek: The target gameweek number.
        predicted_points: The predicted total points.
        confidence_lower: Lower bound of the confidence interval.
        confidence_upper: Upper bound of the confidence interval.
        model: Name of the prediction model used.
    """

    player_id: int
    gameweek: int = Field(ge=1, le=38)
    predicted_points: float
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    model: str = "ensemble"


class ModelBreakdown(BaseModel):
    """Per-model prediction values for a single player.

    Attributes:
        player_id: The FPL element ID.
        gameweek: The target gameweek number.
        predictions: Mapping of model name to predicted points.
    """

    player_id: int
    gameweek: int = Field(ge=1, le=38)
    predictions: dict[str, float]


class PredictPointsRequest(BaseModel):
    """Request body for point predictions.

    Attributes:
        player_ids: Optional list of specific player IDs to predict.
            If None, predicts for all available players.
        gameweeks: List of target gameweek numbers (each 1-38).
        model: Optional model name. None or 'ensemble' uses all models.

    Example:
        >>> request = PredictPointsRequest(
        ...     player_ids=[1, 2, 3],
        ...     gameweeks=[28, 29],
        ...     model="ensemble",
        ... )
    """

    player_ids: list[int] | None = None
    gameweeks: list[int] = Field(
        ...,
        min_length=1,
        description="Target gameweek numbers (1-38)",
        json_schema_extra={"examples": [[28, 29]]},
    )
    model: str | None = Field(
        default=None,
        description=(
            "Prediction model to use. Options: arima_100, weighted_avg, "
            "hybrid_ml, exp_smoothing, monte_carlo, ensemble (default)"
        ),
    )


class PredictPointsResponse(BaseModel):
    """Response for point predictions."""

    predictions: list[PointPrediction]
    model: str
    gameweeks: list[int]


class BatchPredictRequest(BaseModel):
    """Request body for batch predictions.

    Attributes:
        gameweeks: List of target gameweek numbers.
        model: Optional model name for predictions.
    """

    gameweeks: list[int] = Field(min_length=1)
    model: str | None = None


class BatchPredictResponse(BaseModel):
    """Response for batch predictions."""

    predictions: list[PointPrediction]
    model: str
    gameweeks: list[int]
    total_players: int


class CompareModelsRequest(BaseModel):
    """Request body for model comparison.

    Attributes:
        player_ids: List of player IDs to compare predictions for.
        gameweek: Target gameweek number (1-38).

    Example:
        >>> request = CompareModelsRequest(
        ...     player_ids=[1, 10, 20],
        ...     gameweek=28,
        ... )
    """

    player_ids: list[int] = Field(min_length=1)
    gameweek: int = Field(ge=1, le=38)


class CompareModelsResponse(BaseModel):
    """Response for model comparison."""

    comparisons: list[ModelBreakdown]
    gameweek: int


class ModelInfo(BaseModel):
    """Information about a registered prediction model.

    Attributes:
        name: Internal model name.
        type: Model type (e.g. 'time_series', 'ml').
        description: Human-readable description.
        weight: Weight in the ensemble (e.g. 'auto').
    """

    name: str
    type: str
    description: str
    weight: str


class ModelListResponse(BaseModel):
    """Response for listing available models."""

    models: list[ModelInfo]


class PlayerPredictionResponse(BaseModel):
    """Detailed prediction for a single player with per-model breakdown.

    Attributes:
        player_id: The FPL element ID.
        gameweek: Target gameweek number.
        ensemble_prediction: The combined ensemble prediction.
        confidence_lower: Lower bound of the confidence interval.
        confidence_upper: Upper bound of the confidence interval.
        model_breakdown: Per-model prediction values.
    """

    player_id: int
    gameweek: int
    ensemble_prediction: float
    confidence_lower: float
    confidence_upper: float
    model_breakdown: dict[str, float]


class BacktestRequest(BaseModel):
    """Request body for model backtesting.

    Attributes:
        model: The model name to backtest.
        gw_start: First gameweek in the backtest range (1-38).
        gw_end: Last gameweek in the backtest range (1-38).
    """

    model: str
    gw_start: int = Field(ge=1, le=38)
    gw_end: int = Field(ge=1, le=38)


class BacktestGameweekResult(BaseModel):
    """Result for a single gameweek in a backtest."""

    gameweek: int
    mae: float
    predicted_total: float
    actual_total: float


class BacktestResponse(BaseModel):
    """Response for backtest results."""

    model: str
    gw_start: int
    gw_end: int
    mae: float
    cumulative_points: float
    results: list[BacktestGameweekResult]
