from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_scope
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import (
    AlertCategory,
    AlertItem,
    AlertOverview,
    AlertSeverity,
    AlertStatus,
    AlertStatusUpdateRequest,
)
from app.services.alert_service import AlertService
from app.services.market_store import MarketDataStore

router = APIRouter()


def get_market_store(settings: Settings = Depends(get_settings)) -> MarketDataStore:
    return MarketDataStore(settings.market_database_path)


@router.get("/overview", response_model=AlertOverview)
def get_alert_overview(
    status: AlertStatus | None = Query(default=None),
    severity: AlertSeverity | None = Query(default=None),
    category: AlertCategory | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    market: str = Depends(get_market_scope),
) -> AlertOverview:
    return AlertOverview.model_validate(
        AlertService.build_overview(
            db,
            market=market,
            status=status,
            severity=severity,
            category=category,
            limit=limit,
        )
    )


@router.post("/evaluate", response_model=AlertOverview)
def evaluate_alerts(
    db: Session = Depends(get_db),
    market_store: MarketDataStore = Depends(get_market_store),
    market: str = Depends(get_market_scope),
) -> AlertOverview:
    AlertService.refresh_alerts(db, market_store)
    return AlertOverview.model_validate(AlertService.build_overview(db, market=market))


@router.put("/{alert_id}", response_model=AlertItem)
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> AlertItem:
    try:
        row = AlertService.update_status(db, alert_id=alert_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.") from exc
    return AlertItem.model_validate(row)
