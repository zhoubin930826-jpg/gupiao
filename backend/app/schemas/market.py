from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WatchlistStatus = Literal["watching", "holding", "archived"]
TradePlanStatus = Literal["planned", "active", "closed", "cancelled"]
TradePlanSource = Literal["manual", "recommendation", "watchlist"]
PortfolioPositionStatus = Literal["holding", "closed"]
PortfolioPositionSource = Literal["manual", "trade_plan", "recommendation", "watchlist"]
AlertStatus = Literal["active", "handled", "resolved"]
AlertSeverity = Literal["critical", "warning", "info"]
AlertCategory = Literal["trade_plan", "portfolio", "watchlist"]


class HealthResponse(BaseModel):
    status: str
    app_name: str
    mode: str
    scheduler_enabled: bool
    market_db_path: str
    strategy_store: str


class MetricCard(BaseModel):
    label: str
    value: str
    change: str
    tone: Literal["positive", "negative", "neutral"]
    description: str


class IndustryHeat(BaseModel):
    industry: str
    score: int
    momentum: str


class MarketPulsePoint(BaseModel):
    date: str
    score: int
    turnover: float


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
    in_watchlist: bool = False


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
    tags: list[str]
    price_at_publish: float
    current_price: float | None = None
    current_return: float | None = None


class RecommendationReviewWindowMetric(BaseModel):
    window_days: int
    sample_size: int
    win_rate: float | None = None
    avg_return: float | None = None
    best_return: float | None = None
    worst_return: float | None = None


class RecommendationReviewRun(BaseModel):
    run_key: str
    generated_at: str
    source: str
    picks: int
    avg_score: float
    avg_return_5d: float | None = None
    avg_return_10d: float | None = None
    avg_return_20d: float | None = None
    avg_expected_return: float | None = None


class RecommendationReviewSample(BaseModel):
    run_key: str
    generated_at: str
    symbol: str
    name: str
    score: int
    source: str
    entry_window: str
    expected_holding_days: int
    thesis: str
    tags: list[str]
    price_at_publish: float
    latest_known_price: float | None = None
    return_5d: float | None = None
    return_10d: float | None = None
    return_20d: float | None = None
    expected_return: float | None = None


class RecommendationReviewResponse(BaseModel):
    total_samples: int
    window_metrics: list[RecommendationReviewWindowMetric]
    recent_runs: list[RecommendationReviewRun]
    top_hits: list[RecommendationReviewSample]
    top_misses: list[RecommendationReviewSample]
    samples: list[RecommendationReviewSample]


class DashboardSummary(BaseModel):
    headline: str
    updated_at: str
    market_overview: list[MetricCard]
    hot_industries: list[IndustryHeat]
    market_pulse: list[MarketPulsePoint]
    top_recommendations: list[RecommendationItem]
    risk_flags: list[str]


class StockItem(BaseModel):
    symbol: str
    name: str
    board: str
    industry: str
    latest_price: float
    change_pct: float
    turnover_ratio: float
    pe_ttm: float
    market_cap: float
    score: int
    thesis: str
    tags: list[str]
    in_watchlist: bool = False


class StockListResponse(BaseModel):
    total: int
    rows: list[StockItem]


class PricePoint(BaseModel):
    date: str
    open: float
    close: float
    low: float
    high: float
    volume: float
    ma5: float
    ma20: float


class SignalBreakdown(BaseModel):
    dimension: str
    score: int
    takeaway: str


class FundamentalSnapshot(BaseModel):
    report_period: str | None = None
    revenue_growth: float | None = None
    net_profit_growth: float | None = None
    deduct_profit_growth: float | None = None
    roe: float | None = None
    gross_margin: float | None = None
    debt_ratio: float | None = None
    eps: float | None = None
    operating_cashflow_per_share: float | None = None


class StockDetail(StockItem):
    price_series: list[PricePoint]
    thesis_points: list[str]
    risk_notes: list[str]
    signal_breakdown: list[SignalBreakdown]
    fundamental: FundamentalSnapshot | None = None


class StrategyConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    technical_weight: int
    fundamental_weight: int
    money_flow_weight: int
    sentiment_weight: int
    rebalance_cycle: Literal["daily", "weekly", "biweekly"]
    min_turnover: float
    min_listing_days: int
    exclude_st: bool
    exclude_new_shares: bool


class SyncTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_key: str
    name: str
    status: Literal["idle", "running", "success", "warning"]
    schedule: str
    last_run_at: str | None
    next_run_at: str | None
    message: str
    source: str


class WatchlistCreateRequest(BaseModel):
    symbol: str
    source: Literal["manual", "recommendation"] = "manual"
    status: WatchlistStatus = "watching"
    notes: str | None = None


class WatchlistUpdateRequest(BaseModel):
    status: WatchlistStatus | None = None
    notes: str | None = None


class WatchlistItem(BaseModel):
    symbol: str
    name: str
    board: str | None = None
    industry: str | None = None
    status: WatchlistStatus
    source: str
    notes: str | None = None
    added_price: float | None = None
    latest_price: float | None = None
    change_pct: float | None = None
    score: int | None = None
    thesis: str | None = None
    tags: list[str]
    current_return: float | None = None
    added_at: str
    updated_at: str


class TradePlanCreateRequest(BaseModel):
    symbol: str
    source: TradePlanSource = "manual"
    status: TradePlanStatus = "planned"
    thesis: str | None = None
    notes: str | None = None
    planned_entry_price: float | None = Field(default=None, ge=0)
    actual_entry_price: float | None = Field(default=None, ge=0)
    actual_exit_price: float | None = Field(default=None, ge=0)
    stop_loss_price: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    planned_position_pct: int | None = Field(default=None, ge=1, le=100)


class TradePlanUpdateRequest(BaseModel):
    status: TradePlanStatus | None = None
    thesis: str | None = None
    notes: str | None = None
    planned_entry_price: float | None = Field(default=None, ge=0)
    actual_entry_price: float | None = Field(default=None, ge=0)
    actual_exit_price: float | None = Field(default=None, ge=0)
    stop_loss_price: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    planned_position_pct: int | None = Field(default=None, ge=1, le=100)


class TradePlanItem(BaseModel):
    id: int
    symbol: str
    name: str
    board: str | None = None
    industry: str | None = None
    source: TradePlanSource
    status: TradePlanStatus
    thesis: str | None = None
    notes: str | None = None
    planned_entry_price: float | None = None
    actual_entry_price: float | None = None
    actual_exit_price: float | None = None
    stop_loss_price: float | None = None
    target_price: float | None = None
    planned_position_pct: int | None = None
    latest_price: float | None = None
    change_pct: float | None = None
    score: int | None = None
    tags: list[str]
    plan_gap_pct: float | None = None
    current_return: float | None = None
    realized_return: float | None = None
    risk_reward_ratio: float | None = None
    created_at: str
    opened_at: str | None = None
    closed_at: str | None = None
    updated_at: str


class PortfolioProfileConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    initial_capital: float = Field(ge=1000)
    benchmark: str
    notes: str | None = None


class PortfolioPositionCreateRequest(BaseModel):
    symbol: str
    source: PortfolioPositionSource = "manual"
    status: PortfolioPositionStatus = "holding"
    quantity: int = Field(ge=1)
    entry_price: float = Field(ge=0)
    exit_price: float | None = Field(default=None, ge=0)
    stop_loss_price: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    thesis: str | None = None
    notes: str | None = None


class PortfolioPositionUpdateRequest(BaseModel):
    status: PortfolioPositionStatus | None = None
    quantity: int | None = Field(default=None, ge=1)
    entry_price: float | None = Field(default=None, ge=0)
    exit_price: float | None = Field(default=None, ge=0)
    stop_loss_price: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    thesis: str | None = None
    notes: str | None = None


class PortfolioPositionItem(BaseModel):
    id: int
    symbol: str
    name: str
    board: str | None = None
    industry: str | None = None
    source: PortfolioPositionSource
    status: PortfolioPositionStatus
    quantity: int
    entry_price: float
    exit_price: float | None = None
    stop_loss_price: float | None = None
    target_price: float | None = None
    latest_price: float | None = None
    change_pct: float | None = None
    score: int | None = None
    tags: list[str]
    thesis: str | None = None
    notes: str | None = None
    cost_value: float
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_return: float | None = None
    realized_pnl: float | None = None
    realized_return: float | None = None
    weight_pct: float | None = None
    stop_distance_pct: float | None = None
    target_distance_pct: float | None = None
    created_at: str
    opened_at: str | None = None
    closed_at: str | None = None
    updated_at: str


class PortfolioSummary(BaseModel):
    initial_capital: float
    estimated_cash: float
    estimated_total_assets: float
    invested_cost: float
    market_value: float
    holding_count: int
    closed_count: int
    unrealized_pnl: float
    realized_pnl: float
    total_return_pct: float
    utilization_pct: float
    largest_weight_pct: float | None = None


class PortfolioOverview(BaseModel):
    profile: PortfolioProfileConfig
    summary: PortfolioSummary
    positions: list[PortfolioPositionItem]


class AlertStatusUpdateRequest(BaseModel):
    status: AlertStatus


class AlertItem(BaseModel):
    id: int
    event_key: str
    status: AlertStatus
    severity: AlertSeverity
    category: AlertCategory
    kind: str
    symbol: str | None = None
    name: str | None = None
    title: str
    message: str
    action_path: str | None = None
    source_type: str | None = None
    source_id: int | None = None
    last_value: float | None = None
    threshold_value: float | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: str
    last_seen_at: str
    resolved_at: str | None = None
    updated_at: str


class AlertOverview(BaseModel):
    total_count: int
    filtered_count: int
    active_count: int
    handled_count: int
    resolved_count: int
    critical_count: int
    warning_count: int
    info_count: int
    latest_evaluated_at: str | None = None
    items: list[AlertItem]
