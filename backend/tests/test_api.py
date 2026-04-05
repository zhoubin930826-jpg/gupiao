import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "scheduler_enabled" in payload


def test_stocks_list(client: TestClient) -> None:
    response = client.get("/api/stocks")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert len(payload["rows"]) > 0


def test_multi_market_switching(client: TestClient) -> None:
    hk_response = client.get("/api/stocks", params={"market": "hk", "page_size": 5})
    assert hk_response.status_code == 200
    hk_payload = hk_response.json()
    assert hk_payload["total"] > 0
    assert hk_payload["rows"][0]["symbol"].endswith(".HK")

    us_response = client.get("/api/stocks", params={"market": "us", "page_size": 5})
    assert us_response.status_code == 200
    us_payload = us_response.json()
    assert us_payload["total"] > 0
    assert us_payload["rows"][0]["symbol"].isupper()

    hk_tasks = client.get("/api/tasks", params={"market": "hk"}).json()
    assert any(str(item["schedule"]).startswith("每日") for item in hk_tasks)
    assert any(item["next_run_at"] is not None for item in hk_tasks)

    us_tasks = client.get("/api/tasks", params={"market": "us"}).json()
    assert any(str(item["schedule"]).startswith("每日") for item in us_tasks)
    assert any(item["next_run_at"] is not None for item in us_tasks)


def test_stock_detail_contains_fundamental_snapshot(client: TestClient) -> None:
    recommendation_rows = client.get("/api/recommendations").json()
    assert recommendation_rows
    symbol = recommendation_rows[0]["symbol"]

    response = client.get(f"/api/stocks/{symbol}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["fundamental"] is not None
    assert "roe" in payload["fundamental"]
    assert payload["move_analysis"] is not None
    assert payload["move_analysis"]["summary"]
    assert len(payload["move_analysis"]["positive_drivers"]) >= 1
    assert payload["event_analysis"] is not None
    assert payload["event_analysis"]["summary"]
    assert payload["capital_flow_analysis"] is not None
    assert payload["capital_flow_analysis"]["status"] in {"ready", "derived", "placeholder"}
    assert payload["capital_flow_analysis"]["tone"] in {"positive", "neutral", "caution"}
    assert payload["recommendation_diagnosis"] is not None
    assert payload["recommendation_diagnosis"]["is_recommended"] is True


def test_stock_detail_explains_why_not_recommended(client: TestClient) -> None:
    recommendation_rows = client.get("/api/recommendations").json()
    recommended_symbols = {row["symbol"] for row in recommendation_rows}
    stock_rows = client.get("/api/stocks", params={"page_size": 200}).json()["rows"]
    non_recommended = next((row for row in stock_rows if row["symbol"] not in recommended_symbols), None)
    if non_recommended is None:
        pytest.skip("Current dataset does not contain extra non-recommended stocks.")

    response = client.get(f"/api/stocks/{non_recommended['symbol']}")
    assert response.status_code == 200
    payload = response.json()
    diagnosis = payload["recommendation_diagnosis"]
    assert diagnosis is not None
    assert diagnosis["is_recommended"] is False
    assert diagnosis["current_rank"] > diagnosis["recommendation_limit"]
    assert len(diagnosis["blocking_points"]) >= 1
    assert len(diagnosis["action_points"]) >= 1


def test_recommendations_include_performance(client: TestClient) -> None:
    response = client.get("/api/recommendations")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0
    assert "recent_return_5d" in payload[0]
    assert payload[0]["move_summary"] is not None
    assert payload[0]["move_bias"] in {"bullish", "mixed", "cautious"}
    assert payload[0]["event_summary"] is not None
    assert payload[0]["event_tone"] in {"positive", "neutral", "caution"}


def test_recommendation_journal_exists(client: TestClient) -> None:
    response = client.get("/api/recommendations/journal")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0
    assert payload[0]["price_at_publish"] > 0


def test_recommendation_review_exists(client: TestClient) -> None:
    response = client.get("/api/recommendations/review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_samples"] > 0
    assert len(payload["window_metrics"]) == 3
    assert any(item["sample_size"] > 0 for item in payload["window_metrics"])


def test_dashboard_contains_market_context(client: TestClient) -> None:
    response = client.get("/api/dashboard/summary", params={"market": "cn"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["market_context"]["regime"] in {"risk_on", "balanced", "risk_off"}
    assert payload["market_context"]["regime_label"]
    assert payload["market_context"]["summary"]
    assert payload["market_context"]["action_hint"]
    assert len(payload["market_context"]["metrics"]) == 4
    assert len(payload["market_context"]["watch_points"]) >= 1
    assert payload["breadth_snapshot"]["total_count"] > 0
    assert payload["breadth_snapshot"]["scope_label"]
    assert len(payload["benchmark_indices"]) >= 1
    assert payload["benchmark_indices"][0]["trend"]
    assert payload["market_capital_flow"]["status"] in {"ready", "derived", "placeholder"}
    assert payload["market_capital_flow"]["summary"]
    assert len(payload["market_capital_flow"]["metrics"]) == 4


def test_strategy_roundtrip(client: TestClient) -> None:
    current = client.get("/api/strategies/default")
    assert current.status_code == 200

    payload = current.json()
    payload["sentiment_weight"] = 20
    payload["money_flow_weight"] = 20

    response = client.put("/api/strategies/default", json=payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["sentiment_weight"] == 20


def test_tasks_endpoint(client: TestClient) -> None:
    response = client.get("/api/tasks")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1


def test_data_source_overview(client: TestClient) -> None:
    response = client.get("/api/data-sources/overview")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) >= 1
    assert any(item["provider_key"] == "sample" for item in payload["items"])
    assert "fallback_chain" in payload
    assert payload["event_sync"]["status"] in {"idle", "partial", "placeholder", "ready"}
    assert "公告" in payload["event_sync"]["configured_sources"]
    assert payload["event_sync"]["coverage_count"] >= 0


def test_watchlist_crud(client: TestClient) -> None:
    symbol = "300308"
    before = client.get("/api/watchlist")
    assert before.status_code == 200
    existing = next((row for row in before.json() if row["symbol"] == symbol), None)

    create = client.post(
        "/api/watchlist",
        json={"symbol": symbol, "source": existing["source"] if existing else "manual"},
    )
    assert create.status_code == 200
    created = create.json()
    assert created["symbol"] == symbol
    assert created["status"] == "watching"
    assert created["added_price"] is not None

    listing = client.get("/api/watchlist")
    assert listing.status_code == 200
    rows = listing.json()
    target = next((row for row in rows if row["symbol"] == symbol), None)
    assert target is not None

    update = client.put(
        f"/api/watchlist/{symbol}",
        json={"status": "holding", "notes": "突破后继续跟踪"},
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["status"] == "holding"
    assert updated["notes"] == "突破后继续跟踪"

    detail = client.get(f"/api/stocks/{symbol}")
    assert detail.status_code == 200
    assert detail.json()["in_watchlist"] is True

    if existing is None:
        delete = client.delete(f"/api/watchlist/{symbol}")
        assert delete.status_code == 204
    else:
        restore = client.put(
            f"/api/watchlist/{symbol}",
            json={"status": existing["status"], "notes": existing["notes"]},
        )
        assert restore.status_code == 200


def test_trade_plan_crud(client: TestClient) -> None:
    create = client.post(
        "/api/trade-plans",
        json={
            "symbol": "300308",
            "source": "recommendation",
            "status": "planned",
            "planned_entry_price": 600,
            "stop_loss_price": 560,
            "target_price": 720,
            "planned_position_pct": 15,
            "notes": "突破后准备分批介入",
        },
    )
    assert create.status_code == 200
    created = create.json()
    assert created["symbol"] == "300308"
    assert created["status"] == "planned"
    assert created["risk_reward_ratio"] == 3.0
    plan_id = created["id"]

    listing = client.get("/api/trade-plans")
    assert listing.status_code == 200
    rows = listing.json()
    target = next((row for row in rows if row["id"] == plan_id), None)
    assert target is not None

    activate = client.put(
        f"/api/trade-plans/{plan_id}",
        json={"status": "active", "actual_entry_price": 605.5},
    )
    assert activate.status_code == 200
    active = activate.json()
    assert active["status"] == "active"
    assert active["actual_entry_price"] == 605.5
    assert active["opened_at"] is not None

    close = client.put(
        f"/api/trade-plans/{plan_id}",
        json={"status": "closed", "actual_exit_price": 632.0},
    )
    assert close.status_code == 200
    closed = close.json()
    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None
    assert closed["realized_return"] is not None

    delete = client.delete(f"/api/trade-plans/{plan_id}")
    assert delete.status_code == 204


def test_portfolio_profile_and_position_crud(client: TestClient) -> None:
    profile = client.get("/api/portfolio/profile")
    assert profile.status_code == 200
    profile_payload = profile.json()
    assert profile_payload["initial_capital"] > 0

    updated_profile = dict(profile_payload)
    updated_profile["initial_capital"] = 600000
    update_profile = client.put("/api/portfolio/profile", json=updated_profile)
    assert update_profile.status_code == 200
    assert update_profile.json()["initial_capital"] == 600000

    create = client.post(
        "/api/portfolio/positions",
        json={
            "symbol": "300308",
            "source": "trade_plan",
            "status": "holding",
            "quantity": 200,
            "entry_price": 600,
            "stop_loss_price": 560,
            "target_price": 720,
            "notes": "从交易计划转入持仓",
        },
    )
    assert create.status_code == 200
    created = create.json()
    assert created["symbol"] == "300308"
    assert created["status"] == "holding"
    assert created["cost_value"] == 120000
    position_id = created["id"]

    overview = client.get("/api/portfolio/overview")
    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["summary"]["holding_count"] >= 1
    assert overview_payload["summary"]["risk_level"] in {"low", "medium", "high"}
    assert "industry_exposure" in overview_payload
    assert isinstance(overview_payload["positions"][0]["risk_flags"], list)
    assert any(item["id"] == position_id for item in overview_payload["positions"])

    close = client.put(
        f"/api/portfolio/positions/{position_id}",
        json={"status": "closed", "exit_price": 630},
    )
    assert close.status_code == 200
    closed = close.json()
    assert closed["status"] == "closed"
    assert closed["realized_pnl"] == 6000

    delete = client.delete(f"/api/portfolio/positions/{position_id}")
    assert delete.status_code == 204


def test_alerts_refresh_and_status_update(client: TestClient) -> None:
    stock = client.get("/api/stocks/300308")
    assert stock.status_code == 200
    latest_price = stock.json()["latest_price"]

    create = client.post(
        "/api/trade-plans",
        json={
            "symbol": "300308",
            "source": "manual",
            "status": "planned",
            "planned_entry_price": round(latest_price * 1.01, 2),
            "stop_loss_price": round(latest_price * 0.9, 2),
            "target_price": round(latest_price * 1.15, 2),
            "notes": "用于验证提醒触发",
        },
    )
    assert create.status_code == 200
    plan_id = create.json()["id"]

    evaluate = client.post("/api/alerts/evaluate")
    assert evaluate.status_code == 200
    overview = evaluate.json()
    assert overview["active_count"] >= 1

    target = next(
        (
            item
            for item in overview["items"]
            if item["source_type"] == "trade_plan"
            and item["source_id"] == plan_id
            and item["kind"] == "entry_zone"
        ),
        None,
    )
    assert target is not None

    handle = client.put(f"/api/alerts/{target['id']}", json={"status": "handled"})
    assert handle.status_code == 200
    assert handle.json()["status"] == "handled"

    handled = client.get("/api/alerts/overview", params={"status": "handled"})
    assert handled.status_code == 200
    assert any(item["id"] == target["id"] for item in handled.json()["items"])

    delete = client.delete(f"/api/trade-plans/{plan_id}")
    assert delete.status_code == 204
