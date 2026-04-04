from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.services.task_service import TaskService


class TaskScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.timezone = ZoneInfo(self.settings.app_timezone)
        self.scheduler = BackgroundScheduler(
            timezone=self.timezone,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            },
        )
        self.started = False

    def start(self) -> None:
        TaskService.sync_task_plans()
        if not self.settings.enable_task_scheduler:
            return

        self.scheduler.add_job(
            TaskService.run_market_sync_job,
            trigger=CronTrigger(
                hour=self.settings.scheduler_market_hour,
                minute=self.settings.scheduler_market_minute,
                timezone=self.timezone,
            ),
            id="market-sync",
            replace_existing=True,
        )
        self.scheduler.start()
        self.started = True
        TaskService.sync_task_plans()

    def shutdown(self) -> None:
        if self.started and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.started = False
