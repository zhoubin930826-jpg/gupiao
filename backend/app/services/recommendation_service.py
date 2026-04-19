from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.market_scope import is_a_share_symbol
from app.models.recommendation import RecommendationJournal
from app.services.market_store import MarketDataStore


class RecommendationService:
    @staticmethod
    def publish_current_run(
        db: Session,
        market_store: MarketDataStore,
        *,
        generated_at: datetime,
        source: str,
    ) -> None:
        recommendations = market_store.get_recommendations()
        if not recommendations:
            return

        run_key = generated_at.strftime("%Y%m%d%H%M%S")
        rows = [
            RecommendationJournal(
                run_key=run_key,
                symbol=str(item["symbol"]),
                name=str(item["name"]),
                score=int(item["score"]),
                entry_window=str(item["entry_window"]),
                expected_holding_days=int(item["expected_holding_days"]),
                thesis=str(item["thesis"]),
                risk=str(item["risk"]),
                source=source,
                tags_json=json.dumps(item.get("tags", []), ensure_ascii=False),
                price_at_publish=float(item.get("latest_price") or 0.0),
                generated_at=generated_at,
            )
            for item in recommendations[:8]
        ]
        db.add_all(rows)
        db.commit()

    @staticmethod
    def ensure_seed(db: Session, market_store: MarketDataStore) -> None:
        source = market_store.current_source()
        if source == "sample":
            has_sample_seed = any(
                is_a_share_symbol(row.symbol)
                for row in db.query(RecommendationJournal)
                .filter(RecommendationJournal.run_key.like("sample-%"))
                .all()
            )
            if not has_sample_seed:
                RecommendationService._seed_sample_history(db, market_store)

        has_current_run = any(
            is_a_share_symbol(row.symbol)
            for row in db.query(RecommendationJournal)
            .filter(RecommendationJournal.run_key.not_like("sample-%"))
            .all()
        )
        if has_current_run:
            return
        RecommendationService.publish_current_run(
            db,
            market_store,
            generated_at=datetime.now(ZoneInfo(get_settings().app_timezone)),
            source=source,
        )

    @staticmethod
    def list_journal(
        db: Session,
        market_store: MarketDataStore,
        *,
        limit: int = 24,
    ) -> list[dict[str, object]]:
        rows = (
            db.query(RecommendationJournal)
            .order_by(RecommendationJournal.generated_at.desc(), RecommendationJournal.id.desc())
            .all()
        )
        rows = [row for row in rows if is_a_share_symbol(row.symbol)][:limit]
        if not rows:
            return []

        latest_prices = market_store.get_latest_snapshot_map([row.symbol for row in rows])
        journal: list[dict[str, object]] = []
        for row in rows:
            current_price = latest_prices.get(row.symbol)
            current_return = None
            if current_price is not None and row.price_at_publish > 0:
                current_return = round((current_price / row.price_at_publish - 1) * 100, 2)
            journal.append(
                {
                    "run_key": row.run_key,
                    "generated_at": row.generated_at.isoformat(timespec="seconds"),
                    "symbol": row.symbol,
                    "name": row.name,
                    "score": row.score,
                    "entry_window": row.entry_window,
                    "expected_holding_days": row.expected_holding_days,
                    "thesis": row.thesis,
                    "risk": row.risk,
                    "source": row.source,
                    "tags": json.loads(row.tags_json),
                    "price_at_publish": round(row.price_at_publish, 2),
                    "current_price": round(current_price, 2) if current_price is not None else None,
                    "current_return": current_return,
                }
            )
        return journal

    @staticmethod
    def _seed_sample_history(
        db: Session,
        market_store: MarketDataStore,
    ) -> None:
        market = DEFAULT_MARKET_SCOPE
        recommendations = market_store.get_recommendations()
        if not recommendations:
            return

        symbols = [str(item["symbol"]) for item in recommendations]
        settings = get_settings()
        placeholders = ",".join(["?"] * len(symbols))
        with duckdb.connect(market_store.db_path) as conn:
            price_rows = conn.execute(
                f"""
                select symbol, date, close
                from stock_price
                where symbol in ({placeholders})
                order by symbol, date
                """,
                symbols,
            ).fetchall()

        history_map: dict[str, list[tuple[str, float]]] = {}
        for symbol, trade_date, close in price_rows:
            history_map.setdefault(str(symbol), []).append((str(trade_date), float(close)))
        if not history_map:
            return

        reference_dates = [row[0] for row in history_map.get(symbols[0], [])]
        eligible_dates = reference_dates[:-20]
        if not eligible_dates:
            return

        selected_dates = eligible_dates[max(0, len(eligible_dates) - 25) :: 5][-5:]
        if not selected_dates:
            selected_dates = eligible_dates[-min(5, len(eligible_dates)) :]

        timezone = ZoneInfo(settings.app_timezone)
        new_rows: list[RecommendationJournal] = []
        for trade_date in selected_dates:
            run_key = f"sample-{market}-{trade_date.replace('-', '')}"
            exists = db.query(RecommendationJournal).filter_by(run_key=run_key).first()
            if exists is not None:
                continue

            generated_at = datetime.fromisoformat(trade_date).replace(
                hour=18,
                minute=30,
                second=0,
                microsecond=0,
                tzinfo=timezone,
            )
            for item in recommendations[:8]:
                history_rows = history_map.get(str(item["symbol"]), [])
                price_at_publish = next(
                    (close for row_date, close in history_rows if row_date == trade_date),
                    None,
                )
                if price_at_publish is None:
                    continue
                new_rows.append(
                    RecommendationJournal(
                        run_key=run_key,
                        symbol=str(item["symbol"]),
                        name=str(item["name"]),
                        score=int(item["score"]),
                        entry_window=str(item["entry_window"]),
                        expected_holding_days=int(item["expected_holding_days"]),
                        thesis=str(item["thesis"]),
                        risk=str(item["risk"]),
                        source="sample",
                        tags_json=json.dumps(item.get("tags", []), ensure_ascii=False),
                        price_at_publish=float(price_at_publish),
                        generated_at=generated_at,
                    )
                )

        if new_rows:
            db.add_all(new_rows)
            db.commit()
