from app.services.market_store import MarketDataStore
from app.services.sample_market import build_demo_snapshot_records


def test_refresh_snapshot_records_handles_empty_lhb_rows_for_hk(tmp_path) -> None:
    db_path = tmp_path / "market.duckdb"
    store = MarketDataStore(str(db_path))

    store.refresh_snapshot_records(
        build_demo_snapshot_records("hk"),
        source="sample",
        market="hk",
        lhb_rows=[],
    )

    summary = store.get_dashboard_summary("hk")
    assert summary["market_capital_flow"]["status"] == "placeholder"
    assert summary["headline"]
