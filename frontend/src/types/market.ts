export interface HealthStatus {
  status: string
  app_name: string
  mode: string
  scheduler_enabled: boolean
  market_db_path: string
  strategy_store: string
}

export interface MetricCard {
  label: string
  value: string
  change: string
  tone: 'positive' | 'negative' | 'neutral'
  description: string
}

export interface IndustryHeat {
  industry: string
  score: number
  momentum: string
}

export interface MarketPulsePoint {
  date: string
  score: number
  turnover: number
}

export interface DashboardSummary {
  headline: string
  updated_at: string
  market_overview: MetricCard[]
  hot_industries: IndustryHeat[]
  market_pulse: MarketPulsePoint[]
  top_recommendations: RecommendationItem[]
  risk_flags: string[]
}

export interface StockItem {
  symbol: string
  name: string
  board: string
  industry: string
  latest_price: number
  change_pct: number
  turnover_ratio: number
  pe_ttm: number
  market_cap: number
  score: number
  thesis: string
  tags: string[]
  in_watchlist: boolean
}

export interface StockListResponse {
  total: number
  rows: StockItem[]
}

export interface PricePoint {
  date: string
  open: number
  close: number
  low: number
  high: number
  volume: number
  ma5: number
  ma20: number
}

export interface SignalBreakdown {
  dimension: string
  score: number
  takeaway: string
}

export interface FundamentalSnapshot {
  report_period: string | null
  revenue_growth: number | null
  net_profit_growth: number | null
  deduct_profit_growth: number | null
  roe: number | null
  gross_margin: number | null
  debt_ratio: number | null
  eps: number | null
  operating_cashflow_per_share: number | null
}

export interface StockDetail extends StockItem {
  price_series: PricePoint[]
  thesis_points: string[]
  risk_notes: string[]
  signal_breakdown: SignalBreakdown[]
  fundamental: FundamentalSnapshot | null
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
  tags: string[]
  price_at_publish: number
  current_price: number | null
  current_return: number | null
}

export interface RecommendationReviewWindowMetric {
  window_days: number
  sample_size: number
  win_rate: number | null
  avg_return: number | null
  best_return: number | null
  worst_return: number | null
}

export interface RecommendationReviewRun {
  run_key: string
  generated_at: string
  source: string
  picks: number
  avg_score: number
  avg_return_5d: number | null
  avg_return_10d: number | null
  avg_return_20d: number | null
  avg_expected_return: number | null
}

export interface RecommendationReviewSample {
  run_key: string
  generated_at: string
  symbol: string
  name: string
  score: number
  source: string
  entry_window: string
  expected_holding_days: number
  thesis: string
  tags: string[]
  price_at_publish: number
  latest_known_price: number | null
  return_5d: number | null
  return_10d: number | null
  return_20d: number | null
  expected_return: number | null
}

export interface RecommendationReviewResponse {
  total_samples: number
  window_metrics: RecommendationReviewWindowMetric[]
  recent_runs: RecommendationReviewRun[]
  top_hits: RecommendationReviewSample[]
  top_misses: RecommendationReviewSample[]
  samples: RecommendationReviewSample[]
}

export interface StrategyConfig {
  technical_weight: number
  fundamental_weight: number
  money_flow_weight: number
  sentiment_weight: number
  rebalance_cycle: 'daily' | 'weekly' | 'biweekly'
  min_turnover: number
  min_listing_days: number
  exclude_st: boolean
  exclude_new_shares: boolean
}

export interface SyncTask {
  task_key: string
  name: string
  status: 'idle' | 'running' | 'success' | 'warning'
  schedule: string
  last_run_at: string | null
  next_run_at: string | null
  message: string
  source: string
}

export type WatchlistStatus = 'watching' | 'holding' | 'archived'

export interface WatchlistCreateRequest {
  symbol: string
  source?: 'manual' | 'recommendation'
  status?: WatchlistStatus
  notes?: string | null
}

export interface WatchlistUpdateRequest {
  status?: WatchlistStatus
  notes?: string | null
}

export interface WatchlistItem {
  symbol: string
  name: string
  board: string | null
  industry: string | null
  status: WatchlistStatus
  source: string
  notes: string | null
  added_price: number | null
  latest_price: number | null
  change_pct: number | null
  score: number | null
  thesis: string | null
  tags: string[]
  current_return: number | null
  added_at: string
  updated_at: string
}

export type TradePlanStatus = 'planned' | 'active' | 'closed' | 'cancelled'
export type TradePlanSource = 'manual' | 'recommendation' | 'watchlist'

export interface TradePlanCreateRequest {
  symbol: string
  source?: TradePlanSource
  status?: TradePlanStatus
  thesis?: string | null
  notes?: string | null
  planned_entry_price?: number | null
  actual_entry_price?: number | null
  actual_exit_price?: number | null
  stop_loss_price?: number | null
  target_price?: number | null
  planned_position_pct?: number | null
}

export interface TradePlanUpdateRequest {
  status?: TradePlanStatus
  thesis?: string | null
  notes?: string | null
  planned_entry_price?: number | null
  actual_entry_price?: number | null
  actual_exit_price?: number | null
  stop_loss_price?: number | null
  target_price?: number | null
  planned_position_pct?: number | null
}

export interface TradePlanItem {
  id: number
  symbol: string
  name: string
  board: string | null
  industry: string | null
  source: TradePlanSource
  status: TradePlanStatus
  thesis: string | null
  notes: string | null
  planned_entry_price: number | null
  actual_entry_price: number | null
  actual_exit_price: number | null
  stop_loss_price: number | null
  target_price: number | null
  planned_position_pct: number | null
  latest_price: number | null
  change_pct: number | null
  score: number | null
  tags: string[]
  plan_gap_pct: number | null
  current_return: number | null
  realized_return: number | null
  risk_reward_ratio: number | null
  created_at: string
  opened_at: string | null
  closed_at: string | null
  updated_at: string
}

export type PortfolioPositionStatus = 'holding' | 'closed'
export type PortfolioPositionSource = 'manual' | 'trade_plan' | 'recommendation' | 'watchlist'

export interface PortfolioProfileConfig {
  name: string
  initial_capital: number
  benchmark: string
  notes: string | null
}

export interface PortfolioPositionCreateRequest {
  symbol: string
  source?: PortfolioPositionSource
  status?: PortfolioPositionStatus
  quantity: number
  entry_price: number
  exit_price?: number | null
  stop_loss_price?: number | null
  target_price?: number | null
  thesis?: string | null
  notes?: string | null
}

export interface PortfolioPositionUpdateRequest {
  status?: PortfolioPositionStatus
  quantity?: number | null
  entry_price?: number | null
  exit_price?: number | null
  stop_loss_price?: number | null
  target_price?: number | null
  thesis?: string | null
  notes?: string | null
}

export interface PortfolioPositionItem {
  id: number
  symbol: string
  name: string
  board: string | null
  industry: string | null
  source: PortfolioPositionSource
  status: PortfolioPositionStatus
  quantity: number
  entry_price: number
  exit_price: number | null
  stop_loss_price: number | null
  target_price: number | null
  latest_price: number | null
  change_pct: number | null
  score: number | null
  tags: string[]
  thesis: string | null
  notes: string | null
  cost_value: number
  market_value: number | null
  unrealized_pnl: number | null
  unrealized_return: number | null
  realized_pnl: number | null
  realized_return: number | null
  weight_pct: number | null
  stop_distance_pct: number | null
  target_distance_pct: number | null
  created_at: string
  opened_at: string | null
  closed_at: string | null
  updated_at: string
}

export interface PortfolioSummary {
  initial_capital: number
  estimated_cash: number
  estimated_total_assets: number
  invested_cost: number
  market_value: number
  holding_count: number
  closed_count: number
  unrealized_pnl: number
  realized_pnl: number
  total_return_pct: number
  utilization_pct: number
  largest_weight_pct: number | null
}

export interface PortfolioOverview {
  profile: PortfolioProfileConfig
  summary: PortfolioSummary
  positions: PortfolioPositionItem[]
}

export type AlertStatus = 'active' | 'handled' | 'resolved'
export type AlertSeverity = 'critical' | 'warning' | 'info'
export type AlertCategory = 'trade_plan' | 'portfolio' | 'watchlist'

export interface AlertItem {
  id: number
  event_key: string
  status: AlertStatus
  severity: AlertSeverity
  category: AlertCategory
  kind: string
  symbol: string | null
  name: string | null
  title: string
  message: string
  action_path: string | null
  source_type: string | null
  source_id: number | null
  last_value: number | null
  threshold_value: number | null
  payload: Record<string, unknown>
  created_at: string
  last_seen_at: string
  resolved_at: string | null
  updated_at: string
}

export interface AlertOverview {
  total_count: number
  filtered_count: number
  active_count: number
  handled_count: number
  resolved_count: number
  critical_count: number
  warning_count: number
  info_count: number
  latest_evaluated_at: string | null
  items: AlertItem[]
}
