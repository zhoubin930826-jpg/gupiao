from fastapi import APIRouter

from app.api.routes import (
    alerts,
    dashboard,
    data_sources,
    health,
    portfolio,
    recommendations,
    stocks,
    strategies,
    tasks,
    trade_plans,
    watchlist,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(data_sources.router, prefix="/data-sources", tags=["data-sources"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
)
api_router.include_router(trade_plans.router, prefix="/trade-plans", tags=["trade-plans"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
