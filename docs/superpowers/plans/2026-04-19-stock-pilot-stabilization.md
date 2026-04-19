# Stock Pilot Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the highest-risk trust and stability problems so `Stock Pilot` can be used as a dependable daily research console.

**Architecture:** Keep the existing CN-only, local-first architecture intact. First fix the demo cold-start regression, then make demo/live trust state explicit in recommendation and review APIs, and finally remove network-dependent enrichment from stock detail reads so page loads stay deterministic.

**Tech Stack:** FastAPI, SQLAlchemy, DuckDB, pytest, Vue 3, TypeScript, Element Plus, Vite

---

## Scope And File Map

- Modify: `backend/app/services/recommendation_service.py`
  Purpose: fix the sample-seed cold-start crash and expose `data_mode` in serialized journal payloads.
- Modify: `backend/app/services/recommendation_review_service.py`
  Purpose: evaluate review results in a live-first / demo-fallback way and emit trust metadata.
- Modify: `backend/app/services/market_store.py`
  Purpose: stop `get_stock_detail()` from performing live capital-flow fetches during read requests.
- Modify: `backend/app/schemas/market.py`
  Purpose: add `data_mode`, `evaluation_mode`, `evaluation_notice`, and `mode_breakdown` response fields.
- Create: `backend/tests/test_recommendation_service.py`
  Purpose: regression coverage for first-run demo seeding.
- Modify: `backend/tests/test_api.py`
  Purpose: assert the new trust metadata appears in recommendation and review responses.
- Modify: `backend/tests/test_market_store.py`
  Purpose: verify stock detail reads do not trigger capital-flow network enrichment.
- Modify: `frontend/src/types/market.ts`
  Purpose: mirror new backend fields.
- Modify: `frontend/src/views/RecommendationView.vue`
  Purpose: show whether current journal/recommendation context is demo or live.
- Modify: `frontend/src/views/ReviewView.vue`
  Purpose: show review trust state and sample breakdown.
- Modify: `docs/BEGINNER_GUIDE.md`
  Purpose: explain the new demo/live signals so daily usage stays aligned with system trust level.

## Out Of Scope For This Plan

These are important, but they should be separate plans after this one lands:

- Benchmark-relative review metrics,手续费,滑点,策略版本对比
- Full multi-market threading instead of the current CN-first implementation
- Frontend bundle optimization beyond the existing route-level lazy loading

### Task 1: Fix Demo Cold-Start Seeding

**Files:**
- Create: `backend/tests/test_recommendation_service.py`
- Modify: `backend/app/services/recommendation_service.py`
- Test: `backend/tests/test_recommendation_service.py`

- [ ] **Step 1: Write the failing regression test**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.services.market_store import MarketDataStore
from app.services.recommendation_service import RecommendationService


def test_ensure_seed_bootstraps_sample_history_on_fresh_db(tmp_path) -> None:
    market_store = MarketDataStore(str(tmp_path / "market.duckdb"))
    market_store.initialize()

    engine = create_engine(f"sqlite:///{(tmp_path / 'business.db').as_posix()}")
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        RecommendationService.ensure_seed(session, market_store)
        rows = RecommendationService.list_journal(session, market_store, limit=8)
        assert rows
        assert all(row["source"] == "sample" for row in rows)
    finally:
        session.close()
```

- [ ] **Step 2: Run the regression to confirm the current failure**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_recommendation_service.py -v`

Expected: `FAIL` with `NameError: name 'DEFAULT_MARKET_SCOPE' is not defined`

- [ ] **Step 3: Write the minimal implementation**

```python
from app.core.market_scope import DEFAULT_MARKET_SCOPE, is_a_share_symbol


class RecommendationService:
    ...

    @staticmethod
    def _seed_sample_history(
        db: Session,
        market_store: MarketDataStore,
    ) -> None:
        market = DEFAULT_MARKET_SCOPE
        recommendations = market_store.get_recommendations(market=market)
        if not recommendations:
            return
```

Notes:
- Only fix the missing import and keep the current CN-only behavior explicit.
- Do not widen scope to multi-market in this task.

- [ ] **Step 4: Run the focused and full backend tests**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_recommendation_service.py backend/tests/test_api.py backend/tests/test_market_store.py -v`

Expected: all selected backend tests `PASS`

- [ ] **Step 5: Commit**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add backend/app/services/recommendation_service.py backend/tests/test_recommendation_service.py
git commit -m "fix: restore demo seed cold-start path"
```

### Task 2: Make Review Trust State Explicit

**Files:**
- Modify: `backend/app/services/recommendation_service.py`
- Modify: `backend/app/services/recommendation_review_service.py`
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/tests/test_api.py`
- Modify: `frontend/src/types/market.ts`
- Modify: `frontend/src/views/RecommendationView.vue`
- Modify: `frontend/src/views/ReviewView.vue`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Extend the backend schema with trust metadata**

```python
class RecommendationJournalItem(BaseModel):
    run_key: str
    generated_at: str
    symbol: str
    name: str
    score: int
    entry_window: str
    expected_holding_days: int
    thesis: str
    risk: str
    source: str
    data_mode: Literal["demo", "live"]
    tags: list[str]
    price_at_publish: float
    current_price: float | None = None
    current_return: float | None = None


class RecommendationModeBreakdown(BaseModel):
    mode: Literal["demo", "live"]
    sample_size: int


class RecommendationReviewResponse(BaseModel):
    total_samples: int
    evaluation_mode: Literal["demo", "live"]
    evaluation_notice: str
    mode_breakdown: list[RecommendationModeBreakdown]
    window_metrics: list[RecommendationReviewWindowMetric]
    recent_runs: list[RecommendationReviewRun]
    top_hits: list[RecommendationReviewSample]
    top_misses: list[RecommendationReviewSample]
    samples: list[RecommendationReviewSample]
```

- [ ] **Step 2: Add a failing API assertion for the new fields**

```python
def test_recommendation_journal_exposes_data_mode(client: TestClient) -> None:
    response = client.get("/api/recommendations/journal")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0
    assert payload[0]["data_mode"] in {"demo", "live"}


def test_recommendation_review_exposes_evaluation_scope(client: TestClient) -> None:
    response = client.get("/api/recommendations/review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_mode"] in {"demo", "live"}
    assert payload["evaluation_notice"]
    assert len(payload["mode_breakdown"]) >= 1
```

- [ ] **Step 3: Implement live-first / demo-fallback review serialization**

```python
def _data_mode(source: str) -> str:
    return "demo" if str(source).startswith("sample") else "live"


class RecommendationService:
    @staticmethod
    def list_journal(...):
        ...
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
                "data_mode": _data_mode(row.source),
                "tags": json.loads(row.tags_json),
                "price_at_publish": round(row.price_at_publish, 2),
                "current_price": round(current_price, 2) if current_price is not None else None,
                "current_return": current_return,
            }
        )
```

```python
class RecommendationReviewService:
    @classmethod
    def build_review(...):
        ...
        sample_rows = [cls._serialize_row(row, price_map.get(row.symbol, [])) for row in journal_rows]
        live_rows = [row for row in sample_rows if row["data_mode"] == "live"]
        demo_rows = [row for row in sample_rows if row["data_mode"] == "demo"]
        scoped_rows = live_rows or demo_rows
        evaluation_mode = "live" if live_rows else "demo"
        evaluation_notice = (
            "当前复盘统计基于真实同步样本。"
            if evaluation_mode == "live"
            else "当前复盘统计只基于示例样本，适合验证流程，不适合判断策略有效性。"
        )

        return {
            "total_samples": len(scoped_rows),
            "evaluation_mode": evaluation_mode,
            "evaluation_notice": evaluation_notice,
            "mode_breakdown": [
                {"mode": "live", "sample_size": len(live_rows)},
                {"mode": "demo", "sample_size": len(demo_rows)},
            ],
            "window_metrics": [cls._build_window_metric(scoped_rows, window) for window in WINDOWS],
            "recent_runs": cls._build_run_summaries(scoped_rows),
            "top_hits": top_hits,
            "top_misses": top_misses,
            "samples": scoped_rows,
        }

    @classmethod
    def _serialize_row(...):
        payload = {
            ...
            "source": row.source,
            "data_mode": "demo" if str(row.source).startswith("sample") else "live",
            ...
        }
```

- [ ] **Step 4: Mirror the new fields in the frontend and show them**

```ts
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
}

export interface RecommendationModeBreakdown {
  mode: 'demo' | 'live'
  sample_size: number
}

export interface RecommendationReviewResponse {
  total_samples: number
  evaluation_mode: 'demo' | 'live'
  evaluation_notice: string
  mode_breakdown: RecommendationModeBreakdown[]
  window_metrics: RecommendationReviewWindowMetric[]
  recent_runs: RecommendationReviewRun[]
  top_hits: RecommendationReviewSample[]
  top_misses: RecommendationReviewSample[]
  samples: RecommendationReviewSample[]
}
```

```vue
<el-alert
  v-if="journal.length && journal.every((item) => item.data_mode === 'demo')"
  title="当前推荐记录来自示例数据"
  type="warning"
  :closable="false"
>
  <template #default>
    这些记录适合验证流程和页面，不适合直接判断策略有没有真实优势。
  </template>
</el-alert>
```

```vue
<el-alert
  v-if="review"
  :title="review.evaluation_mode === 'live' ? '当前复盘基于真实样本' : '当前复盘基于示例样本'"
  :type="review.evaluation_mode === 'live' ? 'success' : 'warning'"
  :closable="false"
>
  <template #default>
    {{ review.evaluation_notice }}
  </template>
</el-alert>
```

- [ ] **Step 5: Run backend and frontend verification**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_api.py -v`

Expected: new API tests `PASS`

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend && npm run build`

Expected: build `PASS`

- [ ] **Step 6: Commit**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add backend/app/services/recommendation_service.py backend/app/services/recommendation_review_service.py backend/app/schemas/market.py backend/tests/test_api.py frontend/src/types/market.ts frontend/src/views/RecommendationView.vue frontend/src/views/ReviewView.vue
git commit -m "feat: surface recommendation trust state"
```

### Task 3: Remove Network Fetches From Stock Detail Reads

**Files:**
- Modify: `backend/app/services/market_store.py`
- Modify: `backend/tests/test_market_store.py`
- Modify: `frontend/src/views/StockDetailView.vue`
- Test: `backend/tests/test_market_store.py`

- [ ] **Step 1: Write the failing regression that blocks read-path enrichment**

```python
from app.services.market_store import MarketDataStore


def test_stock_detail_uses_cached_capital_flow_only(tmp_path, monkeypatch) -> None:
    store = MarketDataStore(str(tmp_path / "market.duckdb"))
    store.initialize()
    symbol = store.get_recommendations()[0]["symbol"]

    def _should_not_run(*args, **kwargs):
        raise AssertionError("capital flow enrichment should not run during detail reads")

    monkeypatch.setattr(
        "app.services.market_store.collect_cn_stock_capital_flow_analysis",
        _should_not_run,
    )

    detail = store.get_stock_detail(symbol)
    assert detail["capital_flow_analysis"] is not None
    assert detail["capital_flow_analysis"]["status"] in {"ready", "derived", "placeholder"}
```

- [ ] **Step 2: Run the regression to verify the current failure**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_market_store.py -v`

Expected: `FAIL` because `get_stock_detail()` still tries to enrich capital-flow data on demand

- [ ] **Step 3: Replace live read-time enrichment with cached-or-placeholder behavior**

```python
def _resolve_capital_flow_analysis(
    self,
    *,
    symbol: str,
    cached_payload: dict[str, object] | None,
) -> dict[str, object]:
    if isinstance(cached_payload, dict):
        return cached_payload

    lhb_row = self._lookup_lhb_row(symbol)
    return build_placeholder_stock_capital_flow_analysis(symbol=symbol, lhb_row=lhb_row)
```

Notes:
- Do not import `akshare` inside `get_stock_detail()`.
- The only acceptable outputs on read are: cached ready payload, cached derived payload, cached placeholder payload, or a fresh placeholder built locally.

- [ ] **Step 4: Clarify the UI copy so users know the capital-flow panel is cached**

```vue
<span class="hint">{{ capitalFlowHint(detail.capital_flow_analysis.status) }}，详情页不会临时联网补抓</span>
```

- [ ] **Step 5: Run the focused tests and frontend build**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && .venv/bin/python -m pytest backend/tests/test_market_store.py backend/tests/test_api.py -v`

Expected: all selected tests `PASS`

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend && npm run build`

Expected: build `PASS`

- [ ] **Step 6: Commit**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add backend/app/services/market_store.py backend/tests/test_market_store.py frontend/src/views/StockDetailView.vue
git commit -m "refactor: keep stock detail reads deterministic"
```

### Task 4: Update Daily-Use Documentation

**Files:**
- Modify: `docs/BEGINNER_GUIDE.md`
- Test: manual doc review

- [ ] **Step 1: Add the new trust rules to the guide**

```markdown
### 推荐和复盘先看什么

- 如果页面显示 `示例数据` 或 `demo`，优先把它当成流程验证，不要把命中率当成真实表现。
- 如果复盘页显示 `真实样本` 或 `live`，再把窗口收益当成有参考价值的结果。
- 个股详情里的资金面如果显示 `占位` 或 `derived`，说明当前看到的是同步缓存，不是页面临时联网抓到的新结果。
```

- [ ] **Step 2: Review the wording against the UI**

Run: `cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao && rg -n "demo|live|示例数据|真实样本|占位" docs/BEGINNER_GUIDE.md frontend/src/views`

Expected: guide wording matches the visible labels in the updated UI

- [ ] **Step 3: Commit**

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
git add docs/BEGINNER_GUIDE.md
git commit -m "docs: explain demo and live trust signals"
```

## Completion Checklist

- Demo first-run no longer crashes on a fresh local database.
- Recommendation journal rows expose `data_mode`.
- Review payload exposes `evaluation_mode`, `evaluation_notice`, and `mode_breakdown`.
- Review metrics prefer live samples when available and fall back to demo samples only when necessary.
- `get_stock_detail()` no longer performs live capital-flow enrichment during reads.
- Frontend clearly warns when recommendations or review data come from demo samples.
- Beginner guide explains how to interpret the new trust markers.

## Follow-Up Plan Seeds

Write separate plans for these once this stabilization plan is complete:

1. `stock-pilot-review-realism`
   Add benchmark-relative metrics,手续费,滑点,策略版本字段, and stricter review slicing.
2. `stock-pilot-market-scope-threading`
   Either fully thread `market` through tasks/data sources, or explicitly remove fake multi-market affordances.
3. `stock-pilot-frontend-performance`
   Add manual chunking, chart/package split strategy, and bundle-size checks in CI.
