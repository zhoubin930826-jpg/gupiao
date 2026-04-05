from __future__ import annotations

from threading import Lock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.market_scope import (
    DEFAULT_MARKET_SCOPE,
    SUPPORTED_MARKETS,
    market_label,
    normalize_market_scope,
    scoped_key,
    unscoped_key,
)
from app.db.session import SessionLocal
from app.models.task import SyncTaskRecord
from app.schemas.market import SyncTask
from app.services.alert_service import AlertService
from app.services.data_source_service import DataSourceService
from app.services.market_store import MarketDataStore
from app.services.market_data_provider import ProviderSyncResult, build_provider
from app.services.recommendation_service import RecommendationService
from app.services.signal_engine import StrategyWeights
from app.services.strategy_service import StrategyService


class TaskService:
    _job_lock = Lock()

    def __init__(self, db: Session, market_store: MarketDataStore):
        self.db = db
        self.market_store = market_store
        self.settings = get_settings()

    def list_tasks(self, market: str = DEFAULT_MARKET_SCOPE) -> list[dict[str, object]]:
        normalized_market = normalize_market_scope(market)
        rows = [
            row
            for row in self.db.query(SyncTaskRecord).order_by(SyncTaskRecord.id.asc()).all()
            if row.task_key.startswith(f"{normalized_market}:")
        ]
        return [self._serialize_task(row) for row in rows]

    def prepare_market_sync(self, market: str = DEFAULT_MARKET_SCOPE) -> tuple[dict[str, object], bool]:
        normalized_market = normalize_market_scope(market)
        timezone = ZoneInfo(self.settings.app_timezone)
        now = datetime.now(timezone)
        task = self.db.query(SyncTaskRecord).filter_by(
            task_key=scoped_key(normalized_market, "market-sync")
        ).first()
        if task is None:
            raise RuntimeError("Market sync task missing.")

        if task.status == "running":
            return self._serialize_task(task), False

        task.status = "running"
        task.message = f"任务已提交，后台正在同步 {market_label(normalized_market)} 数据..."
        task.source = self.market_store.current_source(normalized_market)
        task.last_run_at = now
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return self._serialize_task(task), True

    @classmethod
    def run_market_sync_job(cls, market: str = DEFAULT_MARKET_SCOPE) -> None:
        if not cls._job_lock.acquire(timeout=1800):
            return
        session = SessionLocal()
        settings = get_settings()
        service = cls(db=session, market_store=MarketDataStore(settings.market_database_path))
        try:
            service._perform_market_sync(market=market)
        finally:
            session.close()
            cls._job_lock.release()

    @classmethod
    def sync_task_plans(cls) -> None:
        settings = get_settings()
        timezone = ZoneInfo(settings.app_timezone)
        now = datetime.now(timezone)

        session = SessionLocal()
        try:
            for market in SUPPORTED_MARKETS:
                normalized_market = normalize_market_scope(market)
                DataSourceService.sync_catalog(session, normalized_market)
                market_schedule = cls._schedule_map(normalized_market)
                for task_key, plan in market_schedule.items():
                    row = session.query(SyncTaskRecord).filter_by(
                        task_key=scoped_key(normalized_market, task_key)
                    ).first()
                    if row is None:
                        continue

                    hour, minute = plan
                    row.schedule = cls._schedule_label(hour, minute)
                    if row.status != "running":
                        row.next_run_at = (
                            cls._next_occurrence(hour=hour, minute=minute, now=now, timezone=timezone)
                            if settings.enable_task_scheduler
                            else None
                        )
                    session.add(row)
            session.commit()
        finally:
            session.close()

    def _perform_market_sync(self, market: str = DEFAULT_MARKET_SCOPE) -> None:
        normalized_market = normalize_market_scope(market)
        timezone = ZoneInfo(self.settings.app_timezone)
        now = datetime.now(timezone)
        task = self.db.query(SyncTaskRecord).filter_by(
            task_key=scoped_key(normalized_market, "market-sync")
        ).first()
        if task is None:
            raise RuntimeError("Market sync task missing.")

        task.status = "running"
        task.message = f"正在刷新 {market_label(normalized_market)} 市场数据..."
        self.db.add(task)
        self.db.commit()

        DataSourceService.sync_catalog(self.db, normalized_market)
        profile = StrategyService.read_config(self.db, normalized_market)
        strategy = StrategyWeights.from_mapping(profile.__dict__)
        source = "sample"
        final_status = "success"
        final_message = f"已刷新 {market_label(normalized_market)} 示例数据。"
        provider_order = DataSourceService.resolve_order(normalized_market)
        warning_messages: list[str] = []

        for provider_key in provider_order:
            result = self._run_provider(
                provider_key=provider_key,
                strategy=strategy,
                market=normalized_market,
            )
            if result.success:
                source = result.source_label
                if result.dataset is not None:
                    self.market_store.refresh_snapshot_records(
                        result.dataset.snapshot_records,
                        source=result.source_label,
                        market=normalized_market,
                        history_rows=result.dataset.history_rows,
                        benchmark_rows=result.dataset.benchmark_records,
                        breadth_snapshot=result.dataset.breadth_snapshot,
                        market_capital_flow=result.dataset.market_capital_flow,
                        lhb_rows=result.dataset.lhb_rows,
                    )
                    final_message = result.message
                    final_status = "success"
                else:
                    self.market_store.seed_demo_dataset(normalized_market)
                    final_status = "warning" if warning_messages else "success"
                    if warning_messages:
                        final_message = (
                            f"{'；'.join(warning_messages)} 已回退到 {market_label(normalized_market)} 示例数据。"
                        )
                    else:
                        final_message = f"已刷新 {market_label(normalized_market)} 示例数据。"
                break
            warning_messages.append(result.message)
        else:
            self.market_store.seed_demo_dataset(normalized_market)
            final_status = "warning"
            final_message = (
                "；".join(warning_messages)
                if warning_messages
                else f"所有数据源均不可用，已回退到 {market_label(normalized_market)} 示例数据。"
            )

        task.status = final_status
        task.last_run_at = now
        market_schedule = self._schedule_map(normalized_market)
        market_sync_hour, market_sync_minute = market_schedule["market-sync"]
        task.next_run_at = (
            self._next_occurrence(
                hour=market_sync_hour,
                minute=market_sync_minute,
                now=now,
                timezone=timezone,
            )
            if self.settings.enable_task_scheduler
            else None
        )
        task.message = final_message
        task.source = source
        self.db.add(task)

        if final_status == "success":
            RecommendationService.publish_current_run(
                self.db,
                self.market_store,
                generated_at=now,
                source=source,
                market=normalized_market,
            )

        for dependent_key in ("signal-rescore", "recommendation-publish"):
            dependent = self.db.query(SyncTaskRecord).filter_by(
                task_key=scoped_key(normalized_market, dependent_key)
            ).first()
            if dependent is None:
                continue
            dependent.status = "success"
            dependent.last_run_at = now
            next_hour, next_minute = market_schedule[dependent_key]
            dependent.next_run_at = (
                self._next_occurrence(
                    hour=next_hour,
                    minute=next_minute,
                    now=now,
                    timezone=timezone,
                )
                if self.settings.enable_task_scheduler
                else None
            )
            dependent.message = f"已基于最新 {market_label(normalized_market)} 市场数据刷新。"
            dependent.source = source
            self.db.add(dependent)

        self.db.commit()

        try:
            AlertService.refresh_alerts(self.db, self.market_store)
        except Exception:  # pragma: no cover - alert refresh should not break sync
            self.db.rollback()

    def _run_provider(
        self,
        *,
        provider_key: str,
        strategy: StrategyWeights,
        market: str = DEFAULT_MARKET_SCOPE,
    ) -> ProviderSyncResult:
        provider = build_provider(provider_key, market=market)
        try:
            result = provider.sync(strategy=strategy)
        except Exception as exc:  # pragma: no cover - provider protection
            result = ProviderSyncResult(
                provider_key=provider_key,
                source_label="sample" if provider_key == "sample" else provider_key,
                success=False,
                used_fallback=provider_key == "sample",
                dataset=None,
                message=f"{provider_key} 同步失败: {exc}",
            )

        DataSourceService.mark_attempt(
            self.db,
            market=market,
            provider_key=provider_key,
            status="success" if result.success else "warning",
            message=result.message,
        )
        return result

    @staticmethod
    def _serialize_task(task: SyncTaskRecord) -> dict[str, object]:
        return SyncTask(
            task_key=unscoped_key(task.task_key),
            name=task.name,
            status=task.status,  # type: ignore[arg-type]
            schedule=task.schedule,
            last_run_at=task.last_run_at.isoformat(timespec="seconds") if task.last_run_at else None,
            next_run_at=task.next_run_at.isoformat(timespec="seconds") if task.next_run_at else None,
            message=task.message,
            source=task.source,
        ).model_dump()

    @staticmethod
    def _schedule_map(market: str = DEFAULT_MARKET_SCOPE) -> dict[str, tuple[int, int]]:
        settings = get_settings()
        offset = TaskService._market_offset_minutes(market)
        return {
            "market-sync": TaskService._apply_offset(
                settings.scheduler_market_hour,
                settings.scheduler_market_minute,
                offset,
            ),
            "signal-rescore": TaskService._apply_offset(
                settings.scheduler_signal_hour,
                settings.scheduler_signal_minute,
                offset,
            ),
            "recommendation-publish": TaskService._apply_offset(
                settings.scheduler_publish_hour,
                settings.scheduler_publish_minute,
                offset,
            ),
        }

    @staticmethod
    def _schedule_label(hour: int, minute: int) -> str:
        return f"每日 {hour:02d}:{minute:02d}"

    @staticmethod
    def _market_offset_minutes(market: str = DEFAULT_MARKET_SCOPE) -> int:
        settings = get_settings()
        normalized_market = normalize_market_scope(market)
        if normalized_market == "hk":
            return settings.scheduler_hk_offset_minutes
        if normalized_market == "us":
            return settings.scheduler_us_offset_minutes
        return 0

    @staticmethod
    def _apply_offset(hour: int, minute: int, offset_minutes: int) -> tuple[int, int]:
        total_minutes = (hour * 60 + minute + offset_minutes) % (24 * 60)
        return total_minutes // 60, total_minutes % 60

    @staticmethod
    def _next_occurrence(
        *,
        hour: int,
        minute: int,
        now: datetime,
        timezone: ZoneInfo,
    ) -> datetime:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate = (candidate + timedelta(days=1)).astimezone(timezone)
        return candidate
