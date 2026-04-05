from datetime import date

from app.services.event_analysis_service import build_event_analysis
from app.services.yfinance_enricher import (
    YahooSymbolSnapshot,
    build_event_items,
    build_fundamental_snapshot,
    merge_fundamental_snapshots,
)


def test_build_fundamental_snapshot_scales_ratios_to_percent() -> None:
    snapshot = YahooSymbolSnapshot(
        symbol="TSLA",
        info={
            "mostRecentQuarter": "2025-12-31",
            "revenueGrowth": 0.157,
            "earningsGrowth": -0.21,
            "earningsQuarterlyGrowth": -0.15,
            "returnOnEquity": 0.32,
            "grossMargins": 0.48,
            "debtToEquity": 22.4,
            "operatingCashflow": 12000000000,
            "sharesOutstanding": 3000000000,
            "trailingEps": 7.9,
        },
        calendar={},
    )

    payload = build_fundamental_snapshot(snapshot)

    assert payload is not None
    assert payload["report_period"] == "2025-12-31"
    assert payload["revenue_growth"] == 15.7
    assert payload["net_profit_growth"] == -21.0
    assert payload["roe"] == 32.0
    assert payload["gross_margin"] == 48.0
    assert payload["debt_ratio"] == 22.4
    assert payload["eps"] == 7.9
    assert payload["operating_cashflow_per_share"] == 4.0


def test_build_event_items_creates_earnings_and_dividend_entries() -> None:
    snapshot = YahooSymbolSnapshot(
        symbol="0700.HK",
        info={
            "earningsGrowth": 0.14,
            "revenueGrowth": 0.12,
        },
        calendar={
            "Earnings Date": [date(2026, 5, 13)],
            "Earnings Average": 7.29,
            "Revenue Average": 198368598920,
            "Ex-Dividend Date": date(2026, 5, 15),
        },
    )

    items = build_event_items(snapshot)

    assert len(items) == 2
    assert items[0]["category"] == "财报日历"
    assert items[0]["tone"] == "positive"
    assert items[1]["category"] == "股息日历"


def test_merge_fundamental_snapshots_prefers_non_null_values() -> None:
    merged = merge_fundamental_snapshots(
        {"report_period": None, "roe": 21.0, "gross_margin": None},
        {"report_period": "2025-12-31", "gross_margin": 48.0},
    )

    assert merged is not None
    assert merged["roe"] == 21.0
    assert merged["gross_margin"] == 48.0
    assert merged["report_period"] == "2025-12-31"


def test_event_analysis_accepts_external_items() -> None:
    payload = build_event_analysis(
        external_items=[
            {
                "date": "2026-05-13",
                "category": "财报日历",
                "title": "即将披露财报",
                "headline": "预计在 2026-05-13 披露下一次财报",
                "detail": "市场正在交易下一次财报预期。",
                "tone": "positive",
                "source": "财报日历",
                "tags": ["财报日历", "盈利增长"],
                "watch_points": ["财报日前后波动会放大。"],
            }
        ]
    )

    assert payload["tone"] == "positive"
    assert "财报日历" in payload["tags"]
    assert len(payload["items"]) == 1
