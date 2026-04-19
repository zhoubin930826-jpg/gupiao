from datetime import date

from app.services.recommendation_tracking_service import (
    matured_for_window,
    traded_days_since_publish,
)


def test_matured_for_window_requires_full_trading_window() -> None:
    price_rows = [
        ("2026-04-01", 10.0),
        ("2026-04-02", 10.1),
        ("2026-04-03", 10.2),
        ("2026-04-06", 10.3),
        ("2026-04-07", 10.4),
    ]
    assert matured_for_window(price_rows, date(2026, 4, 1), 5) is False

    extended_rows = [*price_rows, ("2026-04-08", 10.5)]
    assert matured_for_window(extended_rows, date(2026, 4, 1), 5) is True


def test_traded_days_since_publish_counts_rows_after_publish() -> None:
    price_rows = [
        ("2026-04-01", 10.0),
        ("2026-04-02", 10.1),
        ("2026-04-03", 10.2),
        ("2026-04-06", 10.3),
    ]
    assert traded_days_since_publish(price_rows, date(2026, 4, 1)) == 3
