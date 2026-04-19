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
  market_context: MarketContextSummary
  benchmark_indices: BenchmarkIndex[]
  breadth_snapshot: MarketBreadthSnapshot
  market_capital_flow: MarketCapitalFlowOverview
  market_overview: MetricCard[]
  hot_industries: IndustryHeat[]
  market_pulse: MarketPulsePoint[]
  top_recommendations: RecommendationItem[]
  risk_flags: string[]
}

export interface MarketContextSummary {
  regime: 'risk_on' | 'balanced' | 'risk_off'
  regime_label: string
  summary: string
  action_hint: string
  watch_points: string[]
  metrics: MetricCard[]
}

export interface BenchmarkIndex {
  code: string
  name: string
  latest_price: number
  change_pct: number
  return_20d: number | null
  trend: string
  takeaway: string
}

export interface MarketBreadthSnapshot {
  scope_label: string
  total_count: number
  advancers: number
  decliners: number
  advance_ratio: number
  strong_count: number
  strong_ratio: number
  avg_change: number
  avg_turnover: number
  top_industry: string | null
  top_two_share: number
  limit_up_like: number | null
  limit_down_like: number | null
  summary: string
}

export interface MarketCapitalFlowOverview {
  status: 'ready' | 'derived' | 'placeholder'
  scope_label: string
  summary: string
  watch_points: string[]
  metrics: MetricCard[]
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

export type MoveBias = 'bullish' | 'mixed' | 'cautious'

export interface MoveDriver {
  title: string
  detail: string
  strength: number
  tone: 'positive' | 'negative'
}

export interface MoveAnalysis {
  bias: MoveBias
  summary: string
  positive_drivers: MoveDriver[]
  negative_drivers: MoveDriver[]
  watch_points: string[]
}

export type EventTone = 'positive' | 'neutral' | 'caution'

export interface EventItem {
  date: string | null
  category: string
  title: string
  headline: string
  detail: string
  tone: EventTone
  source: string
  url: string | null
}

export interface EventAnalysis {
  tone: EventTone
  summary: string
  tags: string[]
  items: EventItem[]
  watch_points: string[]
}

export type CapitalFlowTone = 'positive' | 'neutral' | 'caution'

export interface CapitalFlowAnalysis {
  status: 'ready' | 'derived' | 'placeholder'
  tone: CapitalFlowTone
  summary: string
  latest_trade_date: string | null
  main_net_inflow_1d: number | null
  main_net_ratio_1d: number | null
  main_net_inflow_5d: number | null
  active_days_5d: number | null
  ultra_large_net_inflow_1d: number | null
  lhb_on_list_count: number | null
  lhb_recent_date: string | null
  lhb_net_buy_amount: number | null
  watch_points: string[]
}

export interface RecommendationDiagnosis {
  is_recommended: boolean
  current_rank: number
  total_candidates: number
  recommendation_limit: number
  gap_to_limit: number
  score_gap_to_cutoff: number | null
  cutoff_symbol: string | null
  cutoff_name: string | null
  cutoff_score: number | null
  summary: string
  reason_points: string[]
  blocking_points: string[]
  action_points: string[]
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
  move_analysis: MoveAnalysis | null
  event_analysis: EventAnalysis | null
  capital_flow_analysis: CapitalFlowAnalysis | null
  recommendation_diagnosis: RecommendationDiagnosis | null
  recommendation_trust: RecommendationTrustSummary | null
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
  data_mode: 'demo' | 'live'
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

export interface RecommendationModeBreakdown {
  mode: 'demo' | 'live'
  sample_size: number
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

export interface DataSourceStatusItem {
  provider_key: string
  display_name: string
  enabled: boolean
  priority: number
  supports_snapshot: boolean
  supports_history: boolean
  supports_fundamental: boolean
  last_status: 'idle' | 'success' | 'warning'
  last_message: string
  last_run_at: string | null
  last_success_at: string | null
  last_failure_at: string | null
  updated_at: string
}

export interface EventSyncOverview {
  status: 'idle' | 'partial' | 'placeholder' | 'ready'
  summary: string
  configured_sources: string[]
  detected_sources: string[]
  coverage_count: number
  total_symbols: number
  active_symbols: number
  total_items: number
  updated_at: string | null
}

export interface DataSourceOverview {
  current_provider: string
  fallback_chain: string[]
  items: DataSourceStatusItem[]
  event_sync: EventSyncOverview
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
export type PortfolioRiskLevel = 'low' | 'medium' | 'high'

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
  risk_level: PortfolioRiskLevel
  risk_flags: string[]
  stop_distance_pct: number | null
  target_distance_pct: number | null
  created_at: string
  opened_at: string | null
  closed_at: string | null
  updated_at: string
}

export interface PortfolioIndustryExposure {
  industry: string
  market_value: number
  weight_pct: number
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
  winning_count: number
  losing_count: number
  at_risk_position_count: number
  capital_at_risk: number
  capital_at_risk_pct: number
  top_industry: string | null
  top_industry_weight_pct: number | null
  worst_position_name: string | null
  worst_position_return_pct: number | null
  risk_level: PortfolioRiskLevel
  largest_weight_pct: number | null
}

export interface PortfolioOverview {
  profile: PortfolioProfileConfig
  summary: PortfolioSummary
  industry_exposure: PortfolioIndustryExposure[]
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
