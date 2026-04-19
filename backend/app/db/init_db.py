from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

from app.models.data_source import DataSourceStatus
from app.core.config import get_settings
from app.core.market_scope import DEFAULT_MARKET_SCOPE, SUPPORTED_MARKETS, market_label, scoped_key
from app.db.session import engine
from app.models.alert import AlertEvent
from app.models.base import Base
from app.models.portfolio import PortfolioPosition, PortfolioProfile
from app.models.recommendation import RecommendationJournal
from app.models.strategy import StrategyProfile
from app.models.task import SyncTaskRecord
from app.models.trade_plan import TradePlanEntry
from app.models.watchlist import WatchlistEntry
from app.services.data_source_service import DataSourceService
from app.services.task_service import TaskService


def init_db(session: Session) -> None:
    settings = get_settings()
    timezone = ZoneInfo(settings.app_timezone)
    now = datetime.now(timezone)

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    strategy_columns = {column["name"] for column in inspector.get_columns("strategy_profiles")}
    if "market" not in strategy_columns:
        session.execute(text("alter table strategy_profiles add column market varchar(8) default 'cn'"))
    session.execute(text("update strategy_profiles set market = 'cn' where market is null or market = ''"))
    portfolio_columns = {column["name"] for column in inspector.get_columns("portfolio_profiles")}
    if "market" not in portfolio_columns:
        session.execute(text("alter table portfolio_profiles add column market varchar(8) default 'cn'"))
    session.execute(text("update portfolio_profiles set market = 'cn' where market is null or market = ''"))
    session.execute(text("delete from strategy_profiles where market != 'cn'"))
    session.execute(text("delete from portfolio_profiles where market != 'cn'"))
    session.execute(text("delete from sync_tasks where task_key not like 'cn:%'"))
    session.execute(text("delete from data_source_statuses where provider_key not like 'cn:%'"))

    for market in SUPPORTED_MARKETS:
        if session.query(StrategyProfile).filter_by(market=market).first() is None:
            session.add(
                StrategyProfile(
                    market=market,
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

        if session.query(PortfolioProfile).filter_by(market=market).first() is None:
            session.add(
                PortfolioProfile(
                    market=market,
                    name=f"{market_label(market)}账户",
                    initial_capital=500000,
                    benchmark="沪深300",
                    notes=f"用于估算 {market_label(market)} 组合资产、仓位利用率和持仓盈亏。",
                )
            )

    next_run = now + timedelta(days=1)
    for market in SUPPORTED_MARKETS:
        market_schedule = TaskService._schedule_map(market)
        market_hour, market_minute = market_schedule["market-sync"]
        signal_hour, signal_minute = market_schedule["signal-rescore"]
        publish_hour, publish_minute = market_schedule["recommendation-publish"]
        schedule = f"每日 {market_hour:02d}:{market_minute:02d}"
        next_market_run = next_run.replace(
            hour=market_hour,
            minute=market_minute,
            second=0,
            microsecond=0,
        )
        defaults = [
            (
                "market-sync",
                "市场数据同步",
                f"同步 {market_label(market)} 股票池与市场概览。",
                schedule,
                next_market_run,
            ),
            (
                "signal-rescore",
                "因子评分刷新",
                f"基于最新 {market_label(market)} 行情刷新四维评分。",
                f"每日 {signal_hour:02d}:{signal_minute:02d}",
                next_run.replace(hour=signal_hour, minute=signal_minute, second=0, microsecond=0),
            ),
            (
                "recommendation-publish",
                "推荐清单生成",
                f"输出 {market_label(market)} 高分候选和推荐理由。",
                f"每日 {publish_hour:02d}:{publish_minute:02d}",
                next_run.replace(hour=publish_hour, minute=publish_minute, second=0, microsecond=0),
            ),
        ]
        for raw_key, name, message, item_schedule, next_run_at in defaults:
            task_key = scoped_key(market, raw_key)
            if session.query(SyncTaskRecord).filter_by(task_key=task_key).first() is not None:
                continue
            session.add(
                SyncTaskRecord(
                    task_key=task_key,
                    name=name,
                    status="idle",
                    schedule=item_schedule,
                    message=message,
                    source="sample",
                    next_run_at=next_run_at,
                )
            )

    session.query(DataSourceStatus).count()
    session.query(RecommendationJournal).count()
    session.query(AlertEvent).count()
    session.query(PortfolioPosition).count()
    session.query(PortfolioProfile).count()
    session.query(TradePlanEntry).count()
    session.query(WatchlistEntry).count()

    session.commit()
    DataSourceService.sync_catalog(session, DEFAULT_MARKET_SCOPE)
