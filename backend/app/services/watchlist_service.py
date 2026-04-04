from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.watchlist import WatchlistEntry
from app.schemas.market import WatchlistCreateRequest, WatchlistUpdateRequest
from app.services.market_store import MarketDataStore


class WatchlistService:
    @staticmethod
    def symbols_in_watchlist(db: Session, symbols: list[str]) -> set[str]:
        if not symbols:
            return set()
        rows = db.query(WatchlistEntry.symbol).filter(WatchlistEntry.symbol.in_(symbols)).all()
        return {str(row[0]) for row in rows}

    @classmethod
    def list_items(
        cls,
        db: Session,
        market_store: MarketDataStore,
        *,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        query = db.query(WatchlistEntry)
        if status:
            query = query.filter(WatchlistEntry.status == status)
        rows = query.order_by(WatchlistEntry.updated_at.desc(), WatchlistEntry.id.desc()).all()
        snapshot_map = market_store.get_snapshot_briefs([row.symbol for row in rows])
        return [cls._serialize(row, snapshot_map.get(row.symbol)) for row in rows]

    @classmethod
    def upsert_item(
        cls,
        db: Session,
        market_store: MarketDataStore,
        payload: WatchlistCreateRequest,
    ) -> dict[str, object]:
        symbol = str(payload.symbol).zfill(6)
        snapshot = market_store.get_snapshot_briefs([symbol]).get(symbol)
        if snapshot is None:
            raise KeyError(symbol)

        item = db.query(WatchlistEntry).filter_by(symbol=symbol).first()
        notes = _clean_notes(payload.notes)
        if item is None:
            item = WatchlistEntry(
                symbol=symbol,
                name=str(snapshot["name"]),
                source=payload.source,
                status=payload.status,
                notes=notes,
                added_price=_optional_float(snapshot.get("latest_price")),
            )
        else:
            item.name = str(snapshot["name"])
            item.source = payload.source
            item.status = payload.status
            if notes is not None:
                item.notes = notes
            if item.added_price is None:
                item.added_price = _optional_float(snapshot.get("latest_price"))

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
        symbol: str,
        payload: WatchlistUpdateRequest,
    ) -> dict[str, object]:
        normalized_symbol = str(symbol).zfill(6)
        item = db.query(WatchlistEntry).filter_by(symbol=normalized_symbol).first()
        if item is None:
            raise KeyError(normalized_symbol)

        if payload.status is not None:
            item.status = payload.status
        if payload.notes is not None:
            item.notes = _clean_notes(payload.notes)

        snapshot = market_store.get_snapshot_briefs([normalized_symbol]).get(normalized_symbol)
        if snapshot is not None:
            item.name = str(snapshot["name"])
            if item.added_price is None:
                item.added_price = _optional_float(snapshot.get("latest_price"))

        db.add(item)
        db.commit()
        db.refresh(item)
        return cls._serialize(item, snapshot)

    @staticmethod
    def delete_item(db: Session, *, symbol: str) -> None:
        normalized_symbol = str(symbol).zfill(6)
        item = db.query(WatchlistEntry).filter_by(symbol=normalized_symbol).first()
        if item is None:
            raise KeyError(normalized_symbol)
        db.delete(item)
        db.commit()

    @staticmethod
    def _serialize(
        item: WatchlistEntry,
        snapshot: dict[str, object] | None,
    ) -> dict[str, object]:
        latest_price = _optional_float(snapshot.get("latest_price")) if snapshot else None
        added_price = item.added_price if item.added_price and item.added_price > 0 else None
        current_return = None
        if latest_price is not None and added_price is not None:
            current_return = round((latest_price / added_price - 1) * 100, 2)

        return {
            "symbol": item.symbol,
            "name": snapshot.get("name", item.name) if snapshot else item.name,
            "board": snapshot.get("board") if snapshot else None,
            "industry": snapshot.get("industry") if snapshot else None,
            "status": item.status,
            "source": item.source,
            "notes": item.notes,
            "added_price": round(added_price, 2) if added_price is not None else None,
            "latest_price": round(latest_price, 2) if latest_price is not None else None,
            "change_pct": _rounded_optional(snapshot.get("change_pct")) if snapshot else None,
            "score": int(snapshot["score"]) if snapshot and snapshot.get("score") is not None else None,
            "thesis": str(snapshot["thesis"]) if snapshot and snapshot.get("thesis") else None,
            "tags": list(snapshot.get("tags", [])) if snapshot else [],
            "current_return": current_return,
            "added_at": item.added_at.isoformat(timespec="seconds"),
            "updated_at": item.updated_at.isoformat(timespec="seconds"),
        }


def _clean_notes(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


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
