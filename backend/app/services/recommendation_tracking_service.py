from __future__ import annotations

from datetime import date

import duckdb

from app.services.market_store import MarketDataStore


def build_price_map(
    market_store: MarketDataStore,
    symbols: list[str],
) -> dict[str, list[tuple[str, float]]]:
    if not symbols:
        return {}

    placeholders = ",".join(["?"] * len(symbols))
    with duckdb.connect(market_store.db_path) as conn:
        rows = conn.execute(
            f"""
            select symbol, date, close
            from stock_price
            where symbol in ({placeholders})
            order by symbol, date
            """,
            symbols,
        ).fetchall()

    grouped: dict[str, list[tuple[str, float]]] = {}
    for symbol, trade_date, close in rows:
        grouped.setdefault(str(symbol), []).append((str(trade_date), float(close)))
    return grouped


def locate_start_index(price_rows: list[tuple[str, float]], publish_date: date) -> int | None:
    publish_text = publish_date.isoformat()
    for index, (trade_date, _) in enumerate(price_rows):
        if trade_date >= publish_text:
            return index
    return None


def matured_for_window(price_rows: list[tuple[str, float]], publish_date: date, window: int) -> bool:
    start_index = locate_start_index(price_rows, publish_date)
    return start_index is not None and start_index + window < len(price_rows)


def traded_days_since_publish(price_rows: list[tuple[str, float]], publish_date: date) -> int:
    start_index = locate_start_index(price_rows, publish_date)
    if start_index is None:
        return 0
    return max(len(price_rows) - start_index - 1, 0)
