from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.market_scope import is_a_share_symbol
from app.models.recommendation import RecommendationJournal
from app.services.market_store import MarketDataStore
from app.services.recommendation_tracking_service import (
    build_price_map,
    locate_start_index,
    matured_for_window,
)
from app.services.recommendation_trust_service import data_mode_from_source

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
        journal_rows = [row for row in journal_rows if is_a_share_symbol(row.symbol)]
        mode_breakdown = cls._build_mode_breakdown(journal_rows)
        if not journal_rows:
            return {
                "total_samples": 0,
                "evaluation_mode": "demo",
                "evaluation_notice": "当前还没有可用于复盘的样本，后续积累真实推荐后会自动切换到真实样本统计。",
                "trust_level": "low",
                "trust_reasons": [
                    "当前还没有真实样本，复盘结果暂时不能当成策略优势证明。",
                    "请先继续积累真实推荐样本，并观察 20 日窗口成熟数量。",
                ],
                "mode_breakdown": mode_breakdown,
                "maturity_breakdown": [
                    {
                        "window_days": window,
                        "total_samples": 0,
                        "matured_samples": 0,
                        "immature_samples": 0,
                    }
                    for window in WINDOWS
                ],
                "window_metrics": [],
                "recent_runs": [],
                "top_hits": [],
                "top_misses": [],
                "samples": [],
            }

        evaluation_mode = (
            "live" if any(data_mode_from_source(row.source) == "live" for row in journal_rows) else "demo"
        )
        evaluation_rows = [
            row for row in journal_rows if data_mode_from_source(row.source) == evaluation_mode
        ][:limit]

        symbols = sorted({row.symbol for row in evaluation_rows})
        price_map = cls._build_price_map(market_store, symbols)
        sample_rows = [cls._serialize_row(row, price_map.get(row.symbol, [])) for row in evaluation_rows]
        maturity_breakdown = [
            cls._build_maturity_metric(evaluation_rows, price_map, window)
            for window in WINDOWS
        ]

        sortable = [row for row in sample_rows if row.get("expected_return") is not None]
        top_hits = sorted(sortable, key=lambda item: float(item["expected_return"]), reverse=True)[:5]
        top_misses = sorted(sortable, key=lambda item: float(item["expected_return"]))[:5]

        return {
            "total_samples": len(sample_rows),
            "evaluation_mode": evaluation_mode,
            "evaluation_notice": cls._evaluation_notice(evaluation_mode, mode_breakdown),
            "trust_level": cls._trust_level(evaluation_mode, maturity_breakdown),
            "trust_reasons": cls._trust_reasons(evaluation_mode, mode_breakdown, maturity_breakdown),
            "mode_breakdown": mode_breakdown,
            "maturity_breakdown": maturity_breakdown,
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
        return build_price_map(market_store, symbols)

    @classmethod
    def _serialize_row(
        cls,
        row: RecommendationJournal,
        price_rows: list[tuple[str, float]],
    ) -> dict[str, object]:
        publish_date = row.generated_at.date()
        start_index = locate_start_index(price_rows, publish_date)
        latest_known_price = price_rows[-1][1] if price_rows else None

        payload = {
            "run_key": row.run_key,
            "generated_at": row.generated_at.isoformat(timespec="seconds"),
            "symbol": row.symbol,
            "name": row.name,
            "score": row.score,
            "source": row.source,
            "data_mode": data_mode_from_source(row.source),
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
            buckets[str(row["run_key"])] .append(row)

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

    @staticmethod
    def _build_mode_breakdown(rows: list[RecommendationJournal]) -> list[dict[str, object]]:
        counts = {"live": 0, "demo": 0}
        for row in rows:
            counts[data_mode_from_source(row.source)] += 1
        return [
            {"mode": "live", "sample_size": counts["live"]},
            {"mode": "demo", "sample_size": counts["demo"]},
        ]

    @staticmethod
    def _build_maturity_metric(
        rows: list[RecommendationJournal],
        price_map: dict[str, list[tuple[str, float]]],
        window: int,
    ) -> dict[str, object]:
        total_samples = len(rows)
        matured_samples = sum(
            1
            for row in rows
            if matured_for_window(price_map.get(row.symbol, []), _publish_date(row.generated_at), window)
        )
        return {
            "window_days": window,
            "total_samples": total_samples,
            "matured_samples": matured_samples,
            "immature_samples": total_samples - matured_samples,
        }

    @staticmethod
    def _trust_level(
        evaluation_mode: str,
        maturity_breakdown: list[dict[str, object]],
    ) -> str:
        maturity_20 = next(
            (item for item in maturity_breakdown if int(item["window_days"]) == 20),
            {"matured_samples": 0},
        )
        matured_20 = int(maturity_20["matured_samples"])
        if evaluation_mode == "live" and matured_20 >= 16:
            return "high"
        if evaluation_mode == "live" and matured_20 >= 6:
            return "medium"
        return "low"

    @staticmethod
    def _trust_reasons(
        evaluation_mode: str,
        mode_breakdown: list[dict[str, object]],
        maturity_breakdown: list[dict[str, object]],
    ) -> list[str]:
        counts = {str(item["mode"]): int(item["sample_size"]) for item in mode_breakdown}
        maturity_20 = next(
            (item for item in maturity_breakdown if int(item["window_days"]) == 20),
            {"matured_samples": 0, "immature_samples": 0},
        )
        reasons: list[str] = []
        if evaluation_mode == "live":
            reasons.append(
                f"当前复盘已切换到 {counts.get('live', 0)} 条真实样本统计。"
            )
            if counts.get("demo", 0) > 0:
                reasons.append(
                    f"另外还有 {counts.get('demo', 0)} 条示例样本，仅保留做流程演示，不参与当前指标计算。"
                )
        else:
            reasons.append(
                f"当前仍主要依赖 {counts.get('demo', 0)} 条示例样本，结果更适合验证流程而不是判断真实优势。"
            )

        matured_20 = int(maturity_20["matured_samples"])
        immature_20 = int(maturity_20["immature_samples"])
        if matured_20 >= 16:
            reasons.append(f"20 日窗口已有 {matured_20} 条成熟样本，当前复盘结论相对更稳。")
        elif matured_20 >= 6:
            reasons.append(
                f"20 日窗口已有 {matured_20} 条成熟样本，但仍有 {immature_20} 条样本在跟踪中，适合谨慎参考。"
            )
        else:
            reasons.append(
                f"20 日窗口成熟样本只有 {matured_20} 条，当前更适合把结果当作方向参考。"
            )
        return reasons[:3]

    @staticmethod
    def _evaluation_notice(
        evaluation_mode: str,
        mode_breakdown: list[dict[str, object]],
    ) -> str:
        counts = {str(item["mode"]): int(item["sample_size"] ) for item in mode_breakdown}
        if evaluation_mode == "live":
            demo_count = counts.get("demo", 0)
            if demo_count > 0:
                return (
                    f"当前复盘优先使用 {counts.get('live', 0)} 条真实样本。"
                    f"另外还有 {demo_count} 条示例样本，仅用于流程演示，不参与本次指标计算。"
                )
            return f"当前复盘基于 {counts.get('live', 0)} 条真实样本，更适合判断策略在真实环境下的表现。"
        return (
            f"当前还没有真实推荐样本，以下指标全部来自 {counts.get('demo', 0)} 条示例样本，"
            "这些结果适合验证流程和页面，不适合直接判断策略有没有真实优势。"
        )


def _average_optional(values: object) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return None
    return round(sum(filtered) / len(filtered), 2)


def _publish_date(value: object):
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value)).date()
