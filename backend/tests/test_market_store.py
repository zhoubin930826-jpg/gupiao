import json

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


def test_stock_detail_uses_cached_capital_flow_only(tmp_path, monkeypatch) -> None:
    store = MarketDataStore(str(tmp_path / "market.duckdb"))
    store.initialize()
    symbol = str(store.get_recommendations()[0]["symbol"])

    with store._connect() as conn:
        conn.execute(
            "update stock_snapshot set capital_flow_json = ? where market = ? and symbol = ?",
            [None, "cn", symbol],
        )

    def _should_not_run(*args, **kwargs):
        raise AssertionError("capital flow enrichment should not run during detail reads")

    monkeypatch.setattr(
        "app.services.capital_flow_service.collect_cn_stock_capital_flow_analysis",
        _should_not_run,
    )

    detail = store.get_stock_detail(symbol)
    assert detail["capital_flow_analysis"] is not None
    assert detail["capital_flow_analysis"]["status"] in {"ready", "derived", "placeholder"}


def test_stock_detail_uses_cached_derived_capital_flow_payload(tmp_path, monkeypatch) -> None:
    store = MarketDataStore(str(tmp_path / "market.duckdb"))
    store.initialize()
    symbol = str(store.get_recommendations()[0]["symbol"])

    cached_payload = {
        "status": "derived",
        "tone": "neutral",
        "summary": "cached placeholder from prior sync",
    }

    with store._connect() as conn:
        conn.execute(
            "update stock_snapshot set capital_flow_json = ? where market = ? and symbol = ?",
            [json.dumps(cached_payload), "cn", symbol],
        )

    def _should_not_run(*args, **kwargs):
        raise AssertionError("capital flow enrichment should not replace cached payloads")

    monkeypatch.setattr(
        "app.services.capital_flow_service.collect_cn_stock_capital_flow_analysis",
        _should_not_run,
    )

    detail = store.get_stock_detail(symbol)
    assert detail["capital_flow_analysis"] == cached_payload
