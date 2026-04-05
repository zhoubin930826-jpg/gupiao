from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_scope
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import (
    RecommendationItem,
    RecommendationJournalItem,
    RecommendationReviewResponse,
)
from app.services.market_store import MarketDataStore
from app.services.recommendation_review_service import RecommendationReviewService
from app.services.recommendation_service import RecommendationService
from app.services.watchlist_service import WatchlistService

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("", response_model=list[RecommendationItem])
def recommendations(
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
    market: str = Depends(get_market_scope),
) -> list[RecommendationItem]:
    rows = market_store.get_recommendations(market)
    watchlist_symbols = WatchlistService.symbols_in_watchlist(
        db,
        [str(row["symbol"]) for row in rows],
    )
    for row in rows:
        row["in_watchlist"] = str(row["symbol"]) in watchlist_symbols
    return [RecommendationItem.model_validate(row) for row in rows]


@router.get("/journal", response_model=list[RecommendationJournalItem])
def recommendation_journal(
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
    market: str = Depends(get_market_scope),
) -> list[RecommendationJournalItem]:
    rows = RecommendationService.list_journal(db, market_store, market=market)
    return [RecommendationJournalItem.model_validate(row) for row in rows]


@router.get("/review", response_model=RecommendationReviewResponse)
def recommendation_review(
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
    market: str = Depends(get_market_scope),
) -> RecommendationReviewResponse:
    payload = RecommendationReviewService.build_review(db, market_store, market=market)
    return RecommendationReviewResponse.model_validate(payload)
