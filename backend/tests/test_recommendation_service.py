from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.market_scope import DEFAULT_MARKET_SCOPE
from app.models.base import Base
from app.services.market_store import MarketDataStore
from app.services.recommendation_service import RecommendationService


def test_ensure_seed_bootstraps_sample_history_on_fresh_db(tmp_path) -> None:
    market_store = MarketDataStore(str(tmp_path / "market.duckdb"))
    market_store.initialize()

    engine = create_engine(f"sqlite:///{(tmp_path / 'business.db').as_posix()}")
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        RecommendationService.ensure_seed(session, market_store)
        rows = RecommendationService.list_journal(session, market_store, limit=200)
        assert rows
        assert all(row["source"] == "sample" for row in rows)
        assert any(row["run_key"].startswith(f"sample-{DEFAULT_MARKET_SCOPE}-") for row in rows)
    finally:
        session.close()
