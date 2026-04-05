from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.market_scope import DEFAULT_MARKET_SCOPE, market_label, normalize_market_scope

CN_BENCHMARKS: tuple[tuple[str, str], ...] = (
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
    ("sh000300", "沪深300"),
)


def collect_market_benchmark_records(
    *,
    ak: Any,
    market: str = DEFAULT_MARKET_SCOPE,
) -> list[dict[str, object]]:
    normalized_market = normalize_market_scope(market)
    if normalized_market != "cn":
        return []

    records: list[dict[str, object]] = []
    # `stock_zh_index_daily` 底层会触发 py_mini_racer；并发拉取时会出现原生崩溃，
    # 这里宁可慢一点，也要保证同步过程稳定。
    for code, name in CN_BENCHMARKS:
        try:
            record = _fetch_cn_benchmark_record(ak, code, name)
        except Exception:
            continue
        if record:
            records.append(record)

    order_map = {code: index for index, (code, _) in enumerate(CN_BENCHMARKS)}
    records.sort(key=lambda item: order_map.get(str(item["code"]), 99))
    return records


def build_market_breadth_from_spot_frame(
    spot_frame: pd.DataFrame,
    market: str = DEFAULT_MARKET_SCOPE,
) -> dict[str, object]:
    normalized_market = normalize_market_scope(market)
    frame = _normalize_spot_frame(spot_frame)
    return _build_market_breadth(frame, normalized_market)


def build_market_breadth_from_records(
    records: list[dict[str, object]],
    market: str = DEFAULT_MARKET_SCOPE,
) -> dict[str, object]:
    normalized_market = normalize_market_scope(market)
    frame = pd.DataFrame(records)
    return _build_market_breadth(frame, normalized_market)


def build_sample_benchmark_records(
    records: list[dict[str, object]],
    market: str = DEFAULT_MARKET_SCOPE,
) -> list[dict[str, object]]:
    normalized_market = normalize_market_scope(market)
    presets: dict[str, list[tuple[str, str, float]]] = {
        "cn": [
            ("sh000001", "上证指数", 3300.0),
            ("sz399001", "深证成指", 10500.0),
            ("sz399006", "创业板指", 2100.0),
            ("sh000300", "沪深300", 3900.0),
        ],
        "hk": [
            ("HSI", "恒生指数", 18000.0),
            ("HSCEI", "国企指数", 6200.0),
            ("HSTECH", "恒生科技指数", 4200.0),
        ],
        "us": [
            ("SPX", "标普500", 5200.0),
            ("IXIC", "纳斯达克综合指数", 16500.0),
            ("DJI", "道琼斯工业指数", 38500.0),
        ],
    }
    frame = pd.DataFrame(records)
    avg_change = float(frame["change_pct"].mean()) if not frame.empty and "change_pct" in frame.columns else 0.0
    avg_score = float(frame["score"].mean()) if not frame.empty and "score" in frame.columns else 60.0
    ret20 = round((avg_score - 60) * 0.35, 2)

    rows: list[dict[str, object]] = []
    for code, name, base_value in presets.get(normalized_market, []):
        latest_price = round(base_value * (1 + avg_change / 120), 2)
        rows.append(
            {
                "code": code,
                "name": name,
                "latest_price": latest_price,
                "change_pct": round(avg_change, 2),
                "return_20d": ret20,
                "trend": _trend_label(avg_change, ret20),
                "takeaway": "示例环境下使用样本池节奏生成，用来占位指数环境展示。",
            }
        )
    return rows


def _fetch_cn_benchmark_record(ak: Any, code: str, name: str) -> dict[str, object] | None:
    frame = ak.stock_zh_index_daily(symbol=code)
    if frame is None or frame.empty:
        return None
    closes = pd.to_numeric(frame["close"], errors="coerce").dropna()
    if closes.empty:
        return None

    latest = float(closes.iloc[-1])
    previous = float(closes.iloc[-2]) if len(closes) > 1 else latest
    change_pct = round((latest / previous - 1) * 100, 2) if previous else 0.0
    return_20d = round((latest / float(closes.iloc[-21]) - 1) * 100, 2) if len(closes) > 20 else None
    ma20 = float(closes.tail(20).mean()) if len(closes) >= 20 else float(closes.mean())
    trend = _trend_label(change_pct, return_20d or 0.0, latest_price=latest, ma20=ma20)
    takeaway = _benchmark_takeaway(name=name, latest_price=latest, ma20=ma20, return_20d=return_20d)

    return {
        "code": code,
        "name": name,
        "latest_price": round(latest, 2),
        "change_pct": change_pct,
        "return_20d": return_20d,
        "trend": trend,
        "takeaway": takeaway,
    }


def _normalize_spot_frame(spot_frame: pd.DataFrame) -> pd.DataFrame:
    frame = spot_frame.copy()
    column_map = {
        "change_pct": ["涨跌幅", "change_pct"],
        "turnover_ratio": ["换手率", "turnover_ratio"],
        "latest_price": ["最新价", "latest_price"],
        "industry": ["所属行业", "行业", "industry", "板块", "board"],
        "score": ["score"],
    }
    for target, candidates in column_map.items():
        for column in candidates:
            if column in frame.columns:
                frame[target] = frame[column]
                break
        else:
            frame[target] = pd.NA

    frame["change_pct"] = pd.to_numeric(frame["change_pct"], errors="coerce")
    frame["turnover_ratio"] = pd.to_numeric(frame["turnover_ratio"], errors="coerce")
    frame["latest_price"] = pd.to_numeric(frame["latest_price"], errors="coerce")
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    frame["industry"] = frame["industry"].fillna("其他").astype(str).str.strip()
    return frame[frame["latest_price"].fillna(0) > 0].copy()


def _build_market_breadth(frame: pd.DataFrame, market: str) -> dict[str, object]:
    market_name = market_label(market)
    if frame.empty:
        return {
            "scope_label": f"{market_name} 活跃样本宽度",
            "total_count": 0,
            "advancers": 0,
            "decliners": 0,
            "advance_ratio": 0.0,
            "strong_count": 0,
            "strong_ratio": 0.0,
            "avg_change": 0.0,
            "avg_turnover": 0.0,
            "top_industry": None,
            "top_two_share": 0.0,
            "limit_up_like": None,
            "limit_down_like": None,
            "summary": "当前还没有足够样本来判断宽度，先完成同步再看扩散情况。",
        }

    total = int(frame.shape[0])
    advancers = int((frame["change_pct"] > 0).sum())
    decliners = max(total - advancers, 0)
    advance_ratio = round(advancers / total * 100, 2) if total else 0.0
    avg_change = round(float(frame["change_pct"].fillna(0).mean()), 2)
    avg_turnover = round(float(frame["turnover_ratio"].fillna(0).mean()), 2)

    strong_threshold = 3.0 if market == "cn" else 2.0
    strong_count = int((frame["change_pct"] >= strong_threshold).sum())
    strong_ratio = round(strong_count / total * 100, 2) if total else 0.0

    industry_share = frame["industry"].value_counts(normalize=True)
    top_industry = str(industry_share.index[0]) if not industry_share.empty else None
    top_two_share = round(float(industry_share.head(2).sum()) * 100, 2) if not industry_share.empty else 0.0

    limit_up_like = int((frame["change_pct"] >= 9.8).sum()) if market == "cn" else None
    limit_down_like = int((frame["change_pct"] <= -9.8).sum()) if market == "cn" else None

    if advance_ratio >= 58 and strong_ratio >= 18:
        summary = "活跃样本里上涨扩散较好，说明今天更像可操作环境，但仍要看主线是否过于拥挤。"
    elif advance_ratio <= 45:
        summary = "活跃样本里上涨扩散偏弱，说明强势票更容易变成局部行情，不适合把分数直接当成买点。"
    else:
        summary = "活跃样本宽度处于中间区间，更像轮动分化，优先做解释更清楚、趋势更完整的标的。"

    return {
        "scope_label": f"{market_name} 活跃样本宽度",
        "total_count": total,
        "advancers": advancers,
        "decliners": decliners,
        "advance_ratio": advance_ratio,
        "strong_count": strong_count,
        "strong_ratio": strong_ratio,
        "avg_change": avg_change,
        "avg_turnover": avg_turnover,
        "top_industry": top_industry,
        "top_two_share": top_two_share,
        "limit_up_like": limit_up_like,
        "limit_down_like": limit_down_like,
        "summary": summary,
    }


def _trend_label(
    change_pct: float,
    return_20d: float,
    *,
    latest_price: float | None = None,
    ma20: float | None = None,
) -> str:
    if return_20d >= 5 and (latest_price is None or ma20 is None or latest_price >= ma20):
        return "强势上行"
    if return_20d <= -5 and (latest_price is None or ma20 is None or latest_price < ma20):
        return "趋势承压"
    if change_pct >= 1:
        return "短线修复"
    return "区间震荡"


def _benchmark_takeaway(
    *,
    name: str,
    latest_price: float,
    ma20: float,
    return_20d: float | None,
) -> str:
    if return_20d is None:
        return f"{name} 当前位于 {latest_price:.2f}，还需要结合更多交易日判断趋势。"
    if latest_price >= ma20 and return_20d >= 0:
        return f"{name} 仍站在 20 日均线之上，近 20 日表现偏稳，适合当作顺势背景参考。"
    if latest_price < ma20 and return_20d < 0:
        return f"{name} 已落到 20 日均线下方，近 20 日承压，说明环境容错率在下降。"
    return f"{name} 仍在均线附近反复，当前更像轮动和震荡，不宜只按单边行情理解。"
