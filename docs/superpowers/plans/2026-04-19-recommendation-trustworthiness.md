# Recommendation Trustworthiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make recommendation results easier to trust by exposing explicit confidence evidence, separating tracking samples from matured samples, and surfacing review trust level + maturity across the backend and frontend.

**Architecture:** Add two small backend helper services to centralize trust and tracking logic, extend the API schema with explicit confidence/maturity fields, and then wire the recommendation, review, and stock-detail views to those fields. Keep the existing scoring algorithm intact; this plan only improves transparency, sample handling, and trust communication.

**Tech Stack:** FastAPI, SQLAlchemy, DuckDB, pytest, Vue 3, TypeScript, Element Plus, Vite

---

## Scope And File Map

- Create: `backend/app/services/recommendation_trust_service.py`
  Purpose: compute `data_mode`, strongest signals, primary risk, confidence score, and confidence notice from existing recommendation evidence.
- Create: `backend/app/services/recommendation_tracking_service.py`
  Purpose: centralize trading-window maturity helpers and price-map lookup for recommendation journal/review code.
- Modify: `backend/app/schemas/market.py`
  Purpose: add trust and maturity response models for recommendation, review, and stock detail APIs.
- Modify: `backend/app/services/market_store.py`
  Purpose: enrich recommendation rows with trust metadata and expose snapshot timestamps needed by stock detail trust summaries.
- Modify: `backend/app/services/recommendation_service.py`
  Purpose: add journal maturity/tracking fields using trading-day windows.
- Modify: `backend/app/services/recommendation_review_service.py`
  Purpose: add review trust level, trust reasons, and maturity breakdown while reusing the shared tracking helpers.
- Modify: `backend/app/api/routes/stocks.py`
  Purpose: attach a backend-built `recommendation_trust` summary to stock detail responses.
- Modify: `backend/tests/test_api.py`
  Purpose: verify the new API contracts and source-level frontend strings that enforce the trust UX.
- Create: `backend/tests/test_recommendation_tracking_service.py`
  Purpose: lock the trading-window maturity rules to trading days instead of calendar days.
- Modify: `frontend/src/types/market.ts`
  Purpose: mirror the backend schema additions.
- Modify: `frontend/src/views/RecommendationView.vue`
  Purpose: show confidence evidence on recommendation cards and rename top metrics to tracking-oriented copy.
- Modify: `frontend/src/views/ReviewView.vue`
  Purpose: show `trust_level`, `trust_reasons`, and per-window maturity breakdown ahead of review metrics.
- Modify: `frontend/src/views/StockDetailView.vue`
  Purpose: add a compact trust summary card so stock detail uses the same confidence contract as the recommendation list.
- Modify: `docs/BEGINNER_GUIDE.md`
  Purpose: document how to interpret `demo/live`, tracking vs matured samples, and review trust levels.

## Task 1: Shared Trust Contract For Current Recommendations

**Files:**
- Create: `backend/app/services/recommendation_trust_service.py`
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/app/services/market_store.py`
- Modify: `backend/app/api/routes/stocks.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing API contract tests**

```python
def test_recommendations_expose_confidence_contract(client: TestClient) -> None:
    response = client.get("/api/recommendations")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0

    row = payload[0]
    assert row["data_mode"] in {"demo", "live"}
    assert row["snapshot_updated_at"]
    assert len(row["strongest_signals"]) >= 1
    assert row["primary_risk"]
    assert 20 <= row["confidence_score"] <= 95
    assert row["confidence_notice"]


def test_stock_detail_exposes_recommendation_trust_summary(client: TestClient) -> None:
    recommendation_rows = client.get("/api/recommendations").json()
    assert recommendation_rows
    symbol = recommendation_rows[0]["symbol"]

    response = client.get(f"/api/stocks/{symbol}")
    assert response.status_code == 200
    payload = response.json()
    trust = payload["recommendation_trust"]
    assert trust["data_mode"] in {"demo", "live"}
    assert trust["snapshot_updated_at"]
    assert len(trust["strongest_signals"]) >= 1
    assert trust["primary_risk"]
    assert 20 <= trust["confidence_score"] <= 95
    assert trust["confidence_notice"]
```

- [ ] **Step 2: Run the focused API tests to confirm the current failure**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_api.py::test_recommendations_expose_confidence_contract backend/tests/test_api.py::test_stock_detail_exposes_recommendation_trust_summary -v`

Expected: `FAIL` because `/api/recommendations` and `/api/stocks/{symbol}` do not yet expose the trust fields.

- [ ] **Step 3: Add the backend trust schema and helper service**

```python
# backend/app/schemas/market.py
class RecommendationConfidenceSignal(BaseModel):
    dimension: str
    score: int
    takeaway: str


class RecommendationTrustSummary(BaseModel):
    data_mode: Literal["demo", "live"]
    snapshot_updated_at: str
    strongest_signals: list[RecommendationConfidenceSignal]
    primary_risk: str
    confidence_score: int
    confidence_notice: str


class RecommendationItem(BaseModel):
    symbol: str
    name: str
    score: int
    entry_window: str
    expected_holding_days: int
    thesis: str
    risk: str
    tags: list[str]
    latest_price: float | None = None
    recent_return_5d: float | None = None
    recent_return_20d: float | None = None
    move_bias: MoveBias | None = None
    move_summary: str | None = None
    event_tone: EventTone | None = None
    event_summary: str | None = None
    data_mode: Literal["demo", "live"]
    snapshot_updated_at: str
    strongest_signals: list[RecommendationConfidenceSignal]
    primary_risk: str
    confidence_score: int
    confidence_notice: str
    in_watchlist: bool = False


class StockDetail(StockItem):
    price_series: list[PricePoint]
    thesis_points: list[str]
    risk_notes: list[str]
    signal_breakdown: list[SignalBreakdown]
    fundamental: FundamentalSnapshot | None = None
    move_analysis: MoveAnalysis | None = None
    event_analysis: EventAnalysis | None = None
    capital_flow_analysis: CapitalFlowAnalysis | None = None
    recommendation_diagnosis: RecommendationDiagnosis | None = None
    recommendation_trust: RecommendationTrustSummary | None = None
```

```python
# backend/app/services/recommendation_trust_service.py
from __future__ import annotations

from typing import Any, Literal, Mapping


def data_mode_from_source(source: str) -> Literal["demo", "live"]:
    return "demo" if str(source).startswith("sample") else "live"


def build_recommendation_trust(
    *,
    source: str,
    snapshot_updated_at: str,
    signal_breakdown: list[Mapping[str, Any]],
    risk_notes: list[str],
) -> dict[str, object]:
    strongest_signals = [
        {
            "dimension": str(item.get("dimension") or "信号"),
            "score": int(item.get("score") or 0),
            "takeaway": str(item.get("takeaway") or "").strip(),
        }
        for item in sorted(signal_breakdown, key=lambda item: int(item.get("score") or 0), reverse=True)[:2]
    ]
    data_mode = data_mode_from_source(source)
    primary_risk = next((item.strip() for item in risk_notes if item.strip()), "当前仍需人工复核主要风险。")
    signal_base = round(sum(item["score"] for item in strongest_signals) / len(strongest_signals)) if strongest_signals else 55
    mode_bonus = 10 if data_mode == "live" else -10
    risk_penalty = 8 if primary_risk else 0
    confidence_score = int(max(20, min(95, round(signal_base * 0.7 + mode_bonus - risk_penalty))))
    confidence_notice = (
        "当前基于真实同步快照，适合优先人工复核，但仍需结合主要风险控制节奏。"
        if data_mode == "live"
        else "当前基于示例快照，只适合流程演示，不宜直接当成真实效果判断。"
    )
    return {
        "data_mode": data_mode,
        "snapshot_updated_at": snapshot_updated_at,
        "strongest_signals": strongest_signals,
        "primary_risk": primary_risk,
        "confidence_score": confidence_score,
        "confidence_notice": confidence_notice,
    }
```

- [ ] **Step 4: Wire the trust helper into recommendation and stock-detail serialization**

```python
# backend/app/services/market_store.py
from app.services.recommendation_trust_service import build_recommendation_trust

def get_recommendations(self, market: str = DEFAULT_MARKET_SCOPE) -> list[dict[str, object]]:
    normalized_market = normalize_market_scope(market)
    with self._connect() as conn:
        rows = conn.execute(
            """
            select
                recommendation_item.symbol,
                recommendation_item.name,
                recommendation_item.score,
                recommendation_item.entry_window,
                recommendation_item.expected_holding_days,
                recommendation_item.thesis,
                recommendation_item.risk,
                recommendation_item.tags_json,
                recommendation_item.updated_at,
                stock_snapshot.signal_breakdown_json,
                stock_snapshot.risk_notes_json,
                stock_snapshot.move_analysis_json,
                stock_snapshot.event_analysis_json,
                sync_metadata.source
            from recommendation_item
            left join stock_snapshot
                on recommendation_item.market = stock_snapshot.market
                and recommendation_item.symbol = stock_snapshot.symbol
            left join sync_metadata
                on recommendation_item.market = sync_metadata.market
            where recommendation_item.market = ?
            order by recommendation_item.score desc
            """,
            [normalized_market],
        ).fetchdf()

    recommendations = []
    for row in rows.to_dict(orient="records"):
        row["tags"] = json.loads(row.pop("tags_json"))
        signal_breakdown = json.loads(row.pop("signal_breakdown_json")) if row.get("signal_breakdown_json") else []
        risk_notes = json.loads(row.pop("risk_notes_json")) if row.get("risk_notes_json") else []
        trust = build_recommendation_trust(
            source=str(row.pop("source") or "sample"),
            snapshot_updated_at=str(row.pop("updated_at")).replace("T", " "),
            signal_breakdown=signal_breakdown,
            risk_notes=[str(item) for item in risk_notes],
        )
        row.update(trust)
        recommendations.append(row)
    return recommendations
```

```python
# backend/app/api/routes/stocks.py
from app.services.recommendation_trust_service import build_recommendation_trust

@router.get("/{symbol}", response_model=StockDetail)
def stock_detail(
    symbol: str,
    market_store: MarketDataStore = Depends(get_market_store),
    db: Session = Depends(get_db),
) -> StockDetail:
    payload = market_store.get_stock_detail(symbol)
    payload["in_watchlist"] = symbol in WatchlistService.symbols_in_watchlist(db, [symbol])
    payload["recommendation_diagnosis"] = RecommendationDiagnosisService.build(
        detail=payload,
        ranking=market_store.get_recommendation_context(symbol),
        strategy=StrategyConfig.model_validate(StrategyService.read_config(db)),
    )
    payload["recommendation_trust"] = build_recommendation_trust(
        source=market_store.current_source(),
        snapshot_updated_at=str(payload.pop("snapshot_updated_at")).replace("T", " "),
        signal_breakdown=list(payload.get("signal_breakdown", [])),
        risk_notes=[str(item) for item in payload.get("risk_notes", [])],
    )
    return StockDetail.model_validate(payload)
```

- [ ] **Step 5: Re-run the focused API tests**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_api.py::test_recommendations_expose_confidence_contract backend/tests/test_api.py::test_stock_detail_exposes_recommendation_trust_summary -v`

Expected: both tests `PASS`

- [ ] **Step 6: Commit the shared trust contract**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add backend/app/schemas/market.py backend/app/services/recommendation_trust_service.py backend/app/services/market_store.py backend/app/api/routes/stocks.py backend/tests/test_api.py
git commit -m "feat: add recommendation trust contract"
```

## Task 2: Trading-Window Tracking In Recommendation Journal

**Files:**
- Create: `backend/app/services/recommendation_tracking_service.py`
- Create: `backend/tests/test_recommendation_tracking_service.py`
- Modify: `backend/app/services/recommendation_service.py`
- Modify: `backend/tests/test_api.py`
- Test: `backend/tests/test_recommendation_tracking_service.py`, `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing helper and API tests**

```python
# backend/tests/test_recommendation_tracking_service.py
from datetime import date

from app.services.recommendation_tracking_service import matured_for_window, traded_days_since_publish


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
```

```python
# backend/tests/test_api.py
def test_recommendation_journal_exposes_tracking_status(client: TestClient) -> None:
    response = client.get("/api/recommendations/journal")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0

    row = payload[0]
    assert isinstance(row["days_since_publish"], int)
    assert row["tracking_status"] in {"tracking", "matured"}
    assert row["is_matured_for_expected_window"] is (row["tracking_status"] == "matured")
```

- [ ] **Step 2: Run the focused tests and confirm the current failure**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_recommendation_tracking_service.py backend/tests/test_api.py::test_recommendation_journal_exposes_tracking_status -v`

Expected: `FAIL` because the tracking helper file and journal fields do not exist yet.

- [ ] **Step 3: Add the shared tracking helper**

```python
# backend/app/services/recommendation_tracking_service.py
from __future__ import annotations

from datetime import date

import duckdb

from app.services.market_store import MarketDataStore


def build_price_map(
    market_store: MarketDataStore,
    symbols: list[str],
) -> dict[str, list[tuple[str, float]]]:
    if not symbols:
        return {}
    placeholders = ",".join(["?"] * len(symbols))
    with duckdb.connect(market_store.db_path) as conn:
        rows = conn.execute(
            f"""
            select symbol, date, close
            from stock_price
            where symbol in ({placeholders})
            order by symbol, date
            """,
            symbols,
        ).fetchall()
    grouped: dict[str, list[tuple[str, float]]] = {}
    for symbol, trade_date, close in rows:
        grouped.setdefault(str(symbol), []).append((str(trade_date), float(close)))
    return grouped


def locate_start_index(price_rows: list[tuple[str, float]], publish_date: date) -> int | None:
    publish_text = publish_date.isoformat()
    for index, (trade_date, _) in enumerate(price_rows):
        if trade_date >= publish_text:
            return index
    return None


def matured_for_window(price_rows: list[tuple[str, float]], publish_date: date, window: int) -> bool:
    start_index = locate_start_index(price_rows, publish_date)
    return start_index is not None and start_index + window < len(price_rows)


def traded_days_since_publish(price_rows: list[tuple[str, float]], publish_date: date) -> int:
    start_index = locate_start_index(price_rows, publish_date)
    if start_index is None:
        return 0
    return max(len(price_rows) - start_index - 1, 0)
```

- [ ] **Step 4: Use the tracking helper when serializing recommendation journal rows**

```python
# backend/app/services/recommendation_service.py
from app.services.recommendation_tracking_service import build_price_map, matured_for_window, traded_days_since_publish
from app.services.recommendation_trust_service import data_mode_from_source

def list_journal(
    db: Session,
    market_store: MarketDataStore,
    *,
    limit: int = 24,
) -> list[dict[str, object]]:
    rows = (
        db.query(RecommendationJournal)
        .order_by(RecommendationJournal.generated_at.desc(), RecommendationJournal.id.desc())
        .all()
    )
    rows = [row for row in rows if is_a_share_symbol(row.symbol)][:limit]
    if not rows:
        return []

    latest_prices = market_store.get_latest_snapshot_map([row.symbol for row in rows])
    price_map = build_price_map(market_store, [row.symbol for row in rows])
    journal: list[dict[str, object]] = []
    for row in rows:
        publish_date = row.generated_at.date()
        price_rows = price_map.get(row.symbol, [])
        matured = matured_for_window(price_rows, publish_date, row.expected_holding_days)
        current_price = latest_prices.get(row.symbol)
        current_return = None
        if current_price is not None and row.price_at_publish > 0:
            current_return = round((current_price / row.price_at_publish - 1) * 100, 2)
        journal.append(
            {
                "run_key": row.run_key,
                "generated_at": row.generated_at.isoformat(timespec="seconds"),
                "symbol": row.symbol,
                "name": row.name,
                "score": row.score,
                "entry_window": row.entry_window,
                "expected_holding_days": row.expected_holding_days,
                "thesis": row.thesis,
                "risk": row.risk,
                "source": row.source,
                "data_mode": data_mode_from_source(row.source),
                "tags": json.loads(row.tags_json),
                "price_at_publish": round(row.price_at_publish, 2),
                "current_price": round(current_price, 2) if current_price is not None else None,
                "current_return": current_return,
                "days_since_publish": traded_days_since_publish(price_rows, publish_date),
                "tracking_status": "matured" if matured else "tracking",
                "is_matured_for_expected_window": matured,
            }
        )
    return journal
```

- [ ] **Step 5: Re-run the focused tracking tests**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_recommendation_tracking_service.py backend/tests/test_api.py::test_recommendation_journal_exposes_tracking_status -v`

Expected: all selected tests `PASS`

- [ ] **Step 6: Commit the journal tracking changes**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add backend/app/services/recommendation_tracking_service.py backend/app/services/recommendation_service.py backend/tests/test_recommendation_tracking_service.py backend/tests/test_api.py
git commit -m "feat: track recommendation journal maturity"
```

## Task 3: Review Trust Level And Maturity Breakdown

**Files:**
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/app/services/recommendation_review_service.py`
- Modify: `backend/tests/test_api.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Add failing review contract tests**

```python
def test_recommendation_review_exposes_trust_level_and_maturity(client: TestClient) -> None:
    response = client.get("/api/recommendations/review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["trust_level"] in {"low", "medium", "high"}
    assert len(payload["trust_reasons"]) >= 2
    assert {item["window_days"] for item in payload["maturity_breakdown"]} == {5, 10, 20}
    assert all(
        item["matured_samples"] + item["immature_samples"] == item["total_samples"]
        for item in payload["maturity_breakdown"]
    )
```

```python
def test_recommendation_review_low_trust_when_live_samples_are_still_thin(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuery:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def order_by(self, *args: object) -> "FakeQuery":
            return self

        def all(self) -> list[object]:
            return self._rows

    class FakeSession:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def query(self, model: object) -> FakeQuery:
            return FakeQuery(self._rows)

    class FakeRow:
        def __init__(self, run_key: str, source: str, symbol: str) -> None:
            self.run_key = run_key
            self.source = source
            self.symbol = symbol
            self.generated_at = datetime.fromisoformat("2026-04-19T10:00:00")
            self.id = 1
            self.name = symbol
            self.score = 80
            self.entry_window = "watch"
            self.expected_holding_days = 5
            self.thesis = "thesis"
            self.tags_json = "[]"
            self.price_at_publish = 10.0

    rows = [
        FakeRow("demo-new-1", "sample", "000001"),
        FakeRow("demo-new-2", "sample", "000002"),
        FakeRow("live-old-1", "akshare-live", "000003"),
    ]

    monkeypatch.setattr(
        "app.services.recommendation_review_service.is_a_share_symbol",
        lambda symbol: True,
    )
    monkeypatch.setattr(
        "app.services.recommendation_review_service.build_price_map",
        lambda market_store, symbols: {
            "000003": [
                ("2026-04-21", 10.0),
                ("2026-04-22", 10.1),
                ("2026-04-23", 10.2),
            ]
        },
    )
    monkeypatch.setattr(
        RecommendationReviewService,
        "_serialize_row",
        classmethod(
            lambda cls, row, price_rows: {
                "run_key": row.run_key,
                "generated_at": row.generated_at.isoformat(timespec="seconds"),
                "symbol": row.symbol,
                "name": row.name,
                "score": row.score,
                "source": row.source,
                "data_mode": "demo" if str(row.source).startswith("sample") else "live",
                "entry_window": row.entry_window,
                "expected_holding_days": row.expected_holding_days,
                "thesis": row.thesis,
                "tags": [],
                "price_at_publish": row.price_at_publish,
                "latest_known_price": None,
                "return_5d": None,
                "return_10d": None,
                "return_20d": None,
                "expected_return": None,
            }
        ),
    )

    payload = RecommendationReviewService.build_review(FakeSession(rows), object(), limit=2)
    assert payload["trust_level"] == "low"
    assert len(payload["trust_reasons"]) >= 2
    maturity = {item["window_days"]: item for item in payload["maturity_breakdown"]}
    assert maturity[20]["matured_samples"] == 0
```

- [ ] **Step 2: Run the focused review tests to confirm the current failure**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_api.py::test_recommendation_review_exposes_trust_level_and_maturity backend/tests/test_api.py::test_recommendation_review_low_trust_when_live_samples_are_still_thin -v`

Expected: `FAIL` because the review payload does not yet expose `trust_level`, `trust_reasons`, or `maturity_breakdown`.

- [ ] **Step 3: Extend the review schema and service logic**

```python
# backend/app/schemas/market.py
class RecommendationReviewMaturityMetric(BaseModel):
    window_days: int
    total_samples: int
    matured_samples: int
    immature_samples: int


class RecommendationReviewResponse(BaseModel):
    total_samples: int
    evaluation_mode: Literal["demo", "live"]
    evaluation_notice: str
    trust_level: Literal["low", "medium", "high"]
    trust_reasons: list[str]
    mode_breakdown: list[RecommendationModeBreakdown]
    maturity_breakdown: list[RecommendationReviewMaturityMetric]
    window_metrics: list[RecommendationReviewWindowMetric]
    recent_runs: list[RecommendationReviewRun]
    top_hits: list[RecommendationReviewSample]
    top_misses: list[RecommendationReviewSample]
    samples: list[RecommendationReviewSample]
```

```python
# backend/app/services/recommendation_review_service.py
from app.services.recommendation_tracking_service import build_price_map, locate_start_index, matured_for_window
from app.services.recommendation_trust_service import data_mode_from_source

def build_review(
    cls,
    db: Session,
    market_store: MarketDataStore,
    *,
    limit: int = 120,
) -> dict[str, object]:
    journal_rows = (
        db.query(RecommendationJournal)
        .order_by(RecommendationJournal.generated_at.desc(), RecommendationJournal.id.desc())
        .all()
    )
    journal_rows = [row for row in journal_rows if is_a_share_symbol(row.symbol)]
    mode_breakdown = cls._build_mode_breakdown(journal_rows)
    if not journal_rows:
        return {
            "total_samples": 0,
            "evaluation_mode": "demo",
            "evaluation_notice": "当前还没有可用于复盘的样本，后续积累真实推荐后会自动切换到真实样本统计。",
            "trust_level": "low",
            "trust_reasons": [
                "当前还没有真实样本，复盘结果暂时不能当成策略优势证明。",
                "请先继续积累真实推荐样本，并观察 20 日窗口成熟数量。",
            ],
            "mode_breakdown": mode_breakdown,
            "maturity_breakdown": [
                {"window_days": window, "total_samples": 0, "matured_samples": 0, "immature_samples": 0}
                for window in WINDOWS
            ],
            "window_metrics": [],
            "recent_runs": [],
            "top_hits": [],
            "top_misses": [],
            "samples": [],
        }

    evaluation_mode = "live" if any(data_mode_from_source(row.source) == "live" for row in journal_rows) else "demo"
    evaluation_rows = [row for row in journal_rows if data_mode_from_source(row.source) == evaluation_mode][:limit]
    symbols = sorted({row.symbol for row in evaluation_rows})
    price_map = build_price_map(market_store, symbols)
    sample_rows = [cls._serialize_row(row, price_map.get(row.symbol, [])) for row in evaluation_rows]
    sortable = [row for row in sample_rows if row.get("expected_return") is not None]
    top_hits = sorted(sortable, key=lambda item: float(item["expected_return"]), reverse=True)[:5]
    top_misses = sorted(sortable, key=lambda item: float(item["expected_return"]))[:5]
    maturity_breakdown = [
        cls._build_maturity_metric(evaluation_rows, price_map, window)
        for window in WINDOWS
    ]
    trust_level = cls._trust_level(evaluation_mode, maturity_breakdown)
    trust_reasons = cls._trust_reasons(evaluation_mode, mode_breakdown, maturity_breakdown)
    return {
        "total_samples": len(sample_rows),
        "evaluation_mode": evaluation_mode,
        "evaluation_notice": cls._evaluation_notice(evaluation_mode, mode_breakdown),
        "trust_level": trust_level,
        "trust_reasons": trust_reasons,
        "mode_breakdown": mode_breakdown,
        "maturity_breakdown": maturity_breakdown,
        "window_metrics": [cls._build_window_metric(sample_rows, window) for window in WINDOWS],
        "recent_runs": cls._build_run_summaries(sample_rows),
        "top_hits": top_hits,
        "top_misses": top_misses,
        "samples": sample_rows,
    }

@classmethod
def _build_maturity_metric(
    cls,
    rows: list[RecommendationJournal],
    price_map: dict[str, list[tuple[str, float]]],
    window: int,
) -> dict[str, object]:
    matured_samples = sum(
        1
        for row in rows
        if matured_for_window(price_map.get(row.symbol, []), row.generated_at.date(), window)
    )
    total_samples = len(rows)
    return {
        "window_days": window,
        "total_samples": total_samples,
        "matured_samples": matured_samples,
        "immature_samples": total_samples - matured_samples,
    }

@staticmethod
def _trust_level(
    evaluation_mode: str,
    maturity_breakdown: list[dict[str, object]],
) -> str:
    maturity_20 = next(item for item in maturity_breakdown if item["window_days"] == 20)
    matured_20 = int(maturity_20["matured_samples"])
    if evaluation_mode == "live" and matured_20 >= 16:
        return "high"
    if evaluation_mode == "live" and matured_20 >= 6:
        return "medium"
    return "low"
```

- [ ] **Step 4: Re-run the focused review tests**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_api.py::test_recommendation_review_exposes_trust_level_and_maturity backend/tests/test_api.py::test_recommendation_review_low_trust_when_live_samples_are_still_thin -v`

Expected: both tests `PASS`

- [ ] **Step 5: Commit the review trust changes**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add backend/app/schemas/market.py backend/app/services/recommendation_review_service.py backend/tests/test_api.py
git commit -m "feat: expose review trust level and maturity"
```

## Task 4: Frontend Trust Experience And Beginner Guide

**Files:**
- Modify: `frontend/src/types/market.ts`
- Modify: `frontend/src/views/RecommendationView.vue`
- Modify: `frontend/src/views/ReviewView.vue`
- Modify: `frontend/src/views/StockDetailView.vue`
- Modify: `docs/BEGINNER_GUIDE.md`
- Modify: `backend/tests/test_api.py`
- Test: `backend/tests/test_api.py`, frontend build

- [ ] **Step 1: Add failing source-level assertions for the trust UX**

```python
def test_recommendation_view_mentions_tracking_snapshot_copy() -> None:
    source = Path("frontend/src/views/RecommendationView.vue").read_text(encoding="utf-8")
    assert "运行中跟踪快照" in source
    assert "confidence_notice" in source
    assert "is_matured_for_expected_window" in source


def test_review_view_mentions_trust_level_and_maturity_breakdown() -> None:
    source = Path("frontend/src/views/ReviewView.vue").read_text(encoding="utf-8")
    assert "trust_level" in source
    assert "trust_reasons" in source
    assert "maturity_breakdown" in source


def test_stock_detail_view_mentions_recommendation_trust_summary() -> None:
    source = Path("frontend/src/views/StockDetailView.vue").read_text(encoding="utf-8")
    assert "recommendation_trust" in source
    assert "可信度说明" in source
```

- [ ] **Step 2: Run the focused assertions before editing the frontend**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_api.py::test_recommendation_view_mentions_tracking_snapshot_copy backend/tests/test_api.py::test_review_view_mentions_trust_level_and_maturity_breakdown backend/tests/test_api.py::test_stock_detail_view_mentions_recommendation_trust_summary -v`

Expected: `FAIL` because the current views do not contain the new trust-focused UI copy or fields.

- [ ] **Step 3: Update the frontend types and recommendation/review/detail views**

```ts
// frontend/src/types/market.ts
export interface RecommendationConfidenceSignal {
  dimension: string
  score: number
  takeaway: string
}

export interface RecommendationTrustSummary {
  data_mode: 'demo' | 'live'
  snapshot_updated_at: string
  strongest_signals: RecommendationConfidenceSignal[]
  primary_risk: string
  confidence_score: number
  confidence_notice: string
}

export interface RecommendationItem {
  symbol: string
  name: string
  score: number
  entry_window: string
  expected_holding_days: number
  thesis: string
  risk: string
  tags: string[]
  latest_price: number | null
  recent_return_5d: number | null
  recent_return_20d: number | null
  move_bias: MoveBias | null
  move_summary: string | null
  event_tone: EventTone | null
  event_summary: string | null
  data_mode: 'demo' | 'live'
  snapshot_updated_at: string
  strongest_signals: RecommendationConfidenceSignal[]
  primary_risk: string
  confidence_score: number
  confidence_notice: string
  in_watchlist: boolean
}

export interface RecommendationJournalItem {
  run_key: string
  generated_at: string
  symbol: string
  name: string
  score: number
  entry_window: string
  expected_holding_days: number
  thesis: string
  risk: string
  source: string
  data_mode: 'demo' | 'live'
  tags: string[]
  price_at_publish: number
  current_price: number | null
  current_return: number | null
  days_since_publish: number
  tracking_status: 'tracking' | 'matured'
  is_matured_for_expected_window: boolean
}

export interface RecommendationReviewMaturityMetric {
  window_days: number
  total_samples: number
  matured_samples: number
  immature_samples: number
}

export interface RecommendationReviewResponse {
  total_samples: number
  evaluation_mode: 'demo' | 'live'
  evaluation_notice: string
  trust_level: 'low' | 'medium' | 'high'
  trust_reasons: string[]
  mode_breakdown: RecommendationModeBreakdown[]
  maturity_breakdown: RecommendationReviewMaturityMetric[]
  window_metrics: RecommendationReviewWindowMetric[]
  recent_runs: RecommendationReviewRun[]
  top_hits: RecommendationReviewSample[]
  top_misses: RecommendationReviewSample[]
  samples: RecommendationReviewSample[]
}

export interface StockDetail extends StockItem {
  price_series: PricePoint[]
  thesis_points: string[]
  risk_notes: string[]
  signal_breakdown: SignalBreakdown[]
  fundamental: FundamentalSnapshot | null
  move_analysis: MoveAnalysis | null
  event_analysis: EventAnalysis | null
  capital_flow_analysis: CapitalFlowAnalysis | null
  recommendation_diagnosis: RecommendationDiagnosis | null
  recommendation_trust: RecommendationTrustSummary | null
}
```

```vue
<!-- frontend/src/views/RecommendationView.vue -->
<el-alert
  title="运行中跟踪快照"
  type="info"
  :closable="false"
>
  <template #default>
    顶部卡片只反映当前推荐日志的跟踪状态，不替代复盘页的正式验证结论。
  </template>
</el-alert>

<section class="review-grid">
  <el-card class="panel-card">
    <span class="review-label">已成熟样本</span>
    <strong class="review-value">{{ maturedRows.length }}</strong>
    <p>已经走完预期持有窗口的推荐数。</p>
  </el-card>
  <el-card class="panel-card">
    <span class="review-label">成熟样本命中率</span>
    <strong class="review-value">{{ maturedHitRate === null ? '暂无' : `${maturedHitRate.toFixed(1)}%` }}</strong>
    <p>只统计已成熟样本，避免把跟踪中样本误解为正式结论。</p>
  </el-card>
  <el-card class="panel-card">
    <span class="review-label">跟踪中样本</span>
    <strong class="review-value">{{ trackingRows.length }}</strong>
    <p>这些样本仍在运行中，当前收益只适合作为观察快照。</p>
  </el-card>
</section>

<p class="trust-copy">{{ item.confidence_notice }}</p>
<div class="driver-block">
  <div class="driver-head">
    <span class="driver-title">最强证据</span>
    <el-tag size="small" effect="plain">{{ item.data_mode === 'live' ? '真实快照' : '示例快照' }}</el-tag>
  </div>
  <ul class="copy-list">
    <li v-for="signal in item.strongest_signals" :key="signal.dimension">
      {{ signal.dimension }} {{ signal.score }} 分，{{ signal.takeaway }}
    </li>
  </ul>
  <p class="risk-copy">主要风险：{{ item.primary_risk }}</p>
</div>
```

```vue
<!-- frontend/src/views/ReviewView.vue -->
<el-alert
  v-if="review"
  :title="review.trust_level === 'high' ? '当前复盘可信度较高' : review.trust_level === 'medium' ? '当前复盘可信度中等' : '当前复盘可信度偏低'"
  :type="review.trust_level === 'high' ? 'success' : review.trust_level === 'medium' ? 'warning' : 'info'"
  :closable="false"
>
  <template #default>
    <ul class="copy-list">
      <li v-for="reason in review.trust_reasons" :key="reason">{{ reason }}</li>
    </ul>
  </template>
</el-alert>

<div class="window-list">
  <div
    v-for="item in review?.maturity_breakdown ?? []"
    :key="`maturity-${item.window_days}`"
    class="window-item"
  >
    <strong>{{ item.window_days }} 日成熟度</strong>
    <p>总样本：{{ item.total_samples }}</p>
    <p>已成熟：{{ item.matured_samples }}</p>
    <p>跟踪中：{{ item.immature_samples }}</p>
  </div>
</div>
```

```vue
<!-- frontend/src/views/StockDetailView.vue -->
<el-card v-if="detail.recommendation_trust" class="panel-card">
  <template #header>
    <div class="card-head">
      <span>可信度说明</span>
      <span class="hint">推荐页与详情页使用同一套口径</span>
    </div>
  </template>
  <div class="diagnosis-block">
    <div class="move-summary">
      <el-tag :type="detail.recommendation_trust.data_mode === 'live' ? 'success' : 'warning'" effect="dark">
        {{ detail.recommendation_trust.data_mode === 'live' ? '真实快照' : '示例快照' }}
      </el-tag>
      <p>{{ detail.recommendation_trust.confidence_notice }}</p>
    </div>
    <div class="diagnosis-meta">
      <div class="fundamental-item">
        <span>可信度分</span>
        <strong>{{ detail.recommendation_trust.confidence_score }}</strong>
      </div>
      <div class="fundamental-item">
        <span>快照时间</span>
        <strong>{{ detail.recommendation_trust.snapshot_updated_at }}</strong>
      </div>
    </div>
    <ul class="copy-list">
      <li v-for="signal in detail.recommendation_trust.strongest_signals" :key="signal.dimension">
        {{ signal.dimension }} {{ signal.score }} 分，{{ signal.takeaway }}
      </li>
    </ul>
    <p class="risk-copy">主要风险：{{ detail.recommendation_trust.primary_risk }}</p>
  </div>
</el-card>
```

- [ ] **Step 4: Update the beginner guide to explain trust interpretation**

```md
## 怎么判断“现在能不能信”

- 推荐页上的“运行中跟踪快照”只反映当前日志状态，不等于正式复盘结论。
- `真实快照` 表示当前推荐来自真实同步数据；`示例快照` 只适合做流程演示。
- 复盘页会额外告诉你 `trust_level` 和每个窗口的成熟样本数。
- 如果 20 日窗口成熟样本还不够，优先把结果当作方向参考，而不是稳定优势证明。
```

- [ ] **Step 5: Run focused assertions and the frontend build**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_api.py::test_recommendation_view_mentions_tracking_snapshot_copy backend/tests/test_api.py::test_review_view_mentions_trust_level_and_maturity_breakdown backend/tests/test_api.py::test_stock_detail_view_mentions_recommendation_trust_summary -v && cd frontend && npm run build`

Expected:
- the three source-level assertions `PASS`
- `npm run build` finishes successfully

- [ ] **Step 6: Commit the frontend trust UX**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add frontend/src/types/market.ts frontend/src/views/RecommendationView.vue frontend/src/views/ReviewView.vue frontend/src/views/StockDetailView.vue docs/BEGINNER_GUIDE.md backend/tests/test_api.py
git commit -m "feat: surface recommendation trust across views"
```

## Task 5: Final Regression And Handoff

**Files:**
- Modify: none expected
- Test: full backend suite and frontend build

- [ ] **Step 1: Run the full backend test suite**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests -q`

Expected: all backend tests `PASS`

- [ ] **Step 2: Re-run the frontend production build**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend && npm run build`

Expected: build completes successfully without TypeScript errors

- [ ] **Step 3: Inspect the final diff before handoff**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && git status --short`

Expected: only the intended trustworthiness files are modified; no unrelated files are reverted or staged by accident.

- [ ] **Step 4: Summarize verification evidence in the handoff**

```text
Backend verification:
- .venv/bin/python -m pytest backend/tests -q

Frontend verification:
- cd frontend && npm run build

Key user-visible changes:
- recommendation cards now explain data mode, strongest evidence, and primary risk
- recommendation journal distinguishes tracking vs matured samples
- review page exposes trust level and per-window maturity
- stock detail shows the same trust summary contract as the list page
```
