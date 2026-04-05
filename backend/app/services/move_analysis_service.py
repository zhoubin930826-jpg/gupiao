from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

MoveBias = Literal["bullish", "mixed", "cautious"]
DriverTone = Literal["positive", "negative"]


@dataclass(frozen=True, slots=True)
class _Driver:
    title: str
    detail: str
    strength: int
    tone: DriverTone

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "detail": self.detail,
            "strength": self.strength,
            "tone": self.tone,
        }


def build_move_analysis(
    *,
    latest_price: float,
    change_pct: float,
    turnover_ratio: float,
    pe_ttm: float,
    market_cap: float,
    history_df: pd.DataFrame,
    fundamental: dict[str, object] | None = None,
    volume_ratio: float | None = None,
    min_turnover: float = 1.0,
) -> dict[str, object]:
    if history_df.empty:
        return _fallback_analysis(
            latest_price=latest_price,
            change_pct=change_pct,
            turnover_ratio=turnover_ratio,
            pe_ttm=pe_ttm,
            fundamental=fundamental,
        )

    closes = history_df["close"].astype(float)
    highs = history_df["high"].astype(float)
    close = float(closes.iloc[-1]) if not closes.empty else latest_price
    ma5 = _last_or_default(history_df, "ma5", closes.rolling(window=5, min_periods=1).mean())
    ma20 = _last_or_default(history_df, "ma20", closes.rolling(window=20, min_periods=1).mean())
    ma60 = float(closes.rolling(window=60, min_periods=20).mean().iloc[-1])
    ret_5 = _return_ratio(closes, 5)
    ret_20 = _return_ratio(closes, 20)
    high_60 = float(highs.tail(60).max()) if not highs.empty else close
    near_high_ratio = close / high_60 if high_60 else 0.0
    amount_ratio = _liquidity_ratio(history_df, "amount")
    volume_ratio_calc = volume_ratio if volume_ratio is not None else _liquidity_ratio(history_df, "volume")
    listing_days = int(history_df.shape[0])

    positive: list[_Driver] = []
    negative: list[_Driver] = []
    watch_points: list[str] = []

    if close >= ma20 and ma5 >= ma20:
        strength = 88 if ret_20 >= 0.18 else 82 if ret_20 >= 0.08 else 75
        positive.append(
            _Driver(
                title="趋势延续",
                detail=f"收盘仍站在 20 日线上方，5 日线保持强于 20 日线，近 20 日涨幅 {ret_20 * 100:.2f}%。",
                strength=strength,
                tone="positive",
            )
        )
        watch_points.append("若后续跌破 20 日线，当前趋势驱动会明显降级。")
    else:
        negative.append(
            _Driver(
                title="趋势承接不足",
                detail=f"收盘相对 20 日线偏弱，近 20 日涨幅 {ret_20 * 100:.2f}%，说明趋势还不够完整。",
                strength=84 if close < ma20 else 72,
                tone="negative",
            )
        )

    if near_high_ratio >= 0.97:
        positive.append(
            _Driver(
                title="接近阶段高点",
                detail=f"当前价格距离 60 日高点约 {(1 - near_high_ratio) * 100:.1f}%，更容易吸引追强资金。",
                strength=79 if near_high_ratio >= 0.99 else 72,
                tone="positive",
            )
        )
        watch_points.append("越接近阶段高点，越要看放量突破还是放量滞涨。")
    elif near_high_ratio <= 0.88:
        negative.append(
            _Driver(
                title="离高点偏远",
                detail=f"当前距离 60 日高点约 {(1 - near_high_ratio) * 100:.1f}%，更像修复段而不是强趋势段。",
                strength=68,
                tone="negative",
            )
        )

    if turnover_ratio >= max(min_turnover * 1.4, 2.0) or volume_ratio_calc >= 1.45 or amount_ratio >= 1.2:
        positive.append(
            _Driver(
                title="量能放大",
                detail=f"换手率 {turnover_ratio:.2f}%，近 5 日量能约为近 20 日均值的 {max(amount_ratio, volume_ratio_calc):.2f} 倍。",
                strength=85 if max(amount_ratio, volume_ratio_calc) >= 1.7 else 76,
                tone="positive",
            )
        )
        watch_points.append("量能若无法延续，强势票往往会先表现为冲高回落。")
    elif turnover_ratio < min_turnover or max(amount_ratio, volume_ratio_calc) < 0.92:
        negative.append(
            _Driver(
                title="量能不足",
                detail=f"换手率 {turnover_ratio:.2f}%，量能承接偏弱，后续上行需要新的成交放大来确认。",
                strength=73,
                tone="negative",
            )
        )

    if pe_ttm > 0 and pe_ttm <= 25:
        positive.append(
            _Driver(
                title="估值安全垫",
                detail=f"当前 PE(TTM) 约 {pe_ttm:.1f}，在系统口径里仍算相对可接受区间。",
                strength=69,
                tone="positive",
            )
        )
    elif pe_ttm >= 55:
        negative.append(
            _Driver(
                title="估值透支",
                detail=f"当前 PE(TTM) 约 {pe_ttm:.1f}，后续需要更强的业绩或情绪兑现来支撑估值。",
                strength=80 if pe_ttm >= 80 else 72,
                tone="negative",
            )
        )
        watch_points.append("高估值状态下，一旦情绪回落，回撤速度通常会快于低估值标的。")

    _append_fundamental_drivers(positive, negative, watch_points, fundamental)

    if change_pct >= 4.5 or ret_5 >= 0.10:
        negative.append(
            _Driver(
                title="短线过热",
                detail=f"单日涨幅 {change_pct:.2f}%，近 5 日涨幅 {ret_5 * 100:.2f}%，短线追高性价比在下降。",
                strength=82 if change_pct >= 6 or ret_5 >= 0.14 else 70,
                tone="negative",
            )
        )
        watch_points.append("如果下一次放量上冲不能继续封住强度，先防追高回撤。")
    elif change_pct > 0 and ret_5 > 0.03:
        positive.append(
            _Driver(
                title="情绪回暖",
                detail=f"单日涨幅 {change_pct:.2f}%，近 5 日涨幅 {ret_5 * 100:.2f}%，说明短线关注度在抬升。",
                strength=67,
                tone="positive",
            )
        )
    elif change_pct < -3 or ret_5 < -0.06:
        negative.append(
            _Driver(
                title="情绪转弱",
                detail=f"单日涨幅 {change_pct:.2f}%，近 5 日涨幅 {ret_5 * 100:.2f}%，短线情绪仍在降温。",
                strength=71,
                tone="negative",
            )
        )

    if market_cap <= 1200 and turnover_ratio >= 3:
        positive.append(
            _Driver(
                title="弹性资金偏好",
                detail=f"当前市值约 {market_cap:.0f} 亿，叠加较高换手，更容易被弹性资金选中。",
                strength=66,
                tone="positive",
            )
        )
    elif market_cap >= 5000 and change_pct > 0:
        positive.append(
            _Driver(
                title="大票承接稳定",
                detail=f"当前市值约 {market_cap:.0f} 亿，仍能维持红盘，说明承接更偏配置型资金。",
                strength=62,
                tone="positive",
            )
        )

    if listing_days < 80:
        negative.append(
            _Driver(
                title="历史样本偏短",
                detail=f"当前仅纳入约 {listing_days} 个交易日，趋势和均线判断的稳定性还有限。",
                strength=60,
                tone="negative",
            )
        )

    positive = _dedupe_sort(positive)
    negative = _dedupe_sort(negative)
    bias = _resolve_bias(positive, negative)
    summary = _build_summary(bias=bias, positive=positive, negative=negative)
    watch_points = _finalize_watch_points(watch_points, bias)

    return {
        "bias": bias,
        "summary": summary,
        "positive_drivers": [item.as_dict() for item in positive[:3]],
        "negative_drivers": [item.as_dict() for item in negative[:3]],
        "watch_points": watch_points[:3],
    }


def _fallback_analysis(
    *,
    latest_price: float,
    change_pct: float,
    turnover_ratio: float,
    pe_ttm: float,
    fundamental: dict[str, object] | None,
) -> dict[str, object]:
    positive: list[_Driver] = []
    negative: list[_Driver] = []
    watch_points = ["补齐至少 20 个交易日历史后，再看趋势与量能的稳定性。"]

    if change_pct > 0:
        positive.append(
            _Driver(
                title="短线价格偏强",
                detail=f"最新价 {latest_price:.2f}，单日涨幅 {change_pct:.2f}%。",
                strength=66,
                tone="positive",
            )
        )
    else:
        negative.append(
            _Driver(
                title="短线价格偏弱",
                detail=f"最新价 {latest_price:.2f}，单日涨幅 {change_pct:.2f}%。",
                strength=66,
                tone="negative",
            )
        )

    if turnover_ratio >= 2:
        positive.append(
            _Driver(
                title="换手不低",
                detail=f"当前换手率 {turnover_ratio:.2f}%，说明市场仍在交易这只票。",
                strength=64,
                tone="positive",
            )
        )
    else:
        negative.append(
            _Driver(
                title="交易热度一般",
                detail=f"当前换手率 {turnover_ratio:.2f}%，活跃度还不算高。",
                strength=58,
                tone="negative",
            )
        )

    if pe_ttm > 0 and pe_ttm <= 25:
        positive.append(
            _Driver(
                title="估值可接受",
                detail=f"当前 PE(TTM) 约 {pe_ttm:.1f}。",
                strength=62,
                tone="positive",
            )
        )
    elif pe_ttm >= 55:
        negative.append(
            _Driver(
                title="估值偏高",
                detail=f"当前 PE(TTM) 约 {pe_ttm:.1f}。",
                strength=68,
                tone="negative",
            )
        )

    _append_fundamental_drivers(positive, negative, watch_points, fundamental)
    positive = _dedupe_sort(positive)
    negative = _dedupe_sort(negative)
    bias = _resolve_bias(positive, negative)
    return {
        "bias": bias,
        "summary": _build_summary(bias=bias, positive=positive, negative=negative),
        "positive_drivers": [item.as_dict() for item in positive[:3]],
        "negative_drivers": [item.as_dict() for item in negative[:3]],
        "watch_points": _finalize_watch_points(watch_points, bias)[:3],
    }


def _append_fundamental_drivers(
    positive: list[_Driver],
    negative: list[_Driver],
    watch_points: list[str],
    fundamental: dict[str, object] | None,
) -> None:
    if not fundamental:
        return

    revenue_growth = _to_float(fundamental.get("revenue_growth"))
    profit_growth = _to_float(fundamental.get("net_profit_growth"))
    roe = _to_float(fundamental.get("roe"))
    gross_margin = _to_float(fundamental.get("gross_margin"))
    debt_ratio = _to_float(fundamental.get("debt_ratio"))

    if revenue_growth is not None and profit_growth is not None:
        if revenue_growth >= 12 and profit_growth >= 15:
            positive.append(
                _Driver(
                    title="业绩增速支撑",
                    detail=f"营收同比 {revenue_growth:.1f}%，净利润同比 {profit_growth:.1f}%，基本面兑现仍在延续。",
                    strength=84 if profit_growth >= 25 else 76,
                    tone="positive",
                )
            )
        elif revenue_growth < 0 or profit_growth < 0:
            negative.append(
                _Driver(
                    title="业绩兑现压力",
                    detail=f"营收同比 {revenue_growth:.1f}%，净利润同比 {profit_growth:.1f}%，基本面承接仍需观察。",
                    strength=77,
                    tone="negative",
                )
            )
            watch_points.append("如果下一份财报不能修复增速，题材和情绪溢价会更容易回吐。")

    if roe is not None and gross_margin is not None and debt_ratio is not None:
        if roe >= 12 and gross_margin >= 25 and debt_ratio <= 55:
            positive.append(
                _Driver(
                    title="财务质量稳定",
                    detail=f"ROE {roe:.1f}%，毛利率 {gross_margin:.1f}%，资产负债率 {debt_ratio:.1f}%，质量端没有明显短板。",
                    strength=72,
                    tone="positive",
                )
            )
        elif debt_ratio >= 65:
            negative.append(
                _Driver(
                    title="财务杠杆偏高",
                    detail=f"资产负债率 {debt_ratio:.1f}%，财务弹性会受到一定约束。",
                    strength=68,
                    tone="negative",
                )
            )


def _resolve_bias(positive: list[_Driver], negative: list[_Driver]) -> MoveBias:
    positive_power = sum(item.strength for item in positive[:2])
    negative_power = sum(item.strength for item in negative[:2])
    delta = positive_power - negative_power
    if delta >= 20:
        return "bullish"
    if delta <= -12:
        return "cautious"
    return "mixed"


def _build_summary(
    *,
    bias: MoveBias,
    positive: list[_Driver],
    negative: list[_Driver],
) -> str:
    primary_positive = positive[0].title if positive else "情绪修复"
    secondary_positive = positive[1].title if len(positive) > 1 else "资金承接"
    primary_negative = negative[0].title if negative else "短线波动"

    if bias == "bullish":
        return f"当前更像由{primary_positive}和{secondary_positive}共同驱动的上涨，强势逻辑暂时完整。"
    if bias == "cautious":
        return f"当前主要受{primary_negative}压制，短线更适合先把风险位置看清，再决定是否参与。"
    return f"当前同时存在{primary_positive}和{primary_negative}，更像边走边验证的阶段。"


def _finalize_watch_points(watch_points: list[str], bias: MoveBias) -> list[str]:
    fallback = {
        "bullish": "保持强势的关键是趋势不破坏、量能不快速衰减。",
        "mixed": "这类票更适合等下一次量价确认，而不是只看当天分数。",
        "cautious": "先看风险释放是否结束，再考虑胜率问题。",
    }
    points = list(dict.fromkeys(point.strip() for point in watch_points if point.strip()))
    if not points:
        points.append(fallback[bias])
    elif len(points) < 2:
        points.append(fallback[bias])
    return points


def _dedupe_sort(items: list[_Driver]) -> list[_Driver]:
    unique: dict[str, _Driver] = {}
    for item in items:
        current = unique.get(item.title)
        if current is None or item.strength > current.strength:
            unique[item.title] = item
    return sorted(unique.values(), key=lambda item: item.strength, reverse=True)


def _last_or_default(frame: pd.DataFrame, column: str, fallback: pd.Series) -> float:
    if column in frame.columns and not frame[column].empty:
        return float(frame[column].iloc[-1])
    return float(fallback.iloc[-1])


def _return_ratio(series: pd.Series, lookback: int) -> float:
    if len(series) <= lookback:
        return float(series.iloc[-1] / series.iloc[0] - 1) if len(series) > 1 else 0.0
    base = float(series.iloc[-(lookback + 1)])
    latest = float(series.iloc[-1])
    if base == 0:
        return 0.0
    return latest / base - 1


def _liquidity_ratio(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 1.0
    recent = float(frame[column].tail(5).mean())
    baseline = float(frame[column].tail(20).mean())
    if baseline <= 0:
        return 1.0
    return recent / baseline


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
