from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from app.core.market_scope import (
    DEFAULT_MARKET_SCOPE,
    SUPPORTED_MARKETS,
    normalize_market_scope,
)
from app.services.capital_flow_service import (
    build_placeholder_market_capital_flow_overview,
    build_placeholder_stock_capital_flow_analysis,
    build_sample_market_capital_flow_overview,
    build_sample_stock_capital_flow_analysis,
    build_cn_stock_capital_flow_analysis_from_frame,
    collect_cn_stock_capital_flow_analysis,
)
from app.services.sample_market import (
    build_demo_snapshot_records,
    build_history_records,
    build_industry_heat_records,
    build_market_pulse_records,
    build_recommendation_records,
    dumps_json,
)
from app.services.event_analysis_service import build_event_analysis
from app.services.market_environment_service import (
    build_market_breadth_from_records,
    collect_market_benchmark_records,
    build_sample_benchmark_records,
)
from app.services.market_context_service import build_market_context
from app.services.move_analysis_service import build_move_analysis


class MarketDataStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def initialize(self) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            count = conn.execute("select count(*) from stock_snapshot").fetchone()[0]
        if count == 0:
            self.seed_demo_dataset()
            return
        for market in SUPPORTED_MARKETS:
            self._ensure_market_seed(market)
        self._backfill_event_analysis()
        self._backfill_move_analysis()
        self._backfill_capital_flow_analysis()

    def seed_demo_dataset(self, market: str | None = None) -> None:
        if market is None:
            for scope in SUPPORTED_MARKETS:
                self.seed_demo_dataset(scope)
            return
        normalized = normalize_market_scope(market)
        self.refresh_snapshot_records(
            build_demo_snapshot_records(normalized),
            source="sample",
            market=normalized,
        )

    def _ensure_market_seed(self, market: str) -> None:
        normalized_market = normalize_market_scope(market)
        with self._connect() as conn:
            count = conn.execute(
                "select count(*) from stock_snapshot where market = ?",
                [normalized_market],
            ).fetchone()[0]
        if count == 0:
            self.seed_demo_dataset(normalized_market)

    def refresh_snapshot_records(
        self,
        records: list[dict[str, object]],
        source: str,
        market: str = DEFAULT_MARKET_SCOPE,
        history_rows: list[dict[str, object]] | None = None,
        benchmark_rows: list[dict[str, object]] | None = None,
        breadth_snapshot: dict[str, object] | None = None,
        market_capital_flow: dict[str, object] | None = None,
        lhb_rows: list[dict[str, object]] | None = None,
    ) -> None:
        normalized_market = normalize_market_scope(market)
        history_rows = history_rows or build_history_records(records)
        benchmark_rows = benchmark_rows if benchmark_rows is not None else (
            build_sample_benchmark_records(records, normalized_market) if source == "sample" else []
        )
        breadth_snapshot = breadth_snapshot or build_market_breadth_from_records(records, normalized_market)
        market_capital_flow = market_capital_flow or (
            build_sample_market_capital_flow_overview(records, normalized_market)
            if source == "sample"
            else build_placeholder_market_capital_flow_overview(normalized_market)
        )
        lhb_rows = lhb_rows or []
        history_df = pd.DataFrame(history_rows)
        if not history_df.empty and "amount" in history_df.columns:
            history_df = history_df.drop(columns=["amount"])
        if not history_df.empty:
            history_df["market"] = normalized_market
        records = self._ensure_event_analysis(records)
        records = self._ensure_move_analysis(records, history_df)
        records = self._ensure_capital_flow_analysis(records, source=source, market=normalized_market)
        industry_rows = build_industry_heat_records(records)
        pulse_rows = build_market_pulse_records(records)
        recommendation_rows = build_recommendation_records(records)
        updated_at = datetime.now().isoformat(timespec="seconds")

        snapshot_df = pd.DataFrame(
            [
                {
                    **record,
                    "market": normalized_market,
                    "tags_json": dumps_json(record["tags"]),
                    "thesis_points_json": dumps_json(record["thesis_points"]),
                    "risk_notes_json": dumps_json(record["risk_notes"]),
                    "signal_breakdown_json": dumps_json(record["signal_breakdown"]),
                    "fundamental_json": dumps_json(record.get("fundamental")),
                    "move_analysis_json": dumps_json(record.get("move_analysis")),
                    "event_analysis_json": dumps_json(record.get("event_analysis")),
                    "capital_flow_json": dumps_json(record.get("capital_flow_analysis")),
                    "updated_at": updated_at,
                }
                for record in records
            ]
        )
        snapshot_df = snapshot_df.drop(
            columns=[
                "tags",
                "thesis_points",
                "risk_notes",
                "signal_breakdown",
                "fundamental",
                "move_analysis",
                "event_analysis",
                "capital_flow_analysis",
            ],
            errors="ignore",
        )
        snapshot_df = snapshot_df[
            [
                "symbol",
                "name",
                "board",
                "industry",
                "latest_price",
                "change_pct",
                "turnover_ratio",
                "pe_ttm",
                "market_cap",
                "score",
                "thesis",
                "risk",
                "entry_window",
                "expected_holding_days",
                "market",
                "updated_at",
                "tags_json",
                "thesis_points_json",
                "risk_notes_json",
                "signal_breakdown_json",
                "fundamental_json",
                "move_analysis_json",
                "event_analysis_json",
                "capital_flow_json",
            ]
        ]
        industry_df = pd.DataFrame(industry_rows)
        pulse_df = pd.DataFrame(pulse_rows)
        recommendation_df = pd.DataFrame(
            [
                {
                    **row,
                    "market": normalized_market,
                    "updated_at": updated_at,
                    "tags_json": dumps_json(row["tags"]),
                }
                for row in recommendation_rows
            ]
        )
        recommendation_df = recommendation_df.drop(columns=["tags"])
        recommendation_df = recommendation_df[
            [
                "symbol",
                "name",
                "score",
                "entry_window",
                "expected_holding_days",
                "market",
                "thesis",
                "risk",
                "updated_at",
                "tags_json",
            ]
        ]
        if not industry_df.empty:
            industry_df["market"] = normalized_market
        if not pulse_df.empty:
            pulse_df["market"] = normalized_market
        metadata_df = pd.DataFrame([{"market": normalized_market, "source": source, "updated_at": updated_at}])
        benchmark_df = pd.DataFrame(
            [
                {
                    **row,
                    "market": normalized_market,
                }
                for row in benchmark_rows
            ],
            columns=[
                "market",
                "code",
                "name",
                "latest_price",
                "change_pct",
                "return_20d",
                "trend",
                "takeaway",
            ],
        )
        breadth_df = pd.DataFrame(
            [
                {
                    **breadth_snapshot,
                    "market": normalized_market,
                }
            ]
        )
        capital_flow_df = pd.DataFrame(
            [
                {
                    "market": normalized_market,
                    "summary_json": dumps_json(market_capital_flow),
                    "updated_at": updated_at,
                }
            ]
        )
        lhb_df = pd.DataFrame(
            [
                {
                    **row,
                    "market": normalized_market,
                }
                for row in lhb_rows
            ],
            columns=[
                "market",
                "symbol",
                "name",
                "recent_list_date",
                "close_price",
                "change_pct",
                "on_list_count",
                "net_buy_amount",
                "buy_amount",
                "sell_amount",
                "total_amount",
                "institution_buy_count",
                "institution_sell_count",
                "institution_net_buy",
                "return_1m",
                "return_3m",
                "return_6m",
                "return_1y",
            ],
        )

        with self._connect() as conn:
            self._ensure_schema(conn)
            for table_name in (
                "stock_snapshot",
                "stock_price",
                "industry_heat",
                "market_pulse",
                "recommendation_item",
                "market_benchmark",
                "market_breadth",
                "market_capital_flow",
                "stock_lhb_stat",
                "sync_metadata",
            ):
                conn.execute(f"delete from {table_name} where market = ?", [normalized_market])

            conn.register("snapshot_df", snapshot_df)
            conn.register("history_df", history_df)
            conn.register("industry_df", industry_df)
            conn.register("pulse_df", pulse_df)
            conn.register("recommendation_df", recommendation_df)
            conn.register("metadata_df", metadata_df)
            conn.register("benchmark_df", benchmark_df)
            conn.register("breadth_df", breadth_df)
            conn.register("capital_flow_df", capital_flow_df)
            conn.register("lhb_df", lhb_df)

            conn.execute(
                """
                insert into stock_snapshot (
                    symbol,
                    name,
                    board,
                    industry,
                    latest_price,
                    change_pct,
                    turnover_ratio,
                    pe_ttm,
                    market_cap,
                    score,
                    thesis,
                    risk,
                    entry_window,
                    expected_holding_days,
                    market,
                    updated_at,
                    tags_json,
                    thesis_points_json,
                    risk_notes_json,
                    signal_breakdown_json,
                    fundamental_json,
                    move_analysis_json,
                    event_analysis_json,
                    capital_flow_json
                )
                select * from snapshot_df
                """
            )
            conn.execute(
                """
                insert into stock_price (symbol, date, open, close, low, high, volume, ma5, ma20, market)
                select symbol, date, open, close, low, high, volume, ma5, ma20, market
                from history_df
                """
            )
            conn.execute(
                """
                insert into industry_heat (industry, score, momentum, market)
                select industry, score, momentum, market
                from industry_df
                """
            )
            conn.execute(
                """
                insert into market_pulse (date, score, turnover, market)
                select date, score, turnover, market
                from pulse_df
                """
            )
            conn.execute(
                """
                insert into recommendation_item (
                    symbol,
                    name,
                    score,
                    entry_window,
                    expected_holding_days,
                    market,
                    thesis,
                    risk,
                    updated_at,
                    tags_json
                )
                select * from recommendation_df
                """
            )
            conn.execute(
                """
                insert into market_benchmark (
                    market,
                    code,
                    name,
                    latest_price,
                    change_pct,
                    return_20d,
                    trend,
                    takeaway
                )
                select
                    market,
                    code,
                    name,
                    latest_price,
                    change_pct,
                    return_20d,
                    trend,
                    takeaway
                from benchmark_df
                """
            )
            conn.execute(
                """
                insert into market_breadth (
                    market,
                    scope_label,
                    total_count,
                    advancers,
                    decliners,
                    advance_ratio,
                    strong_count,
                    strong_ratio,
                    avg_change,
                    avg_turnover,
                    top_industry,
                    top_two_share,
                    limit_up_like,
                    limit_down_like,
                    summary
                )
                select
                    market,
                    scope_label,
                    total_count,
                    advancers,
                    decliners,
                    advance_ratio,
                    strong_count,
                    strong_ratio,
                    avg_change,
                    avg_turnover,
                    top_industry,
                    top_two_share,
                    limit_up_like,
                    limit_down_like,
                    summary
                from breadth_df
                """
            )
            conn.execute(
                """
                insert into market_capital_flow (market, summary_json, updated_at)
                select market, summary_json, updated_at
                from capital_flow_df
                """
            )
            conn.execute(
                """
                insert into stock_lhb_stat (
                    market,
                    symbol,
                    name,
                    recent_list_date,
                    close_price,
                    change_pct,
                    on_list_count,
                    net_buy_amount,
                    buy_amount,
                    sell_amount,
                    total_amount,
                    institution_buy_count,
                    institution_sell_count,
                    institution_net_buy,
                    return_1m,
                    return_3m,
                    return_6m,
                    return_1y
                )
                select
                    market,
                    symbol,
                    name,
                    recent_list_date,
                    close_price,
                    change_pct,
                    on_list_count,
                    net_buy_amount,
                    buy_amount,
                    sell_amount,
                    total_amount,
                    institution_buy_count,
                    institution_sell_count,
                    institution_net_buy,
                    return_1m,
                    return_3m,
                    return_6m,
                    return_1y
                from lhb_df
                """
            )
            conn.execute(
                """
                insert into sync_metadata (market, source, updated_at)
                select market, source, updated_at
                from metadata_df
                """
            )

    def _ensure_move_analysis(
        self,
        records: list[dict[str, object]],
        history_df: pd.DataFrame,
    ) -> list[dict[str, object]]:
        history_map = {
            str(symbol): frame.reset_index(drop=True)
            for symbol, frame in history_df.groupby("symbol", sort=False)
        } if not history_df.empty else {}
        normalized: list[dict[str, object]] = []
        for record in records:
            current = dict(record)
            if not current.get("move_analysis"):
                symbol = str(current["symbol"])
                current["move_analysis"] = build_move_analysis(
                    latest_price=float(current.get("latest_price") or 0.0),
                    change_pct=float(current.get("change_pct") or 0.0),
                    turnover_ratio=float(current.get("turnover_ratio") or 0.0),
                    pe_ttm=float(current.get("pe_ttm") or 0.0),
                    market_cap=float(current.get("market_cap") or 0.0),
                    history_df=history_map.get(symbol, pd.DataFrame()),
                    fundamental=current.get("fundamental")
                    if isinstance(current.get("fundamental"), dict)
                    else None,
                )
            normalized.append(current)
        return normalized

    def _ensure_event_analysis(
        self,
        records: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for record in records:
            current = dict(record)
            if not current.get("event_analysis"):
                current["event_analysis"] = build_event_analysis()
            event_analysis = current.get("event_analysis")
            if isinstance(event_analysis, dict):
                current["tags"] = _merge_tags(
                    current.get("tags", []),
                    event_analysis.get("tags", []),
                )
            normalized.append(current)
        return normalized

    def _ensure_capital_flow_analysis(
        self,
        records: list[dict[str, object]],
        *,
        source: str,
        market: str,
    ) -> list[dict[str, object]]:
        normalized_market = normalize_market_scope(market)
        normalized: list[dict[str, object]] = []
        for record in records:
            current = dict(record)
            if not current.get("capital_flow_analysis") and normalized_market == "cn":
                if source == "sample":
                    current["capital_flow_analysis"] = build_sample_stock_capital_flow_analysis(current)
                else:
                    current["capital_flow_analysis"] = build_placeholder_stock_capital_flow_analysis(
                        symbol=str(current["symbol"])
                    )
            normalized.append(current)
        return normalized

    def _backfill_event_analysis(self) -> None:
        with self._connect() as conn:
            pending = conn.execute(
                """
                select symbol
                from stock_snapshot
                where event_analysis_json is null
                    or event_analysis_json = ''
                    or event_analysis_json = 'null'
                """
            ).fetchall()
            if not pending:
                return

            for (symbol,) in pending:
                conn.execute(
                    "update stock_snapshot set event_analysis_json = ? where symbol = ?",
                    [dumps_json(build_event_analysis()), str(symbol)],
                )

    def _backfill_move_analysis(self) -> None:
        with self._connect() as conn:
            pending = conn.execute(
                """
                select
                    symbol,
                    latest_price,
                    change_pct,
                    turnover_ratio,
                    pe_ttm,
                    market_cap,
                    fundamental_json
                from stock_snapshot
                where move_analysis_json is null
                    or move_analysis_json = ''
                    or move_analysis_json = 'null'
                """
            ).fetchdf()
            if pending.empty:
                return

            symbols = pending["symbol"].tolist()
            placeholders = ",".join(["?"] * len(symbols))
            history_df = conn.execute(
                f"""
                select symbol, date, open, close, low, high, volume, ma5, ma20
                from stock_price
                where symbol in ({placeholders})
                order by symbol, date
                """,
                symbols,
            ).fetchdf()

        history_map = {
            str(symbol): frame.reset_index(drop=True)
            for symbol, frame in history_df.groupby("symbol", sort=False)
        } if not history_df.empty else {}

        updates: list[tuple[str, str]] = []
        for row in pending.to_dict(orient="records"):
            move_analysis = build_move_analysis(
                latest_price=float(row.get("latest_price") or 0.0),
                change_pct=float(row.get("change_pct") or 0.0),
                turnover_ratio=float(row.get("turnover_ratio") or 0.0),
                pe_ttm=float(row.get("pe_ttm") or 0.0),
                market_cap=float(row.get("market_cap") or 0.0),
                history_df=history_map.get(str(row["symbol"]), pd.DataFrame()),
                fundamental=json.loads(row["fundamental_json"])
                if row.get("fundamental_json")
                else None,
            )
            updates.append((dumps_json(move_analysis), str(row["symbol"])))

        with self._connect() as conn:
            for move_analysis_json, symbol in updates:
                conn.execute(
                    "update stock_snapshot set move_analysis_json = ? where symbol = ?",
                    [move_analysis_json, symbol],
                )

    def _backfill_capital_flow_analysis(self) -> None:
        with self._connect() as conn:
            pending = conn.execute(
                """
                select
                    symbol,
                    market,
                    name,
                    latest_price,
                    change_pct,
                    turnover_ratio,
                    score,
                    capital_flow_json
                from stock_snapshot
                where capital_flow_json is null
                    or capital_flow_json = ''
                    or capital_flow_json = 'null'
                """
            ).fetchdf()
            if pending.empty:
                return

            for row in pending.to_dict(orient="records"):
                market = normalize_market_scope(str(row.get("market") or DEFAULT_MARKET_SCOPE))
                if market != "cn":
                    continue
                payload = build_sample_stock_capital_flow_analysis(
                    {
                        "symbol": row["symbol"],
                        "name": row["name"],
                        "latest_price": row["latest_price"],
                        "change_pct": row["change_pct"],
                        "turnover_ratio": row["turnover_ratio"],
                        "score": row["score"],
                    }
                )
                conn.execute(
                    "update stock_snapshot set capital_flow_json = ? where market = ? and symbol = ?",
                    [dumps_json(payload), market, str(row["symbol"])],
                )

    def list_stocks(
        self,
        market: str = DEFAULT_MARKET_SCOPE,
        keyword: str | None = None,
        board: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, object]:
        normalized_market = normalize_market_scope(market)
        conditions: list[str] = ["market = ?"]
        params: list[object] = [normalized_market]

        if keyword:
            conditions.append("(symbol like ? or name like ?)")
            like_keyword = f"%{keyword}%"
            params.extend([like_keyword, like_keyword])
        if board and board != "全部":
            conditions.append("board = ?")
            params.append(board)

        where_clause = ""
        if conditions:
            where_clause = f" where {' and '.join(conditions)}"

        offset = max(page - 1, 0) * page_size
        with self._connect() as conn:
            total = conn.execute(
                f"select count(*) from stock_snapshot{where_clause}",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                select
                    symbol,
                    name,
                    board,
                    industry,
                    latest_price,
                    change_pct,
                    turnover_ratio,
                    pe_ttm,
                    market_cap,
                    score,
                    thesis,
                    tags_json
                from stock_snapshot
                {where_clause}
                order by score desc, change_pct desc
                limit ? offset ?
                """,
                [*params, page_size, offset],
            ).fetchdf()

        result_rows = []
        for row in rows.to_dict(orient="records"):
            row["tags"] = json.loads(row.pop("tags_json"))
            result_rows.append(row)

        return {"total": int(total), "rows": result_rows}

    def get_stock_detail(self, symbol: str, market: str = DEFAULT_MARKET_SCOPE) -> dict[str, object]:
        normalized_market = normalize_market_scope(market)
        with self._connect() as conn:
            row = conn.execute(
                """
                select
                    symbol,
                    name,
                    board,
                    industry,
                    latest_price,
                    change_pct,
                    turnover_ratio,
                    pe_ttm,
                    market_cap,
                    score,
                    thesis,
                    tags_json,
                    thesis_points_json,
                    risk_notes_json,
                    signal_breakdown_json,
                    fundamental_json,
                    move_analysis_json,
                    event_analysis_json,
                    capital_flow_json
                from stock_snapshot
                where market = ?
                    and symbol = ?
                """,
                [normalized_market, symbol],
            ).fetchone()
            if row is None:
                raise KeyError(symbol)

            columns = [
                "symbol",
                "name",
                "board",
                "industry",
                "latest_price",
                "change_pct",
                "turnover_ratio",
                "pe_ttm",
                "market_cap",
                "score",
                "thesis",
                "tags_json",
                "thesis_points_json",
                "risk_notes_json",
                "signal_breakdown_json",
                "fundamental_json",
                "move_analysis_json",
                "event_analysis_json",
                "capital_flow_json",
            ]
            detail = dict(zip(columns, row, strict=True))
            prices = conn.execute(
                """
                select date, open, close, low, high, volume, ma5, ma20
                from stock_price
                where market = ?
                    and symbol = ?
                order by date
                """,
                [normalized_market, symbol],
            ).fetchdf()

        detail["tags"] = json.loads(detail.pop("tags_json"))
        detail["thesis_points"] = json.loads(detail.pop("thesis_points_json"))
        detail["risk_notes"] = json.loads(detail.pop("risk_notes_json"))
        detail["signal_breakdown"] = json.loads(detail.pop("signal_breakdown_json"))
        detail["fundamental"] = json.loads(detail.pop("fundamental_json")) if detail.get("fundamental_json") else None
        detail["move_analysis"] = (
            json.loads(detail.pop("move_analysis_json")) if detail.get("move_analysis_json") else None
        )
        detail["event_analysis"] = (
            json.loads(detail.pop("event_analysis_json")) if detail.get("event_analysis_json") else None
        )
        detail["capital_flow_analysis"] = (
            json.loads(detail.pop("capital_flow_json")) if detail.get("capital_flow_json") else None
        )
        if normalize_market_scope(market) == "cn":
            detail["capital_flow_analysis"] = self._resolve_capital_flow_analysis(
                symbol=str(detail["symbol"]),
                cached_payload=detail.get("capital_flow_analysis"),
            )
        detail["price_series"] = prices.to_dict(orient="records")
        return detail

    def _resolve_capital_flow_analysis(
        self,
        *,
        symbol: str,
        cached_payload: dict[str, object] | None,
    ) -> dict[str, object]:
        if isinstance(cached_payload, dict) and cached_payload.get("status") == "ready":
            return cached_payload

        lhb_row = self._lookup_lhb_row(symbol)
        try:
            import akshare as ak

            payload = collect_cn_stock_capital_flow_analysis(ak=ak, symbol=symbol, lhb_row=lhb_row)
        except Exception:
            payload = None

        if isinstance(payload, dict) and payload.get("status") == "ready":
            with self._connect() as conn:
                conn.execute(
                    "update stock_snapshot set capital_flow_json = ? where market = ? and symbol = ?",
                    [dumps_json(payload), "cn", symbol],
                )
            return payload

        if isinstance(cached_payload, dict):
            return cached_payload
        return build_placeholder_stock_capital_flow_analysis(symbol=symbol, lhb_row=lhb_row)

    def _lookup_lhb_row(self, symbol: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select
                    symbol,
                    name,
                    recent_list_date,
                    close_price,
                    change_pct,
                    on_list_count,
                    net_buy_amount,
                    buy_amount,
                    sell_amount,
                    total_amount,
                    institution_buy_count,
                    institution_sell_count,
                    institution_net_buy,
                    return_1m,
                    return_3m,
                    return_6m,
                    return_1y
                from stock_lhb_stat
                where market = 'cn'
                    and symbol = ?
                limit 1
                """,
                [symbol],
            ).fetchone()
        if row is None:
            return None
        columns = [
            "symbol",
            "name",
            "recent_list_date",
            "close_price",
            "change_pct",
            "on_list_count",
            "net_buy_amount",
            "buy_amount",
            "sell_amount",
            "total_amount",
            "institution_buy_count",
            "institution_sell_count",
            "institution_net_buy",
            "return_1m",
            "return_3m",
            "return_6m",
            "return_1y",
        ]
        return dict(zip(columns, row, strict=True))

    def get_recommendations(self, market: str = DEFAULT_MARKET_SCOPE) -> list[dict[str, object]]:
        normalized_market = normalize_market_scope(market)
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    recommendation_item.symbol,
                    recommendation_item.name,
                    recommendation_item.score,
                    recommendation_item.entry_window,
                    recommendation_item.expected_holding_days,
                    recommendation_item.thesis,
                    recommendation_item.risk,
                    recommendation_item.tags_json,
                    stock_snapshot.move_analysis_json,
                    stock_snapshot.event_analysis_json
                from recommendation_item
                left join stock_snapshot
                    on recommendation_item.market = stock_snapshot.market
                    and recommendation_item.symbol = stock_snapshot.symbol
                where recommendation_item.market = ?
                order by recommendation_item.score desc
                """
                ,
                [normalized_market],
            ).fetchdf()
            symbols = rows["symbol"].tolist() if not rows.empty else []
            performance = self._build_performance_map(conn, symbols)

        recommendations = []
        for row in rows.to_dict(orient="records"):
            row["tags"] = json.loads(row.pop("tags_json"))
            move_analysis = json.loads(row.pop("move_analysis_json")) if row.get("move_analysis_json") else None
            event_analysis = json.loads(row.pop("event_analysis_json")) if row.get("event_analysis_json") else None
            metrics = performance.get(str(row["symbol"]), {})
            row["latest_price"] = metrics.get("latest_price")
            row["recent_return_5d"] = metrics.get("recent_return_5d")
            row["recent_return_20d"] = metrics.get("recent_return_20d")
            row["move_bias"] = move_analysis.get("bias") if move_analysis else None
            row["move_summary"] = move_analysis.get("summary") if move_analysis else None
            row["event_tone"] = event_analysis.get("tone") if event_analysis else None
            row["event_summary"] = event_analysis.get("summary") if event_analysis else None
            recommendations.append(row)
        return recommendations

    def get_recommendation_context(
        self,
        symbol: str,
        market: str = DEFAULT_MARKET_SCOPE,
        recommendation_limit: int = 8,
    ) -> dict[str, object]:
        normalized_market = normalize_market_scope(market)
        with self._connect() as conn:
            ranked = conn.execute(
                """
                select
                    symbol,
                    name,
                    score,
                    change_pct,
                    row_number() over (
                        order by score desc, change_pct desc, symbol asc
                    ) as rank
                from stock_snapshot
                where market = ?
                order by rank
                """
                ,
                [normalized_market],
            ).fetchdf()

        if ranked.empty:
            return {
                "current_rank": 0,
                "total_candidates": 0,
                "recommendation_limit": recommendation_limit,
                "cutoff_symbol": None,
                "cutoff_name": None,
                "cutoff_score": None,
            }

        total_candidates = int(ranked.shape[0])
        effective_limit = min(max(recommendation_limit, 1), total_candidates)
        target_rows = ranked.loc[ranked["symbol"] == symbol]
        if target_rows.empty:
            return {
                "current_rank": 0,
                "total_candidates": total_candidates,
                "recommendation_limit": effective_limit,
                "cutoff_symbol": None,
                "cutoff_name": None,
                "cutoff_score": None,
            }

        target_row = target_rows.iloc[0]
        cutoff_row = ranked.iloc[effective_limit - 1]
        return {
            "current_rank": int(target_row["rank"]),
            "total_candidates": total_candidates,
            "recommendation_limit": effective_limit,
            "cutoff_symbol": str(cutoff_row["symbol"]),
            "cutoff_name": str(cutoff_row["name"]),
            "cutoff_score": int(cutoff_row["score"]),
        }

    def get_latest_snapshot_map(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        placeholders = ",".join(["?"] * len(symbols))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select symbol, latest_price
                from stock_snapshot
                where symbol in ({placeholders})
                """,
                symbols,
            ).fetchall()
        return {str(symbol): float(price) for symbol, price in rows}

    def get_snapshot_briefs(self, symbols: list[str]) -> dict[str, dict[str, object]]:
        if not symbols:
            return {}
        placeholders = ",".join(["?"] * len(symbols))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select
                    symbol,
                    name,
                    board,
                    industry,
                    latest_price,
                    change_pct,
                    score,
                    thesis,
                    tags_json
                from stock_snapshot
                where symbol in ({placeholders})
                """,
                symbols,
            ).fetchdf()

        brief_map: dict[str, dict[str, object]] = {}
        for row in rows.to_dict(orient="records"):
            row["tags"] = json.loads(row.pop("tags_json"))
            brief_map[str(row["symbol"])] = row
        return brief_map

    def _build_performance_map(
        self,
        conn: duckdb.DuckDBPyConnection,
        symbols: list[str],
    ) -> dict[str, dict[str, float | None]]:
        if not symbols:
            return {}
        placeholders = ",".join(["?"] * len(symbols))
        frame = conn.execute(
            f"""
            select symbol, date, close
            from stock_price
            where symbol in ({placeholders})
            order by symbol, date
            """,
            symbols,
        ).fetchdf()
        performance: dict[str, dict[str, float | None]] = {}
        for symbol, group in frame.groupby("symbol"):
            closes = group["close"].tolist()
            latest = float(closes[-1]) if closes else None
            performance[str(symbol)] = {
                "latest_price": latest,
                "recent_return_5d": _close_return(closes, 5),
                "recent_return_20d": _close_return(closes, 20),
            }
        return performance

    def get_dashboard_summary(self, market: str = DEFAULT_MARKET_SCOPE) -> dict[str, object]:
        normalized_market = normalize_market_scope(market)
        with self._connect() as conn:
            snapshot_df = conn.execute(
                """
                select score, change_pct, turnover_ratio, market_cap, industry
                from stock_snapshot
                where market = ?
                """
                ,
                [normalized_market],
            ).fetchdf()
            pulse_rows = conn.execute(
                "select date, score, turnover from market_pulse where market = ? order by date",
                [normalized_market],
            ).fetchdf()
            heat_rows = conn.execute(
                "select industry, score, momentum from industry_heat where market = ? order by score desc",
                [normalized_market],
            ).fetchdf()
            benchmark_rows = conn.execute(
                """
                select code, name, latest_price, change_pct, return_20d, trend, takeaway
                from market_benchmark
                where market = ?
                order by code
                """,
                [normalized_market],
            ).fetchdf()
            breadth_row = conn.execute(
                """
                select
                    scope_label,
                    total_count,
                    advancers,
                    decliners,
                    advance_ratio,
                    strong_count,
                    strong_ratio,
                    avg_change,
                    avg_turnover,
                    top_industry,
                    top_two_share,
                    limit_up_like,
                    limit_down_like,
                    summary
                from market_breadth
                where market = ?
                limit 1
                """,
                [normalized_market],
            ).fetchone()
            capital_flow_row = conn.execute(
                """
                select summary_json
                from market_capital_flow
                where market = ?
                limit 1
                """,
                [normalized_market],
            ).fetchone()
            metadata = conn.execute(
                "select source, updated_at from sync_metadata where market = ? limit 1",
                [normalized_market],
            ).fetchone()

        breadth_snapshot = _serialize_breadth_row(breadth_row) or build_market_breadth_from_records(
            snapshot_df.to_dict(orient="records"),
            normalized_market,
        )
        if benchmark_rows.empty:
            if metadata and str(metadata[0]).startswith("sample"):
                benchmark_rows = pd.DataFrame(
                    build_sample_benchmark_records(snapshot_df.to_dict(orient="records"), normalized_market)
                )
            elif normalized_market == "cn":
                try:
                    import akshare as ak

                    benchmark_rows = pd.DataFrame(collect_market_benchmark_records(ak=ak, market=normalized_market))
                except Exception:
                    benchmark_rows = pd.DataFrame()
        market_capital_flow = _load_json(capital_flow_row[0]) if capital_flow_row else None
        if market_capital_flow is None:
            if metadata and str(metadata[0]).startswith("sample") or normalized_market == "cn":
                market_capital_flow = build_sample_market_capital_flow_overview(
                    snapshot_df.to_dict(orient="records"),
                    normalized_market,
                )
            else:
                market_capital_flow = build_placeholder_market_capital_flow_overview(normalized_market)
        avg_score = round(float(snapshot_df["score"].mean()))
        advancers = int((snapshot_df["change_pct"] > 0).sum())
        losers = int((snapshot_df["change_pct"] <= 0).sum())
        avg_turnover = round(float(snapshot_df["turnover_ratio"].mean()), 2)
        total_market_cap = round(float(snapshot_df["market_cap"].sum()), 0)
        top_industry = str(heat_rows.iloc[0]["industry"]) if not heat_rows.empty else "多板块"
        market_context = build_market_context(
            snapshot_df=snapshot_df,
            pulse_rows=pulse_rows,
            heat_rows=heat_rows,
            market=normalized_market,
            breadth_snapshot=breadth_snapshot,
        )

        headline = str(market_context["summary"]) if market_context else f"{top_industry} 维持高热度，系统当前偏向顺势筛选。"
        updated_at = str(metadata[1]) if metadata else datetime.now().isoformat(timespec="seconds")

        return {
            "headline": headline,
            "updated_at": updated_at.replace("T", " "),
            "market_context": market_context,
            "benchmark_indices": benchmark_rows.to_dict(orient="records"),
            "breadth_snapshot": breadth_snapshot,
            "market_capital_flow": market_capital_flow,
            "market_overview": [
                {
                    "label": "股票池规模",
                    "value": f"{len(snapshot_df)} 只",
                    "change": f"+{advancers - losers}",
                    "tone": "positive" if advancers >= losers else "negative",
                    "description": "当前纳入样本池的股票数量，可继续叠加自选池或行业约束。",
                },
                {
                    "label": "平均综合评分",
                    "value": f"{avg_score} 分",
                    "change": "四维加权",
                    "tone": "neutral",
                    "description": "综合技术、基本面、资金和情绪后的整体温度。",
                },
                {
                    "label": "上涨家数",
                    "value": f"{advancers} 只",
                    "change": f"下跌 {losers} 只",
                    "tone": "positive" if advancers > losers else "negative",
                    "description": "用来快速判断当天样本池里是扩散上涨还是分化行情。",
                },
                {
                    "label": "平均换手率",
                    "value": f"{avg_turnover:.2f}%",
                    "change": f"总市值 {total_market_cap:.0f} 亿",
                    "tone": "neutral",
                    "description": "适合观察样本池整体活跃度，后面可以再叠加成交额过滤。",
                },
            ],
            "hot_industries": heat_rows.to_dict(orient="records"),
            "market_pulse": pulse_rows.to_dict(orient="records"),
            "top_recommendations": self.get_recommendations(normalized_market)[:6],
            "risk_flags": [
                str(market_context["action_hint"]),
                *(list(market_context.get("watch_points", []))[:2] if isinstance(market_context, dict) else []),
                "高分只表示相对更值得复核，不代表没有回撤风险。",
            ],
        }

    def current_source(self, market: str = DEFAULT_MARKET_SCOPE) -> str:
        normalized_market = normalize_market_scope(market)
        with self._connect() as conn:
            row = conn.execute(
                "select source from sync_metadata where market = ? limit 1",
                [normalized_market],
            ).fetchone()
        return str(row[0]) if row else "sample"

    def get_event_sync_overview(self, market: str = DEFAULT_MARKET_SCOPE) -> dict[str, object]:
        normalized_market = normalize_market_scope(market)
        configured_sources = _configured_event_sources(normalized_market)
        with self._connect() as conn:
            snapshot_rows = conn.execute(
                """
                select symbol, event_analysis_json
                from stock_snapshot
                where market = ?
                """
                ,
                [normalized_market],
            ).fetchall()
            metadata = conn.execute(
                "select updated_at from sync_metadata where market = ? limit 1",
                [normalized_market],
            ).fetchone()

        total_symbols = len(snapshot_rows)
        updated_at = str(metadata[0]).replace("T", " ") if metadata and metadata[0] else None
        if total_symbols == 0:
            return {
                "status": "idle",
                "summary": "当前还没有样本股票，下一次市场同步后才会生成事件层状态。",
                "configured_sources": configured_sources,
                "detected_sources": [],
                "coverage_count": 0,
                "total_symbols": 0,
                "active_symbols": 0,
                "total_items": 0,
                "updated_at": updated_at,
            }

        coverage_count = 0
        active_symbols = 0
        total_items = 0
        detected_sources: set[str] = set()
        for _, raw_payload in snapshot_rows:
            payload = _load_json(raw_payload)
            if not payload:
                continue
            coverage_count += 1
            items = payload.get("items", [])
            if isinstance(items, list):
                total_items += len(items)
                for item in items:
                    if isinstance(item, dict):
                        source = _normalize_event_source(item.get("source"))
                        if source:
                            detected_sources.add(source)
            tone = str(payload.get("tone") or "neutral")
            if tone != "neutral" or (isinstance(items, list) and items):
                active_symbols += 1

        if coverage_count == 0:
            status = "idle"
            summary = "事件层还没有写入到当前股票池，建议先执行一次市场同步。"
        elif coverage_count < total_symbols:
            status = "partial"
            summary = f"事件层已覆盖 {coverage_count}/{total_symbols} 只股票，当前还是部分写入状态。"
        elif active_symbols == 0:
            status = "placeholder"
            summary = "事件层结构已经接通，但当前库里还没有捕捉到明确催化，页面会先显示中性占位。"
        else:
            status = "ready"
            summary = (
                f"事件层已覆盖全部 {total_symbols} 只股票，当前抓到了 {active_symbols} 只带明确催化的标的，"
                f"共 {total_items} 条结构化事件。"
            )

        return {
            "status": status,
            "summary": summary,
            "configured_sources": configured_sources,
            "detected_sources": sorted(detected_sources),
            "coverage_count": coverage_count,
            "total_symbols": total_symbols,
            "active_symbols": active_symbols,
            "total_items": total_items,
            "updated_at": updated_at,
        }

    def _connect(self) -> duckdb.DuckDBPyConnection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(self.db_path)

    @staticmethod
    def _ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            create table if not exists stock_snapshot (
                market varchar,
                symbol varchar,
                name varchar,
                board varchar,
                industry varchar,
                latest_price double,
                change_pct double,
                turnover_ratio double,
                pe_ttm double,
                market_cap double,
                score integer,
                thesis varchar,
                risk varchar,
                entry_window varchar,
                expected_holding_days integer,
                updated_at varchar,
                tags_json varchar,
                thesis_points_json varchar,
                risk_notes_json varchar,
                signal_breakdown_json varchar,
                fundamental_json varchar,
                move_analysis_json varchar,
                event_analysis_json varchar,
                capital_flow_json varchar
            )
            """
        )
        conn.execute("alter table stock_snapshot add column if not exists market varchar")
        conn.execute("alter table stock_snapshot add column if not exists fundamental_json varchar")
        conn.execute("alter table stock_snapshot add column if not exists move_analysis_json varchar")
        conn.execute("alter table stock_snapshot add column if not exists event_analysis_json varchar")
        conn.execute("alter table stock_snapshot add column if not exists capital_flow_json varchar")
        conn.execute("update stock_snapshot set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists stock_price (
                market varchar,
                symbol varchar,
                date varchar,
                open double,
                close double,
                low double,
                high double,
                volume double,
                ma5 double,
                ma20 double
            )
            """
        )
        conn.execute("alter table stock_price add column if not exists market varchar")
        conn.execute("update stock_price set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists industry_heat (
                market varchar,
                industry varchar,
                score integer,
                momentum varchar
            )
            """
        )
        conn.execute("alter table industry_heat add column if not exists market varchar")
        conn.execute("update industry_heat set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists market_pulse (
                market varchar,
                date varchar,
                score integer,
                turnover double
            )
            """
        )
        conn.execute("alter table market_pulse add column if not exists market varchar")
        conn.execute("update market_pulse set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists recommendation_item (
                market varchar,
                symbol varchar,
                name varchar,
                score integer,
                entry_window varchar,
                expected_holding_days integer,
                thesis varchar,
                risk varchar,
                updated_at varchar,
                tags_json varchar
            )
            """
        )
        conn.execute("alter table recommendation_item add column if not exists market varchar")
        conn.execute("update recommendation_item set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists market_benchmark (
                market varchar,
                code varchar,
                name varchar,
                latest_price double,
                change_pct double,
                return_20d double,
                trend varchar,
                takeaway varchar
            )
            """
        )
        conn.execute("alter table market_benchmark add column if not exists market varchar")
        conn.execute("update market_benchmark set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists market_breadth (
                market varchar,
                scope_label varchar,
                total_count integer,
                advancers integer,
                decliners integer,
                advance_ratio double,
                strong_count integer,
                strong_ratio double,
                avg_change double,
                avg_turnover double,
                top_industry varchar,
                top_two_share double,
                limit_up_like integer,
                limit_down_like integer,
                summary varchar
            )
            """
        )
        conn.execute("alter table market_breadth add column if not exists market varchar")
        conn.execute("update market_breadth set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists market_capital_flow (
                market varchar,
                summary_json varchar,
                updated_at varchar
            )
            """
        )
        conn.execute("alter table market_capital_flow add column if not exists market varchar")
        conn.execute("update market_capital_flow set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists stock_lhb_stat (
                market varchar,
                symbol varchar,
                name varchar,
                recent_list_date varchar,
                close_price double,
                change_pct double,
                on_list_count integer,
                net_buy_amount double,
                buy_amount double,
                sell_amount double,
                total_amount double,
                institution_buy_count integer,
                institution_sell_count integer,
                institution_net_buy double,
                return_1m double,
                return_3m double,
                return_6m double,
                return_1y double
            )
            """
        )
        conn.execute("alter table stock_lhb_stat add column if not exists market varchar")
        conn.execute("update stock_lhb_stat set market = 'cn' where market is null or market = ''")
        conn.execute(
            """
            create table if not exists sync_metadata (
                market varchar,
                source varchar,
                updated_at varchar
            )
            """
        )
        conn.execute("alter table sync_metadata add column if not exists market varchar")
        conn.execute("update sync_metadata set market = 'cn' where market is null or market = ''")


def _close_return(closes: list[float], lookback_days: int) -> float | None:
    if len(closes) <= lookback_days:
        return None
    base = float(closes[-(lookback_days + 1)])
    latest = float(closes[-1])
    if base == 0:
        return None
    return round((latest / base - 1) * 100, 2)


def _load_json(raw_payload: object) -> dict[str, object] | None:
    if raw_payload in (None, "", "null"):
        return None
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_event_source(raw_source: object) -> str:
    source = str(raw_source or "").strip()
    mapping = {
        "eastmoney-yjyg": "业绩预告",
        "eastmoney-notice": "公告",
    }
    return mapping.get(source, source)


def _configured_event_sources(market: str) -> list[str]:
    return ["公告", "业绩预告"]


def _serialize_breadth_row(row: object) -> dict[str, object] | None:
    if row is None:
        return None
    columns = [
        "scope_label",
        "total_count",
        "advancers",
        "decliners",
        "advance_ratio",
        "strong_count",
        "strong_ratio",
        "avg_change",
        "avg_turnover",
        "top_industry",
        "top_two_share",
        "limit_up_like",
        "limit_down_like",
        "summary",
    ]
    payload = dict(zip(columns, row, strict=True))
    return payload


def _merge_tags(base_tags: object, extra_tags: object) -> list[str]:
    result: list[str] = []
    for source in (base_tags, extra_tags):
        if not isinstance(source, list):
            continue
        for tag in source:
            text = str(tag).strip()
            if text and text not in result:
                result.append(text)
    return result
