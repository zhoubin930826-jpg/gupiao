from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.market import DashboardSummary
from app.services.market_store import MarketDataStore

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    market_store: MarketDataStore = Depends(get_market_store),
) -> DashboardSummary:
    return DashboardSummary.model_validate(market_store.get_dashboard_summary())
