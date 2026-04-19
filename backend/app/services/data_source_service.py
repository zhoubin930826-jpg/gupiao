from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.market_scope import DEFAULT_MARKET_SCOPE, scoped_key, unscoped_key
from app.models.data_source import DataSourceStatus
from app.services.market_store import MarketDataStore


@dataclass(frozen=True, slots=True)
class DataSourceDescriptor:
    provider_key: str
    display_name: str
    enabled: bool
    priority: int
    supports_snapshot: bool
    supports_history: bool
    supports_fundamental: bool


class DataSourceService:
    @classmethod
    def sync_catalog(cls, db: Session, market: str = DEFAULT_MARKET_SCOPE) -> list[DataSourceStatus]:
        descriptors = cls.catalog(DEFAULT_MARKET_SCOPE)
        existing = {
            row.provider_key: row
            for row in db.query(DataSourceStatus).all()
        }
        synced_rows: list[DataSourceStatus] = []
        changed = False
        for descriptor in descriptors:
            scoped_provider_key = scoped_key(DEFAULT_MARKET_SCOPE, descriptor.provider_key)
            row = existing.get(scoped_provider_key)
            if row is None:
                row = DataSourceStatus(
                    provider_key=scoped_provider_key,
                    display_name=descriptor.display_name,
                    enabled=descriptor.enabled,
                    priority=descriptor.priority,
                    supports_snapshot=descriptor.supports_snapshot,
                    supports_history=descriptor.supports_history,
                    supports_fundamental=descriptor.supports_fundamental,
                    last_status="idle",
                    last_message="等待首次同步。",
                )
                db.add(row)
                changed = True
            else:
                changed = cls._apply_descriptor(row, descriptor) or changed
                db.add(row)
            synced_rows.append(row)
        if changed:
            db.commit()
            for row in synced_rows:
                db.refresh(row)
        return sorted(synced_rows, key=lambda item: item.priority)

    @classmethod
    def catalog(cls, market: str = DEFAULT_MARKET_SCOPE) -> list[DataSourceDescriptor]:
        settings = get_settings()
        descriptors = [
            DataSourceDescriptor(
                provider_key="akshare",
                display_name="AKShare",
                enabled=settings.enable_akshare_sync,
                priority=1,
                supports_snapshot=True,
                supports_history=True,
                supports_fundamental=True,
            ),
            DataSourceDescriptor(
                provider_key="sample",
                display_name="示例数据",
                enabled=True,
                priority=99,
                supports_snapshot=True,
                supports_history=True,
                supports_fundamental=True,
            ),
        ]
        return descriptors

    @classmethod
    def resolve_order(cls, market: str = DEFAULT_MARKET_SCOPE) -> list[str]:
        settings = get_settings()
        preferred = [provider.strip().lower() for provider in settings.market_data_provider_order if provider.strip()]
        available = {item.provider_key for item in cls.catalog(DEFAULT_MARKET_SCOPE) if item.enabled}
        order = [provider for provider in preferred if provider in available]
        if "sample" not in order:
            order.append("sample")
        return order

    @classmethod
    def mark_attempt(
        cls,
        db: Session,
        *,
        market: str = DEFAULT_MARKET_SCOPE,
        provider_key: str,
        status: str,
        message: str,
        at: datetime | None = None,
    ) -> DataSourceStatus:
        row = db.query(DataSourceStatus).filter_by(provider_key=scoped_key(DEFAULT_MARKET_SCOPE, provider_key)).first()
        if row is None:
            cls.sync_catalog(db, DEFAULT_MARKET_SCOPE)
            row = db.query(DataSourceStatus).filter_by(
                provider_key=scoped_key(DEFAULT_MARKET_SCOPE, provider_key)
            ).first()
        if row is None:
            raise KeyError(provider_key)

        now = at or _now()
        row.last_status = status
        row.last_message = message
        row.last_run_at = now
        if status == "success":
            row.last_success_at = now
        elif status == "warning":
            row.last_failure_at = now
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @classmethod
    def build_overview(
        cls,
        db: Session,
        *,
        current_provider: str,
        fallback_chain: list[str],
        market_store: MarketDataStore,
    ) -> dict[str, object]:
        rows = cls.sync_catalog(db, DEFAULT_MARKET_SCOPE)
        return {
            "current_provider": cls.provider_key_from_source(current_provider),
            "fallback_chain": fallback_chain,
            "items": [cls._serialize(row) for row in rows],
            "event_sync": market_store.get_event_sync_overview(),
        }

    @staticmethod
    def provider_key_from_source(source: str) -> str:
        normalized = source.strip().lower()
        if normalized.startswith("akshare"):
            return "akshare"
        if normalized.startswith("sample"):
            return "sample"
        return normalized

    @staticmethod
    def _serialize(row: DataSourceStatus) -> dict[str, object]:
        return {
            "provider_key": unscoped_key(row.provider_key),
            "display_name": row.display_name,
            "enabled": row.enabled,
            "priority": row.priority,
            "supports_snapshot": row.supports_snapshot,
            "supports_history": row.supports_history,
            "supports_fundamental": row.supports_fundamental,
            "last_status": row.last_status,
            "last_message": row.last_message,
            "last_run_at": row.last_run_at.isoformat(timespec="seconds") if row.last_run_at else None,
            "last_success_at": row.last_success_at.isoformat(timespec="seconds") if row.last_success_at else None,
            "last_failure_at": row.last_failure_at.isoformat(timespec="seconds") if row.last_failure_at else None,
            "updated_at": row.updated_at.isoformat(timespec="seconds"),
        }

    @staticmethod
    def _apply_descriptor(row: DataSourceStatus, descriptor: DataSourceDescriptor) -> bool:
        changed = False
        for field in (
            "display_name",
            "enabled",
            "priority",
            "supports_snapshot",
            "supports_history",
            "supports_fundamental",
        ):
            value = getattr(descriptor, field)
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
        return changed


def _now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().app_timezone))
