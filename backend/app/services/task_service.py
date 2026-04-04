from __future__ import annotations

from threading import Lock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.task import SyncTaskRecord
from app.schemas.market import SyncTask
from app.services.akshare_collector import AkshareCollector
from app.services.alert_service import AlertService
from app.services.market_store import MarketDataStore
from app.services.recommendation_service import RecommendationService
from app.services.signal_engine import StrategyWeights
from app.services.strategy_service import StrategyService


class TaskService:
    _job_lock = Lock()

    def __init__(self, db: Session, market_store: MarketDataStore):
        self.db = db
        self.market_store = market_store
        self.settings = get_settings()
        self.collector = AkshareCollector()

    def list_tasks(self) -> list[dict[str, object]]:
        rows = self.db.query(SyncTaskRecord).order_by(SyncTaskRecord.id.asc()).all()
        return [self._serialize_task(row) for row in rows]

    def prepare_market_sync(self) -> tuple[dict[str, object], bool]:
        timezone = ZoneInfo(self.settings.app_timezone)
        now = datetime.now(timezone)
        task = self.db.query(SyncTaskRecord).filter_by(task_key="market-sync").first()
        if task is None:
            raise RuntimeError("Market sync task missing.")

        if task.status == "running":
            return self._serialize_task(task), False

        task.status = "running"
        task.message = "任务已提交，后台正在同步市场数据..."
        task.source = self.market_store.current_source()
        task.last_run_at = now
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return self._serialize_task(task), True

    @classmethod
    def run_market_sync_job(cls) -> None:
        if not cls._job_lock.acquire(blocking=False):
            return
        session = SessionLocal()
        settings = get_settings()
        service = cls(db=session, market_store=MarketDataStore(settings.market_database_path))
        try:
            service._perform_market_sync()
        finally:
            session.close()
            cls._job_lock.release()

    @classmethod
    def sync_task_plans(cls) -> None:
        settings = get_settings()
        timezone = ZoneInfo(settings.app_timezone)
        now = datetime.now(timezone)
        schedule_map = cls._schedule_map()

        session = SessionLocal()
        try:
            rows = session.query(SyncTaskRecord).order_by(SyncTaskRecord.id.asc()).all()
            for row in rows:
                plan = schedule_map.get(row.task_key)
                if plan is None:
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

    def _perform_market_sync(self) -> None:
        timezone = ZoneInfo(self.settings.app_timezone)
        now = datetime.now(timezone)
        task = self.db.query(SyncTaskRecord).filter_by(task_key="market-sync").first()
        if task is None:
            raise RuntimeError("Market sync task missing.")

        task.status = "running"
        task.message = "正在刷新市场数据..."
        self.db.add(task)
        self.db.commit()

        profile = StrategyService.read_config(self.db)
        strategy = StrategyWeights.from_mapping(profile.__dict__)
        source = "sample"
        final_status = "success"
        final_message = "已刷新示例数据。"

        try:
            if self.settings.enable_akshare_sync:
                dataset, message = self.collector.collect_market_dataset(strategy=strategy)
                if dataset:
                    self.market_store.refresh_snapshot_records(
                        dataset.snapshot_records,
                        source="akshare-live",
                        history_rows=dataset.history_rows,
                    )
                    source = "akshare-live"
                    final_message = message
                else:
                    self.market_store.seed_demo_dataset()
                    source = "sample"
                    final_status = "warning"
                    final_message = f"{message} 已回退到示例数据。"
            else:
                self.market_store.seed_demo_dataset()
                final_message = "已刷新示例数据，可在 .env 中打开 ENABLE_AKSHARE_SYNC。"
        except Exception as exc:  # pragma: no cover - background protection
            self.market_store.seed_demo_dataset()
            source = "sample"
            final_status = "warning"
            final_message = f"同步失败: {exc}，已回退到示例数据。"

        task.status = final_status
        task.last_run_at = now
        task.next_run_at = (
            self._next_occurrence(
                hour=self.settings.scheduler_market_hour,
                minute=self.settings.scheduler_market_minute,
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
            )

        for dependent_key in ("signal-rescore", "recommendation-publish"):
            dependent = self.db.query(SyncTaskRecord).filter_by(task_key=dependent_key).first()
            if dependent is None:
                continue
            dependent.status = "success"
            dependent.last_run_at = now
            next_hour, next_minute = self._schedule_map()[dependent_key]
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
            dependent.message = "已基于最新市场数据刷新。"
            dependent.source = source
            self.db.add(dependent)

        self.db.commit()

        try:
            AlertService.refresh_alerts(self.db, self.market_store)
        except Exception:  # pragma: no cover - alert refresh should not break sync
            self.db.rollback()

    @staticmethod
    def _serialize_task(task: SyncTaskRecord) -> dict[str, object]:
        return SyncTask(
            task_key=task.task_key,
            name=task.name,
            status=task.status,  # type: ignore[arg-type]
            schedule=task.schedule,
            last_run_at=task.last_run_at.isoformat(timespec="seconds") if task.last_run_at else None,
            next_run_at=task.next_run_at.isoformat(timespec="seconds") if task.next_run_at else None,
            message=task.message,
            source=task.source,
        ).model_dump()

    @staticmethod
    def _schedule_map() -> dict[str, tuple[int, int]]:
        settings = get_settings()
        return {
            "market-sync": (settings.scheduler_market_hour, settings.scheduler_market_minute),
            "signal-rescore": (settings.scheduler_signal_hour, settings.scheduler_signal_minute),
            "recommendation-publish": (settings.scheduler_publish_hour, settings.scheduler_publish_minute),
        }

    @staticmethod
    def _schedule_label(hour: int, minute: int) -> str:
        return f"每日 {hour:02d}:{minute:02d}"

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
