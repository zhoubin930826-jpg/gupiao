from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.market_store import MarketDataStore
from app.services.recommendation_service import RecommendationService
from app.services.scheduler_service import TaskScheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    task_scheduler = TaskScheduler()
    session = SessionLocal()
    try:
        init_db(session)
    finally:
        session.close()

    market_store = MarketDataStore(settings.market_database_path)
    market_store.initialize()
    session = SessionLocal()
    try:
        RecommendationService.ensure_seed(session, market_store)
    finally:
        session.close()
    task_scheduler.start()
    try:
        yield
    finally:
        task_scheduler.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)
