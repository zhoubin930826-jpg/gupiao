from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_scope
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import DataSourceOverview
from app.services.data_source_service import DataSourceService
from app.services.market_store import MarketDataStore

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("/overview", response_model=DataSourceOverview)
def get_data_source_overview(
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
    market: str = Depends(get_market_scope),
) -> DataSourceOverview:
    current_provider = market_store.current_source(market)
    payload = DataSourceService.build_overview(
        db,
        market=market,
        current_provider=current_provider,
        fallback_chain=DataSourceService.resolve_order(market),
        market_store=market_store,
    )
    return DataSourceOverview.model_validate(payload)
