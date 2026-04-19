from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import (
    PortfolioOverview,
    PortfolioPositionCreateRequest,
    PortfolioPositionItem,
    PortfolioPositionStatus,
    PortfolioPositionUpdateRequest,
    PortfolioProfileConfig,
)
from app.services.market_store import MarketDataStore
from app.services.portfolio_service import PortfolioService

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("/overview", response_model=PortfolioOverview)
def portfolio_overview(
    status: PortfolioPositionStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> PortfolioOverview:
    payload = PortfolioService.build_overview(db, market_store, status=status)
    return PortfolioOverview.model_validate(payload)


@router.get("/profile", response_model=PortfolioProfileConfig)
def portfolio_profile(
    db: Session = Depends(get_db),
) -> PortfolioProfileConfig:
    profile = PortfolioService.read_profile(db)
    return PortfolioProfileConfig.model_validate(profile)


@router.put("/profile", response_model=PortfolioProfileConfig)
def update_portfolio_profile(
    payload: PortfolioProfileConfig,
    db: Session = Depends(get_db),
) -> PortfolioProfileConfig:
    profile = PortfolioService.update_profile(db, payload)
    return PortfolioProfileConfig.model_validate(profile)


@router.post("/positions", response_model=PortfolioPositionItem)
def create_portfolio_position(
    payload: PortfolioPositionCreateRequest,
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> PortfolioPositionItem:
    try:
        row = PortfolioService.create_position(db, market_store, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Stock {payload.symbol} not found.") from exc
    return PortfolioPositionItem.model_validate(row)


@router.put("/positions/{position_id}", response_model=PortfolioPositionItem)
def update_portfolio_position(
    position_id: int,
    payload: PortfolioPositionUpdateRequest,
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> PortfolioPositionItem:
    try:
        row = PortfolioService.update_position(db, market_store, position_id=position_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Portfolio position {position_id} not found.") from exc
    return PortfolioPositionItem.model_validate(row)


@router.delete("/positions/{position_id}", status_code=204)
def delete_portfolio_position(
    position_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        PortfolioService.delete_position(db, position_id=position_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Portfolio position {position_id} not found.") from exc
    return Response(status_code=204)
