from typing import Annotated

from fastapi import Query

from app.core.market_scope import MarketScope, normalize_market_scope


def get_market_scope(
    market: Annotated[str | None, Query(description="市场范围: cn / hk / us")] = None,
) -> MarketScope:
    return normalize_market_scope(market)
