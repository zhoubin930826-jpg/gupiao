from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping


@dataclass(slots=True)
class YahooSymbolSnapshot:
    symbol: str
    info: dict[str, Any]
    calendar: dict[str, Any]


def fetch_symbol_snapshot(symbol: str) -> YahooSymbolSnapshot | None:
    try:
        import yfinance as yf
    except Exception:
        return None

    lookup_symbol = _normalize_lookup_symbol(symbol)

    try:
        ticker = yf.Ticker(lookup_symbol)
    except Exception:
        return None

    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    try:
        calendar = ticker.calendar or {}
    except Exception:
        calendar = {}

    if not info and not calendar:
        return None
    if not isinstance(calendar, dict):
        calendar = {}
    return YahooSymbolSnapshot(
        symbol=lookup_symbol,
        info=dict(info),
        calendar=dict(calendar),
    )


def build_fundamental_snapshot(snapshot: YahooSymbolSnapshot) -> dict[str, object] | None:
    info = snapshot.info
    payload = {
        "report_period": _serialize_report_period(info.get("mostRecentQuarter") or info.get("lastFiscalYearEnd")),
        "revenue_growth": _scaled_percent(info.get("revenueGrowth")),
        "net_profit_growth": _scaled_percent(info.get("earningsGrowth")),
        "deduct_profit_growth": _scaled_percent(info.get("earningsQuarterlyGrowth") or info.get("earningsGrowth")),
        "roe": _scaled_percent(info.get("returnOnEquity")),
        "gross_margin": _scaled_percent(info.get("grossMargins")),
        "debt_ratio": _safe_float(info.get("debtToEquity")),
        "eps": _safe_float(info.get("trailingEps") or info.get("forwardEps")),
        "operating_cashflow_per_share": _per_share_cashflow(info),
    }
    if not any(value is not None for key, value in payload.items() if key != "report_period"):
        return None
    return payload


def build_event_items(snapshot: YahooSymbolSnapshot) -> list[dict[str, object]]:
    info = snapshot.info
    calendar = snapshot.calendar
    items: list[dict[str, object]] = []

    earnings_date = _extract_first_date(calendar.get("Earnings Date"))
    earnings_growth = _scaled_percent(info.get("earningsGrowth"))
    revenue_growth = _scaled_percent(info.get("revenueGrowth"))
    if earnings_date:
        tone = _tone_from_growth(earnings_growth, revenue_growth)
        detail_bits = [f"预计披露日 {earnings_date.isoformat()}"]
        eps_avg = _safe_float(calendar.get("Earnings Average"))
        revenue_avg = _safe_float(calendar.get("Revenue Average"))
        if eps_avg is not None:
            detail_bits.append(f"市场预期 EPS {eps_avg:.2f}")
        if revenue_avg is not None:
            detail_bits.append(f"市场预期营收 {revenue_avg / 100000000:.2f} 亿")
        items.append(
            {
                "date": earnings_date.isoformat(),
                "category": "财报日历",
                "title": "即将披露财报",
                "headline": f"预计在 {earnings_date.isoformat()} 披露下一次财报",
                "detail": "，".join(detail_bits),
                "tone": tone,
                "source": "财报日历",
                "url": None,
                "tags": ["财报日历", *_growth_tags(earnings_growth, revenue_growth)],
                "watch_points": ["财报披露前后波动通常会放大，别把预期提前当成兑现。"],
            }
        )

    ex_dividend_date = _extract_first_date(calendar.get("Ex-Dividend Date"))
    if ex_dividend_date:
        items.append(
            {
                "date": ex_dividend_date.isoformat(),
                "category": "股息日历",
                "title": "除息日",
                "headline": f"{ex_dividend_date.isoformat()} 是下一次除息日",
                "detail": "除息日前后更适合连同股息率、分红节奏和短线波动一起看。",
                "tone": "neutral",
                "source": "股息日历",
                "url": None,
                "tags": ["股息日历"],
                "watch_points": ["除息本身不是趋势催化，更要看资金是否继续承接。"],
            }
        )

    return items[:3]


def merge_fundamental_snapshots(*snapshots: dict[str, object] | None) -> dict[str, object] | None:
    merged: dict[str, object] = {}
    for snapshot in snapshots:
        if not snapshot:
            continue
        for key, value in snapshot.items():
            if value is None:
                continue
            merged[key] = value
    if not merged:
        return None
    merged.setdefault("report_period", None)
    return merged


def _tone_from_growth(
    earnings_growth: float | None,
    revenue_growth: float | None,
) -> str:
    if earnings_growth is not None and revenue_growth is not None:
        if earnings_growth >= 8 and revenue_growth >= 6:
            return "positive"
        if earnings_growth < 0 or revenue_growth < 0:
            return "caution"
    return "neutral"


def _growth_tags(earnings_growth: float | None, revenue_growth: float | None) -> list[str]:
    tags: list[str] = []
    if earnings_growth is not None and earnings_growth >= 8:
        tags.append("盈利增长")
    elif earnings_growth is not None and earnings_growth < 0:
        tags.append("盈利承压")
    if revenue_growth is not None and revenue_growth >= 6:
        tags.append("营收增长")
    elif revenue_growth is not None and revenue_growth < 0:
        tags.append("营收承压")
    return tags[:2]


def _serialize_report_period(value: object) -> str | None:
    parsed = _extract_first_date(value)
    return parsed.isoformat() if parsed else None


def _extract_first_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, list) and value:
        return _extract_first_date(value[0])
    if isinstance(value, tuple) and value:
        return _extract_first_date(value[0])
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _safe_float(value: object) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scaled_percent(value: object) -> float | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return numeric * 100 if -1 <= numeric <= 1 else numeric


def _per_share_cashflow(info: Mapping[str, Any]) -> float | None:
    cashflow = _safe_float(info.get("operatingCashflow"))
    shares = _safe_float(info.get("sharesOutstanding"))
    if cashflow is None or shares is None or shares <= 0:
        return None
    return cashflow / shares


def _normalize_lookup_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if not text.endswith(".HK"):
        return text
    base = text.removesuffix(".HK")
    digits = "".join(ch for ch in base if ch.isdigit())
    if not digits:
        return text
    return f"{int(digits):04d}.HK"
