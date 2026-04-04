from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.market import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        mode=settings.app_mode,
        scheduler_enabled=settings.enable_task_scheduler,
        market_db_path=settings.market_database_path,
        strategy_store=settings.business_database_url,
    )
