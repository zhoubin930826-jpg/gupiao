from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import engine
from app.models.alert import AlertEvent
from app.models.base import Base
from app.models.portfolio import PortfolioPosition, PortfolioProfile
from app.models.recommendation import RecommendationJournal
from app.models.strategy import StrategyProfile
from app.models.task import SyncTaskRecord
from app.models.trade_plan import TradePlanEntry
from app.models.watchlist import WatchlistEntry


def init_db(session: Session) -> None:
    settings = get_settings()
    timezone = ZoneInfo(settings.app_timezone)
    now = datetime.now(timezone)

    Base.metadata.create_all(bind=engine)

    if session.query(StrategyProfile).first() is None:
        session.add(
            StrategyProfile(
                technical_weight=35,
                fundamental_weight=25,
                money_flow_weight=25,
                sentiment_weight=15,
                rebalance_cycle="weekly",
                min_turnover=2.5,
                min_listing_days=180,
                exclude_st=True,
                exclude_new_shares=True,
            )
        )

    if session.query(PortfolioProfile).first() is None:
        session.add(
            PortfolioProfile(
                name="本地账户",
                initial_capital=500000,
                benchmark="沪深300",
                notes="用于估算组合资产、仓位利用率和持仓盈亏。",
            )
        )

    if session.query(SyncTaskRecord).count() == 0:
        next_run = now + timedelta(days=1)
        session.add_all(
            [
                SyncTaskRecord(
                    task_key="market-sync",
                    name="市场数据同步",
                    status="idle",
                    schedule="每日 18:10",
                    message="同步 A 股快照与市场概览。",
                    source="sample",
                    next_run_at=next_run.replace(hour=18, minute=10, second=0, microsecond=0),
                ),
                SyncTaskRecord(
                    task_key="signal-rescore",
                    name="因子评分刷新",
                    status="idle",
                    schedule="每日 18:20",
                    message="基于最新行情刷新四维评分。",
                    source="sample",
                    next_run_at=next_run.replace(hour=18, minute=20, second=0, microsecond=0),
                ),
                SyncTaskRecord(
                    task_key="recommendation-publish",
                    name="推荐清单生成",
                    status="idle",
                    schedule="每日 18:30",
                    message="输出高分候选和推荐理由。",
                    source="sample",
                    next_run_at=next_run.replace(hour=18, minute=30, second=0, microsecond=0),
                ),
            ]
        )

    session.query(RecommendationJournal).count()
    session.query(AlertEvent).count()
    session.query(PortfolioPosition).count()
    session.query(PortfolioProfile).count()
    session.query(TradePlanEntry).count()
    session.query(WatchlistEntry).count()

    session.commit()
