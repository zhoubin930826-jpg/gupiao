from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from app.services.sample_market import (
    build_demo_snapshot_records,
    build_history_records,
    build_industry_heat_records,
    build_market_pulse_records,
    build_recommendation_records,
    dumps_json,
)


class MarketDataStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def initialize(self) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            count = conn.execute("select count(*) from stock_snapshot").fetchone()[0]
            source_row = conn.execute("select source from sync_metadata limit 1").fetchone()
            source = str(source_row[0]) if source_row else "sample"
        if count == 0:
            self.seed_demo_dataset()
            return
        if source == "sample":
            self.seed_demo_dataset()
            return

    def seed_demo_dataset(self) -> None:
        self.refresh_snapshot_records(build_demo_snapshot_records(), source="sample")

    def refresh_snapshot_records(
        self,
        records: list[dict[str, object]],
        source: str,
        history_rows: list[dict[str, object]] | None = None,
    ) -> None:
        history_rows = history_rows or build_history_records(records)
        industry_rows = build_industry_heat_records(records)
        pulse_rows = build_market_pulse_records(records)
        recommendation_rows = build_recommendation_records(records)
        updated_at = datetime.now().isoformat(timespec="seconds")

        snapshot_df = pd.DataFrame(
            [
                {
                    **record,
                    "tags_json": dumps_json(record["tags"]),
                    "thesis_points_json": dumps_json(record["thesis_points"]),
                    "risk_notes_json": dumps_json(record["risk_notes"]),
                    "signal_breakdown_json": dumps_json(record["signal_breakdown"]),
                    "fundamental_json": dumps_json(record.get("fundamental")),
                    "updated_at": updated_at,
                }
                for record in records
            ]
        )
        snapshot_df = snapshot_df.drop(
            columns=["tags", "thesis_points", "risk_notes", "signal_breakdown", "fundamental"],
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
                "updated_at",
                "tags_json",
                "thesis_points_json",
                "risk_notes_json",
                "signal_breakdown_json",
                "fundamental_json",
            ]
        ]
        history_df = pd.DataFrame(history_rows)
        if not history_df.empty and "amount" in history_df.columns:
            history_df = history_df.drop(columns=["amount"])
        industry_df = pd.DataFrame(industry_rows)
        pulse_df = pd.DataFrame(pulse_rows)
        recommendation_df = pd.DataFrame(
            [
                {
                    **row,
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
                "thesis",
                "risk",
                "updated_at",
                "tags_json",
            ]
        ]
        metadata_df = pd.DataFrame([{"source": source, "updated_at": updated_at}])

        with self._connect() as conn:
            self._ensure_schema(conn)
            for table_name in (
                "stock_snapshot",
                "stock_price",
                "industry_heat",
                "market_pulse",
                "recommendation_item",
                "sync_metadata",
            ):
                conn.execute(f"delete from {table_name}")

            conn.register("snapshot_df", snapshot_df)
            conn.register("history_df", history_df)
            conn.register("industry_df", industry_df)
            conn.register("pulse_df", pulse_df)
            conn.register("recommendation_df", recommendation_df)
            conn.register("metadata_df", metadata_df)

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
                    updated_at,
                    tags_json,
                    thesis_points_json,
                    risk_notes_json,
                    signal_breakdown_json,
                    fundamental_json
                )
                select * from snapshot_df
                """
            )
            conn.execute("insert into stock_price select * from history_df")
            conn.execute("insert into industry_heat select * from industry_df")
            conn.execute("insert into market_pulse select * from pulse_df")
            conn.execute(
                """
                insert into recommendation_item (
                    symbol,
                    name,
                    score,
                    entry_window,
                    expected_holding_days,
                    thesis,
                    risk,
                    updated_at,
                    tags_json
                )
                select * from recommendation_df
                """
            )
            conn.execute("insert into sync_metadata select * from metadata_df")

    def list_stocks(
        self,
        keyword: str | None = None,
        board: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, object]:
        conditions: list[str] = []
        params: list[object] = []

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

    def get_stock_detail(self, symbol: str) -> dict[str, object]:
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
                    fundamental_json
                from stock_snapshot
                where symbol = ?
                """,
                [symbol],
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
            ]
            detail = dict(zip(columns, row, strict=True))
            prices = conn.execute(
                """
                select date, open, close, low, high, volume, ma5, ma20
                from stock_price
                where symbol = ?
                order by date
                """,
                [symbol],
            ).fetchdf()

        detail["tags"] = json.loads(detail.pop("tags_json"))
        detail["thesis_points"] = json.loads(detail.pop("thesis_points_json"))
        detail["risk_notes"] = json.loads(detail.pop("risk_notes_json"))
        detail["signal_breakdown"] = json.loads(detail.pop("signal_breakdown_json"))
        detail["fundamental"] = json.loads(detail.pop("fundamental_json")) if detail.get("fundamental_json") else None
        detail["price_series"] = prices.to_dict(orient="records")
        return detail

    def get_recommendations(self) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    symbol,
                    name,
                    score,
                    entry_window,
                    expected_holding_days,
                    thesis,
                    risk,
                    tags_json
                from recommendation_item
                order by score desc
                """
            ).fetchdf()
            symbols = rows["symbol"].tolist() if not rows.empty else []
            performance = self._build_performance_map(conn, symbols)

        recommendations = []
        for row in rows.to_dict(orient="records"):
            row["tags"] = json.loads(row.pop("tags_json"))
            metrics = performance.get(str(row["symbol"]), {})
            row["latest_price"] = metrics.get("latest_price")
            row["recent_return_5d"] = metrics.get("recent_return_5d")
            row["recent_return_20d"] = metrics.get("recent_return_20d")
            recommendations.append(row)
        return recommendations

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

    def get_dashboard_summary(self) -> dict[str, object]:
        with self._connect() as conn:
            snapshot_df = conn.execute(
                """
                select score, change_pct, turnover_ratio, market_cap, industry
                from stock_snapshot
                """
            ).fetchdf()
            pulse_rows = conn.execute(
                "select date, score, turnover from market_pulse order by date"
            ).fetchdf()
            heat_rows = conn.execute(
                "select industry, score, momentum from industry_heat order by score desc"
            ).fetchdf()
            metadata = conn.execute(
                "select source, updated_at from sync_metadata limit 1"
            ).fetchone()

        avg_score = round(float(snapshot_df["score"].mean()))
        advancers = int((snapshot_df["change_pct"] > 0).sum())
        losers = int((snapshot_df["change_pct"] <= 0).sum())
        avg_turnover = round(float(snapshot_df["turnover_ratio"].mean()), 2)
        total_market_cap = round(float(snapshot_df["market_cap"].sum()), 0)
        top_industry = str(heat_rows.iloc[0]["industry"]) if not heat_rows.empty else "多板块"

        headline = f"{top_industry} 维持高热度，系统当前偏向顺势筛选。"
        updated_at = str(metadata[1]) if metadata else datetime.now().isoformat(timespec="seconds")

        return {
            "headline": headline,
            "updated_at": updated_at.replace("T", " "),
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
            "top_recommendations": self.get_recommendations()[:6],
            "risk_flags": [
                "当前结果默认是研究候选池，不直接替代交易决策。",
                "若切换成 AKShare 快照模式，建议补历史和财务数据后再下结论。",
                "高分只表示相对更值得复核，不代表没有回撤风险。",
            ],
        }

    def current_source(self) -> str:
        with self._connect() as conn:
            row = conn.execute("select source from sync_metadata limit 1").fetchone()
        return str(row[0]) if row else "sample"

    def _connect(self) -> duckdb.DuckDBPyConnection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(self.db_path)

    @staticmethod
    def _ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            create table if not exists stock_snapshot (
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
                fundamental_json varchar
            )
            """
        )
        conn.execute("alter table stock_snapshot add column if not exists fundamental_json varchar")
        conn.execute(
            """
            create table if not exists stock_price (
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
        conn.execute(
            """
            create table if not exists industry_heat (
                industry varchar,
                score integer,
                momentum varchar
            )
            """
        )
        conn.execute(
            """
            create table if not exists market_pulse (
                date varchar,
                score integer,
                turnover double
            )
            """
        )
        conn.execute(
            """
            create table if not exists recommendation_item (
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
        conn.execute(
            """
            create table if not exists sync_metadata (
                source varchar,
                updated_at varchar
            )
            """
        )


def _close_return(closes: list[float], lookback_days: int) -> float | None:
    if len(closes) <= lookback_days:
        return None
    base = float(closes[-(lookback_days + 1)])
    latest = float(closes[-1])
    if base == 0:
        return None
    return round((latest / base - 1) * 100, 2)
