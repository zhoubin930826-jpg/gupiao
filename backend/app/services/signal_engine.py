from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Any, Mapping

import pandas as pd


@dataclass(frozen=True, slots=True)
class StrategyWeights:
    technical_weight: int
    fundamental_weight: int
    money_flow_weight: int
    sentiment_weight: int
    rebalance_cycle: str
    min_turnover: float
    min_listing_days: int
    exclude_st: bool
    exclude_new_shares: bool

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StrategyWeights":
        return cls(
            technical_weight=int(payload["technical_weight"]),
            fundamental_weight=int(payload["fundamental_weight"]),
            money_flow_weight=int(payload["money_flow_weight"]),
            sentiment_weight=int(payload["sentiment_weight"]),
            rebalance_cycle=str(payload["rebalance_cycle"]),
            min_turnover=float(payload["min_turnover"]),
            min_listing_days=int(payload["min_listing_days"]),
            exclude_st=bool(payload["exclude_st"]),
            exclude_new_shares=bool(payload["exclude_new_shares"]),
        )


def enrich_stock_snapshot(
    *,
    symbol: str,
    name: str,
    board: str,
    industry: str,
    latest_price: float,
    change_pct: float,
    turnover_ratio: float,
    pe_ttm: float,
    market_cap: float,
    volume_ratio: float,
    history_df: pd.DataFrame,
    strategy: StrategyWeights,
    fundamental: dict[str, object] | None = None,
) -> dict[str, object]:
    closes = history_df["close"]
    highs = history_df["high"]
    ma5 = float(history_df["ma5"].iloc[-1])
    ma20 = float(history_df["ma20"].iloc[-1])
    ma60 = float(closes.rolling(window=60, min_periods=20).mean().iloc[-1])
    ret_5 = _return_ratio(closes, 5)
    ret_20 = _return_ratio(closes, 20)
    high_60 = float(highs.tail(60).max())
    close = float(closes.iloc[-1])
    near_high_ratio = close / high_60 if high_60 else 0.0
    amount_ratio = _amount_ratio(history_df)
    listing_days = int(history_df.shape[0])

    technical_score = round(
        0.35 * _normalize(ret_20, -0.12, 0.28)
        + 0.25 * (100 if close >= ma20 else 35)
        + 0.20 * (100 if ma5 >= ma20 else 30)
        + 0.20 * _normalize(near_high_ratio, 0.78, 1.01)
    )
    money_flow_score = round(
        0.45 * _normalize(turnover_ratio, 0.6, 10.0)
        + 0.25 * _normalize(volume_ratio, 0.6, 3.2)
        + 0.30 * _normalize(amount_ratio, 0.75, 2.1)
    )
    valuation_score = _valuation_score(pe_ttm)
    size_score = _size_score(market_cap)
    finance_growth_score = _financial_growth_score(fundamental)
    finance_quality_score = _financial_quality_score(fundamental)
    fundamental_score = round(
        0.35 * valuation_score
        + 0.20 * size_score
        + 0.25 * finance_growth_score
        + 0.20 * finance_quality_score
    )
    sentiment_score = round(
        0.40 * _normalize(change_pct / 100, -0.06, 0.06)
        + 0.35 * _normalize(ret_5, -0.08, 0.12)
        + 0.25 * _normalize(near_high_ratio, 0.82, 1.01)
    )

    total_score = round(
        (
            technical_score * strategy.technical_weight
            + fundamental_score * strategy.fundamental_weight
            + money_flow_score * strategy.money_flow_weight
            + sentiment_score * strategy.sentiment_weight
        )
        / 100
    )
    total_score = int(_clamp(total_score, 35, 96))

    tags = _build_tags(
        board=board,
        industry=industry,
        technical_score=technical_score,
        money_flow_score=money_flow_score,
        sentiment_score=sentiment_score,
        pe_ttm=pe_ttm,
        near_high_ratio=near_high_ratio,
        fundamental=fundamental,
    )
    thesis = _build_thesis(
        industry=industry,
        board=board,
        technical_score=technical_score,
        money_flow_score=money_flow_score,
        sentiment_score=sentiment_score,
        fundamental_score=fundamental_score,
        fundamental=fundamental,
    )
    thesis_points = [
        _trend_line(close, ma5, ma20, ma60),
        f"近 20 日涨幅 {ret_20 * 100:.2f}%，距离 60 日高点约 {(1 - near_high_ratio) * 100:.1f}%。",
        f"换手率 {turnover_ratio:.2f}%，量比 {volume_ratio:.2f}，近 5 日成交额是近 20 日均值的 {amount_ratio:.2f} 倍。",
        _valuation_line(pe_ttm, market_cap),
    ]
    risk_notes = _build_risk_notes(
        pe_ttm=pe_ttm,
        turnover_ratio=turnover_ratio,
        change_pct=change_pct,
        close=close,
        ma20=ma20,
        listing_days=listing_days,
        strategy=strategy,
        fundamental=fundamental,
    )
    entry_window = _entry_window(close=close, ma5=ma5, ma20=ma20, near_high_ratio=near_high_ratio)
    expected_holding_days = _holding_days(strategy.rebalance_cycle, total_score)

    return {
        "symbol": symbol,
        "name": name,
        "board": board,
        "industry": industry,
        "latest_price": round(latest_price, 2),
        "change_pct": round(change_pct, 2),
        "turnover_ratio": round(turnover_ratio, 2),
        "pe_ttm": round(pe_ttm, 2),
        "market_cap": round(market_cap, 2),
        "score": total_score,
        "thesis": thesis,
        "tags": tags,
        "thesis_points": thesis_points[:4],
        "risk_notes": risk_notes,
        "risk": risk_notes[0],
        "entry_window": entry_window,
        "expected_holding_days": expected_holding_days,
        "signal_breakdown": [
            {
                "dimension": "技术面",
                "score": technical_score,
                "takeaway": _technical_takeaway(close=close, ma20=ma20, ma5=ma5, ret_20=ret_20),
            },
            {
                "dimension": "基本面",
                "score": fundamental_score,
                "takeaway": _fundamental_takeaway(
                    pe_ttm=pe_ttm,
                    market_cap=market_cap,
                    fundamental=fundamental,
                ),
            },
            {
                "dimension": "资金面",
                "score": money_flow_score,
                "takeaway": _money_flow_takeaway(turnover_ratio=turnover_ratio, amount_ratio=amount_ratio),
            },
            {
                "dimension": "情绪面",
                "score": sentiment_score,
                "takeaway": _sentiment_takeaway(change_pct=change_pct, ret_5=ret_5, near_high_ratio=near_high_ratio),
            },
        ],
        "fundamental": fundamental,
    }


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    ratio = (value - low) / (high - low)
    return round(_clamp(ratio, 0.0, 1.0) * 100, 2)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _return_ratio(series: pd.Series, lookback: int) -> float:
    if len(series) <= lookback:
        return float(series.iloc[-1] / series.iloc[0] - 1) if len(series) > 1 else 0.0
    base = float(series.iloc[-(lookback + 1)])
    latest = float(series.iloc[-1])
    if base == 0:
        return 0.0
    return latest / base - 1


def _amount_ratio(history_df: pd.DataFrame) -> float:
    if "amount" not in history_df.columns:
        return 1.0
    recent = float(history_df["amount"].tail(5).mean())
    baseline = float(history_df["amount"].tail(20).mean())
    if baseline <= 0:
        return 1.0
    return recent / baseline


def _valuation_score(pe_ttm: float) -> int:
    if pe_ttm <= 0:
        return 56
    if pe_ttm <= 18:
        return 88
    if pe_ttm <= 35:
        return 82
    if pe_ttm <= 55:
        return 72
    if pe_ttm <= 85:
        return 58
    return 44


def _size_score(market_cap: float) -> int:
    if market_cap <= 0:
        return 45
    score = 48 + log10(max(market_cap, 10)) * 13
    return int(round(_clamp(score, 45, 88)))


def _build_tags(
    *,
    board: str,
    industry: str,
    technical_score: int,
    money_flow_score: int,
    sentiment_score: int,
    pe_ttm: float,
    near_high_ratio: float,
    fundamental: dict[str, object] | None,
) -> list[str]:
    tags = [board, industry]
    if technical_score >= 82:
        tags.append("趋势完整")
    if money_flow_score >= 80:
        tags.append("资金活跃")
    if sentiment_score >= 80:
        tags.append("情绪偏强")
    if pe_ttm > 0 and pe_ttm <= 25:
        tags.append("估值友好")
    if near_high_ratio >= 0.97:
        tags.append("接近新高")
    if fundamental:
        roe = _as_optional_float(fundamental.get("roe"))
        revenue_growth = _as_optional_float(fundamental.get("revenue_growth"))
        if roe is not None and roe >= 15:
            tags.append("ROE较强")
        if revenue_growth is not None and revenue_growth >= 15:
            tags.append("成长性")
    deduped: list[str] = []
    for tag in tags:
        if tag and tag not in deduped:
            deduped.append(tag)
    return deduped[:5]


def _build_thesis(
    *,
    industry: str,
    board: str,
    technical_score: int,
    money_flow_score: int,
    sentiment_score: int,
    fundamental_score: int,
    fundamental: dict[str, object] | None,
) -> str:
    strengths = sorted(
        [
            ("技术形态", technical_score),
            ("资金活跃度", money_flow_score),
            ("市场情绪", sentiment_score),
            ("估值与体量", fundamental_score),
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    first, second = strengths[:2]
    if fundamental:
        roe = _as_optional_float(fundamental.get("roe"))
        revenue_growth = _as_optional_float(fundamental.get("revenue_growth"))
        if roe is not None and roe >= 15 and revenue_growth is not None and revenue_growth >= 10:
            return f"{industry or board}方向里，财务质量和市场强度同时在线，适合作为优先复核候选。"
    return f"{industry or board}方向里，{first[0]}和{second[0]}更突出，适合作为下一轮人工复核候选。"


def _trend_line(close: float, ma5: float, ma20: float, ma60: float) -> str:
    if close >= ma20 and ma5 >= ma20:
        return f"收盘价 {close:.2f} 站上 MA20({ma20:.2f})，短中期趋势仍偏多。"
    if close >= ma20:
        return f"收盘价仍在 MA20({ma20:.2f}) 上方，但短线结构还需要确认。"
    return f"收盘价暂未站稳 MA20({ma20:.2f})，趋势修复仍需时间。"


def _valuation_line(pe_ttm: float, market_cap: float) -> str:
    if pe_ttm <= 0:
        return f"当前动态 PE 暂不具备可比性，总市值约 {market_cap:.0f} 亿，建议结合行业景气再判断。"
    return f"动态 PE 约 {pe_ttm:.1f} 倍，总市值约 {market_cap:.0f} 亿，可作为估值与容量的粗筛依据。"


def _build_risk_notes(
    *,
    pe_ttm: float,
    turnover_ratio: float,
    change_pct: float,
    close: float,
    ma20: float,
    listing_days: int,
    strategy: StrategyWeights,
    fundamental: dict[str, object] | None,
) -> list[str]:
    notes: list[str] = []
    if pe_ttm > 60:
        notes.append("估值偏高，情绪回落时波动可能明显放大。")
    if turnover_ratio >= 8 or change_pct >= 6:
        notes.append("短线热度较高，追高容错率偏低。")
    if close < ma20:
        notes.append("尚未重新站稳中期均线，趋势确认不足。")
    if strategy.exclude_new_shares and listing_days < strategy.min_listing_days:
        notes.append("历史样本偏短，容易受到新股阶段性波动影响。")
    if fundamental:
        revenue_growth = _as_optional_float(fundamental.get("revenue_growth"))
        net_profit_growth = _as_optional_float(fundamental.get("net_profit_growth"))
        debt_ratio = _as_optional_float(fundamental.get("debt_ratio"))
        if revenue_growth is not None and revenue_growth < 0:
            notes.append("最近一期营收同比为负，基本面修复还需要观察。")
        if net_profit_growth is not None and net_profit_growth < 0:
            notes.append("净利润增速为负，业绩波动会压制估值弹性。")
        if debt_ratio is not None and debt_ratio > 65:
            notes.append("资产负债率偏高，景气回落时抗压能力要重点留意。")
    if not notes:
        notes.append("核心风险来自板块轮动和个股趋势反复，需要持续复核。")
    return notes[:3]


def _entry_window(*, close: float, ma5: float, ma20: float, near_high_ratio: float) -> str:
    if close >= ma20 and near_high_ratio >= 0.97:
        return "放量突破前高后跟踪"
    if close >= ma20:
        return "缩量回踩 MA5 或 MA20 时观察"
    return "等待重新站稳 MA20 后再跟踪"


def _holding_days(rebalance_cycle: str, total_score: int) -> int:
    base_days = {"daily": 4, "weekly": 8, "biweekly": 12}.get(rebalance_cycle, 8)
    if total_score >= 90:
        return base_days + 3
    if total_score >= 82:
        return base_days + 1
    return base_days


def _technical_takeaway(*, close: float, ma20: float, ma5: float, ret_20: float) -> str:
    if close >= ma20 and ma5 >= ma20 and ret_20 > 0:
        return "均线结构和中期涨幅都支持顺势观察。"
    if close >= ma20:
        return "仍在中期均线之上，但短线趋势还不够凌厉。"
    return "尚未形成强趋势，更适合耐心等待确认。"


def _fundamental_takeaway(
    *,
    pe_ttm: float,
    market_cap: float,
    fundamental: dict[str, object] | None,
) -> str:
    if fundamental:
        roe = _as_optional_float(fundamental.get("roe"))
        revenue_growth = _as_optional_float(fundamental.get("revenue_growth"))
        net_profit_growth = _as_optional_float(fundamental.get("net_profit_growth"))
        if roe is not None and revenue_growth is not None and net_profit_growth is not None:
            return (
                f"ROE {roe:.1f}%，营收同比 {revenue_growth:.1f}%，净利润同比 {net_profit_growth:.1f}%，"
                "基本面可直接参与复核。"
            )
    if pe_ttm > 0 and pe_ttm <= 25:
        return "估值相对克制，适合作为中线候选继续跟踪。"
    if pe_ttm <= 0:
        return "盈利指标暂不稳定，基本面需要额外核验。"
    return f"估值不算便宜，总市值约 {market_cap:.0f} 亿，适合结合景气度再判断。"


def _money_flow_takeaway(*, turnover_ratio: float, amount_ratio: float) -> str:
    if turnover_ratio >= 4 and amount_ratio >= 1:
        return "换手和成交额都偏活跃，资金承接较好。"
    if turnover_ratio >= 2:
        return "资金活跃度中性偏上，适合继续观察。"
    return "资金参与度一般，更多依赖后续放量确认。"


def _sentiment_takeaway(*, change_pct: float, ret_5: float, near_high_ratio: float) -> str:
    if change_pct > 2 and ret_5 > 0 and near_high_ratio >= 0.95:
        return "短线情绪和位置都偏强，容易进入关注名单。"
    if ret_5 > 0:
        return "情绪有所修复，但强度还需要连续性。"
    return "情绪偏中性，建议减少主观追高。"


def _financial_growth_score(fundamental: dict[str, object] | None) -> int:
    if not fundamental:
        return 56
    revenue_growth = _as_optional_float(fundamental.get("revenue_growth"))
    profit_growth = _as_optional_float(fundamental.get("net_profit_growth"))
    deduct_growth = _as_optional_float(fundamental.get("deduct_profit_growth"))
    components = [
        _normalize_optional(revenue_growth, -20, 35, default=52),
        _normalize_optional(profit_growth, -25, 45, default=52),
        _normalize_optional(deduct_growth, -25, 45, default=50),
    ]
    return int(round(sum(components) / len(components)))


def _financial_quality_score(fundamental: dict[str, object] | None) -> int:
    if not fundamental:
        return 58
    roe = _as_optional_float(fundamental.get("roe"))
    gross_margin = _as_optional_float(fundamental.get("gross_margin"))
    debt_ratio = _as_optional_float(fundamental.get("debt_ratio"))
    cashflow = _as_optional_float(fundamental.get("operating_cashflow_per_share"))
    components = [
        _normalize_optional(roe, 5, 28, default=54),
        _normalize_optional(gross_margin, 10, 65, default=56),
        _normalize_optional(None if debt_ratio is None else 100 - debt_ratio, 20, 80, default=55),
        _normalize_optional(cashflow, -1, 6, default=52),
    ]
    return int(round(sum(components) / len(components)))


def _normalize_optional(value: float | None, low: float, high: float, default: float) -> float:
    if value is None:
        return default
    return _normalize(value, low, high)


def _as_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
