from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

import duckdb
from sqlalchemy.orm import Session

from app.core.market_scope import is_a_share_symbol
from app.models.recommendation import RecommendationJournal
from app.services.market_store import MarketDataStore

WINDOWS = (5, 10, 20)


class RecommendationReviewService:
    @classmethod
    def build_review(
        cls,
        db: Session,
        market_store: MarketDataStore,
        *,
        limit: int = 120,
    ) -> dict[str, object]:
        journal_rows = (
            db.query(RecommendationJournal)
            .order_by(RecommendationJournal.generated_at.desc(), RecommendationJournal.id.desc())
            .all()
        )
        journal_rows = [row for row in journal_rows if is_a_share_symbol(row.symbol)][:limit]
        if not journal_rows:
            return {
                "total_samples": 0,
                "window_metrics": [],
                "recent_runs": [],
                "top_hits": [],
                "top_misses": [],
                "samples": [],
            }

        symbols = sorted({row.symbol for row in journal_rows})
        price_map = cls._build_price_map(market_store, symbols)
        sample_rows = [cls._serialize_row(row, price_map.get(row.symbol, [])) for row in journal_rows]

        sortable = [row for row in sample_rows if row.get("expected_return") is not None]
        top_hits = sorted(sortable, key=lambda item: float(item["expected_return"]), reverse=True)[:5]
        top_misses = sorted(sortable, key=lambda item: float(item["expected_return"]))[:5]

        return {
            "total_samples": len(sample_rows),
            "window_metrics": [cls._build_window_metric(sample_rows, window) for window in WINDOWS],
            "recent_runs": cls._build_run_summaries(sample_rows),
            "top_hits": top_hits,
            "top_misses": top_misses,
            "samples": sample_rows,
        }

    @staticmethod
    def _build_price_map(
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

        grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for symbol, trade_date, close in rows:
            grouped[str(symbol)].append((str(trade_date), float(close)))
        return grouped

    @classmethod
    def _serialize_row(
        cls,
        row: RecommendationJournal,
        price_rows: list[tuple[str, float]],
    ) -> dict[str, object]:
        publish_date = row.generated_at.date()
        start_index = cls._locate_start_index(price_rows, publish_date)
        latest_known_price = price_rows[-1][1] if price_rows else None

        payload = {
            "run_key": row.run_key,
            "generated_at": row.generated_at.isoformat(timespec="seconds"),
            "symbol": row.symbol,
            "name": row.name,
            "score": row.score,
            "source": row.source,
            "entry_window": row.entry_window,
            "expected_holding_days": row.expected_holding_days,
            "thesis": row.thesis,
            "tags": json.loads(row.tags_json),
            "price_at_publish": round(row.price_at_publish, 2),
            "latest_known_price": round(latest_known_price, 2) if latest_known_price is not None else None,
            "return_5d": None,
            "return_10d": None,
            "return_20d": None,
            "expected_return": None,
        }

        if start_index is None or row.price_at_publish <= 0:
            return payload

        for window in WINDOWS:
            value = cls._forward_return(price_rows, start_index, window, row.price_at_publish)
            payload[f"return_{window}d"] = value

        payload["expected_return"] = cls._forward_return(
            price_rows,
            start_index,
            row.expected_holding_days,
            row.price_at_publish,
        )
        return payload

    @staticmethod
    def _locate_start_index(price_rows: list[tuple[str, float]], publish_date: date) -> int | None:
        if not price_rows:
            return None
        publish_text = publish_date.isoformat()
        for index, (trade_date, _) in enumerate(price_rows):
            if trade_date >= publish_text:
                return index
        return None

    @staticmethod
    def _forward_return(
        price_rows: list[tuple[str, float]],
        start_index: int,
        lookahead: int,
        base_price: float,
    ) -> float | None:
        target_index = start_index + lookahead
        if target_index >= len(price_rows):
            return None
        target_close = price_rows[target_index][1]
        return round((target_close / base_price - 1) * 100, 2)

    @staticmethod
    def _build_window_metric(rows: list[dict[str, object]], window: int) -> dict[str, object]:
        values = [
            float(row[f"return_{window}d"])
            for row in rows
            if row.get(f"return_{window}d") is not None
        ]
        if not values:
            return {
                "window_days": window,
                "sample_size": 0,
                "win_rate": None,
                "avg_return": None,
                "best_return": None,
                "worst_return": None,
            }
        return {
            "window_days": window,
            "sample_size": len(values),
            "win_rate": round(sum(1 for value in values if value > 0) / len(values) * 100, 2),
            "avg_return": round(sum(values) / len(values), 2),
            "best_return": round(max(values), 2),
            "worst_return": round(min(values), 2),
        }

    @staticmethod
    def _build_run_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            buckets[str(row["run_key"])].append(row)

        summaries: list[dict[str, object]] = []
        for run_key, items in buckets.items():
            first = items[0]
            summaries.append(
                {
                    "run_key": run_key,
                    "generated_at": str(first["generated_at"]),
                    "source": str(first["source"]),
                    "picks": len(items),
                    "avg_score": round(sum(int(item["score"]) for item in items) / len(items), 1),
                    "avg_return_5d": _average_optional(item.get("return_5d") for item in items),
                    "avg_return_10d": _average_optional(item.get("return_10d") for item in items),
                    "avg_return_20d": _average_optional(item.get("return_20d") for item in items),
                    "avg_expected_return": _average_optional(item.get("expected_return") for item in items),
                }
            )

        summaries.sort(key=lambda item: str(item["generated_at"]), reverse=True)
        return summaries[:12]


def _average_optional(values: object) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return None
    return round(sum(filtered) / len(filtered), 2)
