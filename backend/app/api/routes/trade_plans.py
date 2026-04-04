from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import (
    TradePlanCreateRequest,
    TradePlanItem,
    TradePlanStatus,
    TradePlanUpdateRequest,
)
from app.services.market_store import MarketDataStore
from app.services.trade_plan_service import TradePlanService

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("", response_model=list[TradePlanItem])
def list_trade_plans(
    status: TradePlanStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> list[TradePlanItem]:
    rows = TradePlanService.list_items(db, market_store, status=status)
    return [TradePlanItem.model_validate(row) for row in rows]


@router.post("", response_model=TradePlanItem)
def create_trade_plan(
    payload: TradePlanCreateRequest,
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> TradePlanItem:
    try:
        row = TradePlanService.create_item(db, market_store, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Stock {payload.symbol} not found.") from exc
    return TradePlanItem.model_validate(row)


@router.put("/{plan_id}", response_model=TradePlanItem)
def update_trade_plan(
    plan_id: int,
    payload: TradePlanUpdateRequest,
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
) -> TradePlanItem:
    try:
        row = TradePlanService.update_item(db, market_store, plan_id=plan_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Trade plan {plan_id} not found.") from exc
    return TradePlanItem.model_validate(row)


@router.delete("/{plan_id}", status_code=204)
def delete_trade_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        TradePlanService.delete_item(db, plan_id=plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Trade plan {plan_id} not found.") from exc
    return Response(status_code=204)
