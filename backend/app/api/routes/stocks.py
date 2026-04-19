from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import StockDetail, StockListResponse, StrategyConfig
from app.services.market_store import MarketDataStore
from app.services.recommendation_diagnosis_service import RecommendationDiagnosisService
from app.services.recommendation_trust_service import build_recommendation_trust
from app.services.strategy_service import StrategyService
from app.services.watchlist_service import WatchlistService

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("", response_model=StockListResponse)
def list_stocks(
    market_store: MarketDataStore = Depends(get_market_store),
    db: Session = Depends(get_db),
    keyword: str | None = None,
    board: str = Query(default="全部"),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> StockListResponse:
    payload = market_store.list_stocks(keyword=keyword, board=board, page=page, page_size=page_size)
    symbols = [str(row["symbol"]) for row in payload["rows"]]
    watchlist_symbols = WatchlistService.symbols_in_watchlist(db, symbols)
    for row in payload["rows"]:
        row["in_watchlist"] = str(row["symbol"]) in watchlist_symbols
    return StockListResponse.model_validate(payload)


@router.get("/{symbol}", response_model=StockDetail)
def stock_detail(
    symbol: str,
    market_store: MarketDataStore = Depends(get_market_store),
    db: Session = Depends(get_db),
) -> StockDetail:
    try:
        payload = market_store.get_stock_detail(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found.") from exc
    payload["in_watchlist"] = symbol in WatchlistService.symbols_in_watchlist(db, [symbol])
    payload["recommendation_diagnosis"] = RecommendationDiagnosisService.build(
        detail=payload,
        ranking=market_store.get_recommendation_context(symbol),
        strategy=StrategyConfig.model_validate(StrategyService.read_config(db)),
    )
    payload["recommendation_trust"] = build_recommendation_trust(
        source=market_store.current_source(),
        snapshot_updated_at=str(payload.pop("snapshot_updated_at") or "").replace("T", " "),
        signal_breakdown=list(payload.get("signal_breakdown", [])),
        risk_notes=[str(item) for item in payload.get("risk_notes", [])],
    )
    return StockDetail.model_validate(payload)
