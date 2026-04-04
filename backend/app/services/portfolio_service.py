from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.portfolio import PortfolioPosition, PortfolioProfile
from app.schemas.market import (
    PortfolioPositionCreateRequest,
    PortfolioPositionUpdateRequest,
    PortfolioProfileConfig,
)
from app.services.market_store import MarketDataStore


class PortfolioService:
    @staticmethod
    def get_profile(db: Session) -> PortfolioProfile:
        profile = db.query(PortfolioProfile).first()
        if profile is None:
            raise RuntimeError("Portfolio profile was not initialized.")
        return profile

    @classmethod
    def read_profile(cls, db: Session) -> PortfolioProfile:
        return cls.get_profile(db)

    @classmethod
    def update_profile(cls, db: Session, payload: PortfolioProfileConfig) -> PortfolioProfile:
        profile = cls.get_profile(db)
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def build_overview(
        cls,
        db: Session,
        market_store: MarketDataStore,
        *,
        status: str | None = None,
    ) -> dict[str, object]:
        profile = cls.read_profile(db)
        query = db.query(PortfolioPosition)
        if status:
            query = query.filter(PortfolioPosition.status == status)
        rows = query.order_by(PortfolioPosition.updated_at.desc(), PortfolioPosition.id.desc()).all()
        snapshot_map = market_store.get_snapshot_briefs([row.symbol for row in rows])

        serialized = [cls._serialize(row, snapshot_map.get(row.symbol)) for row in rows]
        summary = cls._build_summary(profile, serialized)

        estimated_total_assets = float(summary["estimated_total_assets"])
        for row in serialized:
            if row["status"] == "holding" and estimated_total_assets > 0 and row["market_value"] is not None:
                row["weight_pct"] = round(float(row["market_value"]) / estimated_total_assets * 100, 2)
            else:
                row["weight_pct"] = None

        summary["largest_weight_pct"] = (
            round(max((float(row["weight_pct"]) for row in serialized if row["weight_pct"] is not None), default=0.0), 2)
            if serialized
            else None
        )
        if summary["largest_weight_pct"] == 0:
            summary["largest_weight_pct"] = None

        return {
            "profile": PortfolioProfileConfig.model_validate(profile).model_dump(),
            "summary": summary,
            "positions": serialized,
        }

    @classmethod
    def create_position(
        cls,
        db: Session,
        market_store: MarketDataStore,
        payload: PortfolioPositionCreateRequest,
    ) -> dict[str, object]:
        symbol = str(payload.symbol).zfill(6)
        snapshot = market_store.get_snapshot_briefs([symbol]).get(symbol)
        if snapshot is None:
            raise KeyError(symbol)

        latest_price = _optional_float(snapshot.get("latest_price"))
        now = _now()
        exit_price = payload.exit_price
        opened_at = now
        closed_at = None
        if payload.status == "closed":
            exit_price = _preferred_float(exit_price, latest_price, payload.entry_price)
            closed_at = now

        item = PortfolioPosition(
            symbol=symbol,
            name=str(snapshot["name"]),
            source=payload.source,
            status=payload.status,
            quantity=payload.quantity,
            entry_price=payload.entry_price,
            exit_price=exit_price,
            stop_loss_price=payload.stop_loss_price,
            target_price=payload.target_price,
            thesis=_clean_optional_text(payload.thesis) or _clean_optional_text(snapshot.get("thesis")),
            notes=_clean_optional_text(payload.notes),
            opened_at=opened_at,
            closed_at=closed_at,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return cls._serialize(item, snapshot)

    @classmethod
    def update_position(
        cls,
        db: Session,
        market_store: MarketDataStore,
        *,
        position_id: int,
        payload: PortfolioPositionUpdateRequest,
    ) -> dict[str, object]:
        item = db.query(PortfolioPosition).filter_by(id=position_id).first()
        if item is None:
            raise KeyError(str(position_id))

        snapshot = market_store.get_snapshot_briefs([item.symbol]).get(item.symbol)
        latest_price = _optional_float(snapshot.get("latest_price")) if snapshot else None
        now = _now()
        changed_fields = payload.model_fields_set

        if "status" in changed_fields and payload.status is not None:
            item.status = payload.status
            if payload.status == "holding":
                item.opened_at = item.opened_at or now
                item.closed_at = None
                item.exit_price = None
            elif payload.status == "closed":
                item.closed_at = item.closed_at or now
                item.exit_price = _preferred_float(payload.exit_price, item.exit_price, latest_price, item.entry_price)

        if "quantity" in changed_fields and payload.quantity is not None:
            item.quantity = payload.quantity
        if "entry_price" in changed_fields and payload.entry_price is not None:
            item.entry_price = payload.entry_price
        if "exit_price" in changed_fields:
            item.exit_price = payload.exit_price
            if payload.exit_price is not None:
                item.status = "closed"
                item.closed_at = item.closed_at or now
        if "stop_loss_price" in changed_fields:
            item.stop_loss_price = payload.stop_loss_price
        if "target_price" in changed_fields:
            item.target_price = payload.target_price
        if "thesis" in changed_fields:
            item.thesis = _clean_optional_text(payload.thesis)
        if "notes" in changed_fields:
            item.notes = _clean_optional_text(payload.notes)

        if snapshot is not None:
            item.name = str(snapshot["name"])

        db.add(item)
        db.commit()
        db.refresh(item)
        return cls._serialize(item, snapshot)

    @staticmethod
    def delete_position(db: Session, *, position_id: int) -> None:
        item = db.query(PortfolioPosition).filter_by(id=position_id).first()
        if item is None:
            raise KeyError(str(position_id))
        db.delete(item)
        db.commit()

    @staticmethod
    def _serialize(
        item: PortfolioPosition,
        snapshot: dict[str, object] | None,
    ) -> dict[str, object]:
        latest_price = _optional_float(snapshot.get("latest_price")) if snapshot else None
        cost_value = round(item.entry_price * item.quantity, 2)
        market_value = round((latest_price or 0.0) * item.quantity, 2) if latest_price is not None else None

        unrealized_pnl = None
        unrealized_return = None
        if item.status == "holding" and latest_price is not None and item.entry_price > 0:
            unrealized_pnl = round((latest_price - item.entry_price) * item.quantity, 2)
            unrealized_return = round((latest_price / item.entry_price - 1) * 100, 2)

        realized_pnl = None
        realized_return = None
        if item.status == "closed" and item.exit_price is not None and item.entry_price > 0:
            realized_pnl = round((item.exit_price - item.entry_price) * item.quantity, 2)
            realized_return = round((item.exit_price / item.entry_price - 1) * 100, 2)

        stop_distance_pct = None
        if latest_price is not None and item.stop_loss_price is not None and latest_price > 0:
            stop_distance_pct = round((item.stop_loss_price / latest_price - 1) * 100, 2)

        target_distance_pct = None
        if latest_price is not None and item.target_price is not None and latest_price > 0:
            target_distance_pct = round((item.target_price / latest_price - 1) * 100, 2)

        return {
            "id": item.id,
            "symbol": item.symbol,
            "name": snapshot.get("name", item.name) if snapshot else item.name,
            "board": snapshot.get("board") if snapshot else None,
            "industry": snapshot.get("industry") if snapshot else None,
            "source": item.source,
            "status": item.status,
            "quantity": item.quantity,
            "entry_price": round(float(item.entry_price), 2),
            "exit_price": _rounded_optional(item.exit_price),
            "stop_loss_price": _rounded_optional(item.stop_loss_price),
            "target_price": _rounded_optional(item.target_price),
            "latest_price": _rounded_optional(latest_price),
            "change_pct": _rounded_optional(snapshot.get("change_pct")) if snapshot else None,
            "score": int(snapshot["score"]) if snapshot and snapshot.get("score") is not None else None,
            "tags": list(snapshot.get("tags", [])) if snapshot else [],
            "thesis": item.thesis,
            "notes": item.notes,
            "cost_value": cost_value,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_return": unrealized_return,
            "realized_pnl": realized_pnl,
            "realized_return": realized_return,
            "weight_pct": None,
            "stop_distance_pct": stop_distance_pct,
            "target_distance_pct": target_distance_pct,
            "created_at": item.created_at.isoformat(timespec="seconds"),
            "opened_at": item.opened_at.isoformat(timespec="seconds") if item.opened_at else None,
            "closed_at": item.closed_at.isoformat(timespec="seconds") if item.closed_at else None,
            "updated_at": item.updated_at.isoformat(timespec="seconds"),
        }

    @staticmethod
    def _build_summary(profile: PortfolioProfile, rows: list[dict[str, object]]) -> dict[str, object]:
        holding_rows = [row for row in rows if row["status"] == "holding"]
        closed_rows = [row for row in rows if row["status"] == "closed"]

        invested_cost = round(sum(float(row["cost_value"]) for row in holding_rows), 2)
        market_value = round(
            sum(float(row["market_value"]) for row in holding_rows if row["market_value"] is not None),
            2,
        )
        unrealized_pnl = round(
            sum(float(row["unrealized_pnl"]) for row in holding_rows if row["unrealized_pnl"] is not None),
            2,
        )
        realized_pnl = round(
            sum(float(row["realized_pnl"]) for row in closed_rows if row["realized_pnl"] is not None),
            2,
        )

        initial_capital = float(profile.initial_capital)
        estimated_cash = round(initial_capital - invested_cost + realized_pnl, 2)
        estimated_total_assets = round(estimated_cash + market_value, 2)
        total_return_pct = round((estimated_total_assets / initial_capital - 1) * 100, 2) if initial_capital > 0 else 0.0
        utilization_pct = round(invested_cost / initial_capital * 100, 2) if initial_capital > 0 else 0.0

        return {
            "initial_capital": round(initial_capital, 2),
            "estimated_cash": estimated_cash,
            "estimated_total_assets": estimated_total_assets,
            "invested_cost": invested_cost,
            "market_value": market_value,
            "holding_count": len(holding_rows),
            "closed_count": len(closed_rows),
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_return_pct": total_return_pct,
            "utilization_pct": utilization_pct,
            "largest_weight_pct": None,
        }


def _now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().app_timezone))


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rounded_optional(value: object) -> float | None:
    number = _optional_float(value)
    return round(number, 2) if number is not None else None


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _preferred_float(*values: object) -> float | None:
    for value in values:
        number = _optional_float(value)
        if number is not None and number > 0:
            return number
    return None
