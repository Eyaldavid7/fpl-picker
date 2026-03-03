"""Main API router aggregating all endpoint routers."""

from fastapi import APIRouter

from app.api.endpoints import (
    chips,
    data,
    fixtures_analysis,
    health,
    optimize,
    predict,
    squad_import,
    suggestions,
    transfers,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(optimize.router, prefix="/optimize", tags=["optimization"])
api_router.include_router(squad_import.router, prefix="/squad-import", tags=["squad-import"])
api_router.include_router(fixtures_analysis.router, prefix="/fixtures", tags=["fixtures"])
api_router.include_router(suggestions.router, prefix="/suggestions", tags=["suggestions"])
api_router.include_router(predict.router, prefix="/predict", tags=["prediction"])
api_router.include_router(transfers.router, prefix="/transfers", tags=["transfers"])
api_router.include_router(chips.router, prefix="/chips", tags=["chips"])
