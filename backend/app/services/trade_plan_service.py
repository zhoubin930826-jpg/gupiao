from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.trade_plan import TradePlanEntry
from app.schemas.market import TradePlanCreateRequest, TradePlanUpdateRequest
from app.services.market_store import MarketDataStore


class TradePlanService:
    @classmethod
    def list_items(
        cls,
        db: Session,
        market_store: MarketDataStore,
        *,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        query = db.query(TradePlanEntry)
        if status:
            query = query.filter(TradePlanEntry.status == status)
        rows = query.order_by(TradePlanEntry.updated_at.desc(), TradePlanEntry.id.desc()).all()
        snapshot_map = market_store.get_snapshot_briefs([row.symbol for row in rows])
        return [cls._serialize(row, snapshot_map.get(row.symbol)) for row in rows]

    @classmethod
    def create_item(
        cls,
        db: Session,
        market_store: MarketDataStore,
        payload: TradePlanCreateRequest,
    ) -> dict[str, object]:
        symbol = str(payload.symbol).zfill(6)
        snapshot = market_store.get_snapshot_briefs([symbol]).get(symbol)
        if snapshot is None:
            raise KeyError(symbol)

        latest_price = _optional_float(snapshot.get("latest_price"))
        now = _now()
        planned_entry_price = _preferred_price(payload.planned_entry_price, latest_price)
        actual_entry_price = payload.actual_entry_price
        actual_exit_price = payload.actual_exit_price
        opened_at = None
        closed_at = None

        if payload.status == "active":
            actual_entry_price = _preferred_price(actual_entry_price, planned_entry_price, latest_price)
            opened_at = now
        elif payload.status == "closed":
            actual_entry_price = _preferred_price(actual_entry_price, planned_entry_price, latest_price)
            actual_exit_price = _preferred_price(actual_exit_price, latest_price, actual_entry_price)
            opened_at = now
            closed_at = now

        item = TradePlanEntry(
            symbol=symbol,
            name=str(snapshot["name"]),
            source=payload.source,
            status=payload.status,
            thesis=_clean_optional_text(payload.thesis) or _clean_optional_text(snapshot.get("thesis")),
            notes=_clean_optional_text(payload.notes),
            planned_entry_price=planned_entry_price,
            actual_entry_price=actual_entry_price,
            actual_exit_price=actual_exit_price,
            stop_loss_price=payload.stop_loss_price,
            target_price=payload.target_price,
            planned_position_pct=payload.planned_position_pct,
            opened_at=opened_at,
            closed_at=closed_at,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return cls._serialize(item, snapshot)

    @classmethod
    def update_item(
        cls,
        db: Session,
        market_store: MarketDataStore,
        *,
        plan_id: int,
        payload: TradePlanUpdateRequest,
    ) -> dict[str, object]:
        item = db.query(TradePlanEntry).filter_by(id=plan_id).first()
        if item is None:
            raise KeyError(str(plan_id))

        snapshot = market_store.get_snapshot_briefs([item.symbol]).get(item.symbol)
        latest_price = _optional_float(snapshot.get("latest_price")) if snapshot else None
        now = _now()
        changed_fields = payload.model_fields_set

        if "status" in changed_fields and payload.status is not None:
            item.status = payload.status
            if payload.status == "active":
                item.actual_entry_price = _preferred_price(
                    item.actual_entry_price,
                    item.planned_entry_price,
                    latest_price,
                )
                item.opened_at = item.opened_at or now
            elif payload.status == "closed":
                item.actual_entry_price = _preferred_price(
                    item.actual_entry_price,
                    item.planned_entry_price,
                    latest_price,
                )
                item.actual_exit_price = _preferred_price(
                    item.actual_exit_price,
                    latest_price,
                    item.actual_entry_price,
                )
                item.opened_at = item.opened_at or now
                item.closed_at = item.closed_at or now
            elif payload.status == "cancelled":
                item.closed_at = item.closed_at or now

        if "thesis" in changed_fields:
            item.thesis = _clean_optional_text(payload.thesis)
        if "notes" in changed_fields:
            item.notes = _clean_optional_text(payload.notes)
        if "planned_entry_price" in changed_fields:
            item.planned_entry_price = payload.planned_entry_price
        if "actual_entry_price" in changed_fields:
            item.actual_entry_price = payload.actual_entry_price
            if payload.actual_entry_price is not None:
                item.opened_at = item.opened_at or now
        if "actual_exit_price" in changed_fields:
            item.actual_exit_price = payload.actual_exit_price
            if payload.actual_exit_price is not None:
                item.closed_at = item.closed_at or now
                if item.status == "active":
                    item.status = "closed"
        if "stop_loss_price" in changed_fields:
            item.stop_loss_price = payload.stop_loss_price
        if "target_price" in changed_fields:
            item.target_price = payload.target_price
        if "planned_position_pct" in changed_fields:
            item.planned_position_pct = payload.planned_position_pct

        if snapshot is not None:
            item.name = str(snapshot["name"])

        db.add(item)
        db.commit()
        db.refresh(item)
        return cls._serialize(item, snapshot)

    @staticmethod
    def delete_item(db: Session, *, plan_id: int) -> None:
        item = db.query(TradePlanEntry).filter_by(id=plan_id).first()
        if item is None:
            raise KeyError(str(plan_id))
        db.delete(item)
        db.commit()

    @staticmethod
    def _serialize(
        item: TradePlanEntry,
        snapshot: dict[str, object] | None,
    ) -> dict[str, object]:
        latest_price = _optional_float(snapshot.get("latest_price")) if snapshot else None
        planned_entry_price = _optional_float(item.planned_entry_price)
        actual_entry_price = _optional_float(item.actual_entry_price)
        actual_exit_price = _optional_float(item.actual_exit_price)
        stop_loss_price = _optional_float(item.stop_loss_price)
        target_price = _optional_float(item.target_price)

        plan_gap_pct = None
        if latest_price is not None and planned_entry_price and planned_entry_price > 0:
            plan_gap_pct = round((latest_price / planned_entry_price - 1) * 100, 2)

        current_return = None
        if item.status == "active" and latest_price is not None and actual_entry_price and actual_entry_price > 0:
            current_return = round((latest_price / actual_entry_price - 1) * 100, 2)

        realized_return = None
        if item.status == "closed" and actual_entry_price and actual_exit_price and actual_entry_price > 0:
            realized_return = round((actual_exit_price / actual_entry_price - 1) * 100, 2)

        risk_reward_ratio = None
        reference_entry = actual_entry_price or planned_entry_price
        if (
            reference_entry
            and stop_loss_price is not None
            and target_price is not None
            and stop_loss_price < reference_entry < target_price
        ):
            downside = reference_entry - stop_loss_price
            upside = target_price - reference_entry
            if downside > 0:
                risk_reward_ratio = round(upside / downside, 2)

        return {
            "id": item.id,
            "symbol": item.symbol,
            "name": snapshot.get("name", item.name) if snapshot else item.name,
            "board": snapshot.get("board") if snapshot else None,
            "industry": snapshot.get("industry") if snapshot else None,
            "source": item.source,
            "status": item.status,
            "thesis": item.thesis,
            "notes": item.notes,
            "planned_entry_price": _rounded_optional(planned_entry_price),
            "actual_entry_price": _rounded_optional(actual_entry_price),
            "actual_exit_price": _rounded_optional(actual_exit_price),
            "stop_loss_price": _rounded_optional(stop_loss_price),
            "target_price": _rounded_optional(target_price),
            "planned_position_pct": item.planned_position_pct,
            "latest_price": _rounded_optional(latest_price),
            "change_pct": _rounded_optional(snapshot.get("change_pct")) if snapshot else None,
            "score": int(snapshot["score"]) if snapshot and snapshot.get("score") is not None else None,
            "tags": list(snapshot.get("tags", [])) if snapshot else [],
            "plan_gap_pct": plan_gap_pct,
            "current_return": current_return,
            "realized_return": realized_return,
            "risk_reward_ratio": risk_reward_ratio,
            "created_at": item.created_at.isoformat(timespec="seconds"),
            "opened_at": item.opened_at.isoformat(timespec="seconds") if item.opened_at else None,
            "closed_at": item.closed_at.isoformat(timespec="seconds") if item.closed_at else None,
            "updated_at": item.updated_at.isoformat(timespec="seconds"),
        }


def _now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().app_timezone))


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rounded_optional(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _preferred_price(*candidates: float | None) -> float | None:
    for value in candidates:
        if value is not None and value > 0:
            return float(value)
    return None
