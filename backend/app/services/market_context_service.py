from __future__ import annotations

from typing import Literal

import pandas as pd

from app.core.market_scope import DEFAULT_MARKET_SCOPE, market_label, normalize_market_scope

MarketRegime = Literal["risk_on", "balanced", "risk_off"]


def build_market_context(
    *,
    snapshot_df: pd.DataFrame,
    pulse_rows: pd.DataFrame,
    heat_rows: pd.DataFrame,
    market: str = DEFAULT_MARKET_SCOPE,
    breadth_snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized_market = normalize_market_scope(market)
    market_name = market_label(normalized_market)
    if snapshot_df.empty:
        return {
            "regime": "balanced",
            "regime_label": "等待同步",
            "summary": f"{market_name} 当前还没有可分析的样本池，先完成一次同步再判断市场状态。",
            "action_hint": "没有样本时先别下结论，优先确保同步结果完整。",
            "watch_points": [
                "没有样本池时，高分推荐和行业热度都不具备参考意义。",
            ],
            "metrics": [
                _metric("上涨广度", "--", "等待同步", "neutral", "需要先生成股票池后才能判断涨跌扩散。"),
                _metric("主线集中度", "--", "等待同步", "neutral", "同步后才会知道高分主要集中在哪些方向。"),
                _metric("高分密度", "--", "等待同步", "neutral", "同步后才能知道 75 分以上候选占比。"),
                _metric("情绪温度", "--", "等待同步", "neutral", "等待市场温度曲线生成后再看节奏。"),
            ],
        }

    total = int(snapshot_df.shape[0])
    advancers = int((snapshot_df["change_pct"] > 0).sum())
    losers = max(total - advancers, 0)
    adv_ratio = advancers / total if total else 0.0
    avg_change = float(snapshot_df["change_pct"].mean()) if total else 0.0
    avg_turnover = float(snapshot_df["turnover_ratio"].mean()) if total else 0.0
    avg_score = float(snapshot_df["score"].mean()) if total else 0.0
    strong_ratio = float((snapshot_df["score"] >= 75).sum()) / total if total else 0.0

    industry_share = (
        snapshot_df["industry"]
        .fillna("其他")
        .astype(str)
        .value_counts(normalize=True)
    )
    top_industry = str(industry_share.index[0]) if not industry_share.empty else market_name
    top_two_share = float(industry_share.head(2).sum()) if not industry_share.empty else 0.0
    top_heat_score = float(heat_rows.iloc[0]["score"]) if not heat_rows.empty else avg_score

    if breadth_snapshot:
        advancers = int(breadth_snapshot.get("advancers") or advancers)
        losers = int(breadth_snapshot.get("decliners") or losers)
        total_from_breadth = int(breadth_snapshot.get("total_count") or 0)
        if total_from_breadth > 0:
            total = total_from_breadth
        adv_ratio = float(breadth_snapshot.get("advance_ratio") or 0.0) / 100 if breadth_snapshot.get("advance_ratio") is not None else adv_ratio
        avg_change = float(breadth_snapshot.get("avg_change") or avg_change)
        avg_turnover = float(breadth_snapshot.get("avg_turnover") or avg_turnover)
        strong_ratio = float(breadth_snapshot.get("strong_ratio") or 0.0) / 100 if breadth_snapshot.get("strong_ratio") is not None else strong_ratio
        top_industry = str(breadth_snapshot.get("top_industry") or top_industry)
        top_two_share = float(breadth_snapshot.get("top_two_share") or 0.0) / 100 if breadth_snapshot.get("top_two_share") is not None else top_two_share

    latest_pulse = float(pulse_rows["score"].iloc[-1]) if not pulse_rows.empty else avg_score
    pulse_trend = _pulse_trend(pulse_rows)

    breadth_score = round(
        0.45 * _normalize_score(adv_ratio, 0.35, 0.75)
        + 0.30 * _normalize_score(avg_change, -1.2, 2.4)
        + 0.25 * _normalize_score(strong_ratio, 0.08, 0.40)
    )
    activity_score = round(
        0.55 * _normalize_score(avg_turnover, 0.8, 5.5)
        + 0.45 * _normalize_score(latest_pulse, 45, 90)
    )
    concentration_score = round(
        0.65 * _normalize_score(top_two_share, 0.20, 0.60)
        + 0.35 * _normalize_score(top_heat_score, 55, 90)
    )

    regime = _resolve_regime(
        breadth_score=breadth_score,
        activity_score=activity_score,
        latest_pulse=latest_pulse,
        adv_ratio=adv_ratio,
        avg_change=avg_change,
    )
    regime_label = _regime_label(regime)
    summary = _summary(
        regime=regime,
        market_name=market_name,
        top_industry=top_industry,
        top_two_share=top_two_share,
        adv_ratio=adv_ratio,
    )
    action_hint = _action_hint(
        regime=regime,
        concentration_score=concentration_score,
        strong_ratio=strong_ratio,
    )
    watch_points = _watch_points(
        adv_ratio=adv_ratio,
        avg_turnover=avg_turnover,
        strong_ratio=strong_ratio,
        top_two_share=top_two_share,
        pulse_trend=pulse_trend,
    )

    return {
        "regime": regime,
        "regime_label": regime_label,
        "summary": summary,
        "action_hint": action_hint,
        "watch_points": watch_points,
        "metrics": [
            _metric(
                "上涨广度",
                f"{adv_ratio * 100:.0f}%",
                f"上涨 {advancers} / 下跌 {losers}",
                "positive" if adv_ratio >= 0.55 else "negative" if adv_ratio < 0.45 else "neutral",
                "看今天是普涨、分化还是承压，这会直接影响高分票的容错率。",
            ),
            _metric(
                "主线集中度",
                f"{top_two_share * 100:.0f}%",
                f"前两行业主导 {top_industry}",
                "negative" if top_two_share >= 0.52 else "positive" if top_two_share <= 0.35 else "neutral",
                "占比越高，说明高分更集中在少数方向，顺势效率更高但拥挤风险也更大。",
            ),
            _metric(
                "高分密度",
                f"{strong_ratio * 100:.0f}%",
                f"75 分以上均值 {avg_score:.0f}",
                "positive" if strong_ratio >= 0.28 else "neutral" if strong_ratio >= 0.18 else "negative",
                "高分候选占比越高，说明今天更像系统性机会，而不是零星强股。",
            ),
            _metric(
                "情绪温度",
                f"{latest_pulse:.0f} 分",
                f"近 5 日 {'升温' if pulse_trend >= 0 else '降温'} {abs(pulse_trend):.1f} 分",
                "positive" if latest_pulse >= 65 else "negative" if latest_pulse <= 52 else "neutral",
                "市场温度更适合拿来判断该顺势做强，还是先控制节奏。",
            ),
        ],
    }


def _resolve_regime(
    *,
    breadth_score: int,
    activity_score: int,
    latest_pulse: float,
    adv_ratio: float,
    avg_change: float,
) -> MarketRegime:
    if breadth_score >= 68 and activity_score >= 62 and latest_pulse >= 62:
        return "risk_on"
    if breadth_score <= 45 or latest_pulse <= 52 or (adv_ratio < 0.45 and avg_change < 0):
        return "risk_off"
    return "balanced"


def _regime_label(regime: MarketRegime) -> str:
    if regime == "risk_on":
        return "顺势进攻"
    if regime == "risk_off":
        return "谨慎防守"
    return "精选轮动"


def _summary(
    *,
    regime: MarketRegime,
    market_name: str,
    top_industry: str,
    top_two_share: float,
    adv_ratio: float,
) -> str:
    if regime == "risk_on":
        if top_two_share >= 0.45:
            return f"{market_name} 当前更像主线驱动行情，高分集中在 {top_industry} 等少数方向，顺势筛选效率更高。"
        return f"{market_name} 当前偏扩散修复环境，强势方向不只一个，更适合从高分池里精选量价共振的标的。"
    if regime == "risk_off":
        return f"{market_name} 当前偏谨慎，上涨扩散不足，高分候选更适合轻仓观察，不适合把分数直接当成进攻信号。"
    if adv_ratio >= 0.5:
        return f"{market_name} 当前偏轮动分化，能做但需要精选，优先看趋势完整且风险提示更少的票。"
    return f"{market_name} 当前偏弱分化，局部强势仍在，但更要先判断环境而不是只看单票分数。"


def _action_hint(
    *,
    regime: MarketRegime,
    concentration_score: int,
    strong_ratio: float,
) -> str:
    if regime == "risk_on" and concentration_score >= 70:
        return "优先盯主线里的强趋势票，但别忽略抱团过热后的回撤。"
    if regime == "risk_on":
        return "可以适度放宽行业分散度，优先看评分、量价和事件层是否共振。"
    if regime == "risk_off":
        return "先控仓位和节奏，把推荐池当成观察名单，不要把高分直接当买点。"
    if strong_ratio < 0.18:
        return "今天更像结构性机会，宁可少做几只，也别用低质量候选凑仓位。"
    return "更适合少量精选，优先做趋势完整、解释更清楚的候选。"


def _watch_points(
    *,
    adv_ratio: float,
    avg_turnover: float,
    strong_ratio: float,
    top_two_share: float,
    pulse_trend: float,
) -> list[str]:
    points: list[str] = []
    if top_two_share >= 0.45:
        points.append("高分主要集中在前两大行业，主线抱团越强，分化回撤也会越快。")
    if adv_ratio < 0.5:
        points.append("上涨家数没有明显占优，别只盯个别强票而忽略整体环境。")
    if avg_turnover >= 4.5:
        points.append("活跃度偏高时，短线冲高回落会更频繁，入场更要看承接。")
    elif avg_turnover < 2.0:
        points.append("整体活跃度一般，评分再高也要多确认量能有没有真正放出来。")
    if strong_ratio < 0.18:
        points.append("75 分以上候选占比不高，今天更像结构性机会，不像全面扩散。")
    if pulse_trend < 0:
        points.append("近几日市场温度边际走弱，追高前先确认强势方向是否还有接力。")
    return points[:3] or ["先把市场环境和单票解释一起看，别把综合分数单独拿来决策。"]


def _pulse_trend(pulse_rows: pd.DataFrame) -> float:
    if pulse_rows.empty:
        return 0.0
    tail_mean = float(pulse_rows["score"].tail(5).mean())
    if len(pulse_rows) >= 10:
        prev_mean = float(pulse_rows["score"].tail(10).head(5).mean())
    else:
        prev_mean = float(pulse_rows["score"].head(min(5, len(pulse_rows))).mean())
    return round(tail_mean - prev_mean, 1)


def _normalize_score(value: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    ratio = (value - low) / (high - low)
    return max(0.0, min(ratio, 1.0)) * 100


def _metric(
    label: str,
    value: str,
    change: str,
    tone: Literal["positive", "negative", "neutral"],
    description: str,
) -> dict[str, str]:
    return {
        "label": label,
        "value": value,
        "change": change,
        "tone": tone,
        "description": description,
    }
