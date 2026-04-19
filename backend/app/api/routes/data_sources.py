from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
) -> DataSourceOverview:
    current_provider = market_store.current_source()
    payload = DataSourceService.build_overview(
        db,
        current_provider=current_provider,
        fallback_chain=DataSourceService.resolve_order(),
        market_store=market_store,
    )
    return DataSourceOverview.model_validate(payload)
