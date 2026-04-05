from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_scope
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.market import SyncTask
from app.services.market_store import MarketDataStore
from app.services.task_service import TaskService

router = APIRouter()


def get_task_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskService:
    return TaskService(db=db, market_store=MarketDataStore(settings.market_database_path))


@router.get("", response_model=list[SyncTask])
def list_tasks(
    task_service: TaskService = Depends(get_task_service),
    market: str = Depends(get_market_scope),
) -> list[SyncTask]:
    return [SyncTask.model_validate(row) for row in task_service.list_tasks(market)]


@router.post("/sync-market", response_model=SyncTask)
def sync_market(
    background_tasks: BackgroundTasks,
    task_service: TaskService = Depends(get_task_service),
    market: str = Depends(get_market_scope),
) -> SyncTask:
    task_payload, should_schedule = task_service.prepare_market_sync(market)
    if should_schedule:
        background_tasks.add_task(TaskService.run_market_sync_job, market)
    return SyncTask.model_validate(task_payload)
