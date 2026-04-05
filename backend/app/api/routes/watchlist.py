from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_scope
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import (
    WatchlistCreateRequest,
    WatchlistItem,
    WatchlistStatus,
    WatchlistUpdateRequest,
)
from app.services.market_store import MarketDataStore
from app.services.watchlist_service import WatchlistService

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("", response_model=list[WatchlistItem])
def list_watchlist(
    status: WatchlistStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
    market: str = Depends(get_market_scope),
) -> list[WatchlistItem]:
    rows = WatchlistService.list_items(db, market_store, market=market, status=status)
    return [WatchlistItem.model_validate(row) for row in rows]


@router.post("", response_model=WatchlistItem)
def create_watchlist_item(
    payload: WatchlistCreateRequest,
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> WatchlistItem:
    try:
        row = WatchlistService.upsert_item(db, market_store, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Stock {payload.symbol} not found.") from exc
    return WatchlistItem.model_validate(row)


@router.put("/{symbol}", response_model=WatchlistItem)
def update_watchlist_item(
    symbol: str,
    payload: WatchlistUpdateRequest,
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> WatchlistItem:
    try:
        row = WatchlistService.update_item(db, market_store, symbol=symbol, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Watchlist item {symbol} not found.") from exc
    return WatchlistItem.model_validate(row)


@router.delete("/{symbol}", status_code=204)
def delete_watchlist_item(
    symbol: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        WatchlistService.delete_item(db, symbol=symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Watchlist item {symbol} not found.") from exc
    return Response(status_code=204)
