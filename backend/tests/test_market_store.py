from app.services.market_store import MarketDataStore


def test_initialize_seeds_cn_dataset_only(tmp_path) -> None:
    db_path = tmp_path / "market.duckdb"
    store = MarketDataStore(str(db_path))
    store.initialize()

    summary = store.get_dashboard_summary()
    assert summary["headline"]
    recommendations = store.get_recommendations()
    assert recommendations
    assert all(str(item["symbol"]).isdigit() and len(str(item["symbol"])) == 6 for item in recommendations)


def test_event_sync_overview_uses_cn_sources_only(tmp_path) -> None:
    db_path = tmp_path / "market.duckdb"
    store = MarketDataStore(str(db_path))
    store.initialize()

    overview = store.get_event_sync_overview()

    assert overview["configured_sources"] == ["公告", "业绩预告"]
