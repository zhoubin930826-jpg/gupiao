import http from '@/api/http'
import type {
  AlertItem,
  AlertOverview,
  DashboardSummary,
  HealthStatus,
  PortfolioOverview,
  PortfolioPositionCreateRequest,
  PortfolioPositionItem,
  PortfolioPositionUpdateRequest,
  PortfolioProfileConfig,
  RecommendationItem,
  RecommendationJournalItem,
  RecommendationReviewResponse,
  StockDetail,
  StockListResponse,
  StrategyConfig,
  SyncTask,
  TradePlanCreateRequest,
  TradePlanItem,
  TradePlanUpdateRequest,
  WatchlistCreateRequest,
  WatchlistItem,
  WatchlistUpdateRequest,
} from '@/types/market'

export function getHealthStatus() {
  return http.get<HealthStatus>('/health').then((response) => response.data)
}

export function getAlertOverview(params?: {
  status?: string
  severity?: string
  category?: string
  limit?: number
}) {
  return http
    .get<AlertOverview>('/alerts/overview', { params })
    .then((response) => response.data)
}

export function evaluateAlerts() {
  return http
    .post<AlertOverview>('/alerts/evaluate')
    .then((response) => response.data)
}

export function updateAlertItem(alertId: number, payload: { status: string }) {
  return http
    .put<AlertItem>(`/alerts/${alertId}`, payload)
    .then((response) => response.data)
}

export function getDashboardSummary() {
  return http
    .get<DashboardSummary>('/dashboard/summary')
    .then((response) => response.data)
}

export function listStocks(params: {
  keyword?: string
  board?: string
  page?: number
  page_size?: number
}) {
  return http
    .get<StockListResponse>('/stocks', { params })
    .then((response) => response.data)
}

export function getStockDetail(symbol: string) {
  return http.get<StockDetail>(`/stocks/${symbol}`).then((response) => response.data)
}

export function getRecommendations() {
  return http
    .get<RecommendationItem[]>('/recommendations')
    .then((response) => response.data)
}

export function getRecommendationJournal() {
  return http
    .get<RecommendationJournalItem[]>('/recommendations/journal')
    .then((response) => response.data)
}

export function getRecommendationReview() {
  return http
    .get<RecommendationReviewResponse>('/recommendations/review')
    .then((response) => response.data)
}

export function getStrategyConfig() {
  return http
    .get<StrategyConfig>('/strategies/default')
    .then((response) => response.data)
}

export function updateStrategyConfig(payload: StrategyConfig) {
  return http
    .put<StrategyConfig>('/strategies/default', payload)
    .then((response) => response.data)
}

export function listTasks() {
  return http.get<SyncTask[]>('/tasks').then((response) => response.data)
}

export function triggerMarketSync() {
  return http
    .post<SyncTask>('/tasks/sync-market', undefined, { timeout: 30000 })
    .then((response) => response.data)
}

export function getWatchlist(params?: { status?: string }) {
  return http
    .get<WatchlistItem[]>('/watchlist', { params })
    .then((response) => response.data)
}

export function addToWatchlist(payload: WatchlistCreateRequest) {
  return http
    .post<WatchlistItem>('/watchlist', payload)
    .then((response) => response.data)
}

export function updateWatchlistItem(symbol: string, payload: WatchlistUpdateRequest) {
  return http
    .put<WatchlistItem>(`/watchlist/${symbol}`, payload)
    .then((response) => response.data)
}

export function removeFromWatchlist(symbol: string) {
  return http.delete(`/watchlist/${symbol}`).then((response) => response.data)
}

export function getTradePlans(params?: { status?: string }) {
  return http
    .get<TradePlanItem[]>('/trade-plans', { params })
    .then((response) => response.data)
}

export function createTradePlan(payload: TradePlanCreateRequest) {
  return http
    .post<TradePlanItem>('/trade-plans', payload)
    .then((response) => response.data)
}

export function updateTradePlanItem(planId: number, payload: TradePlanUpdateRequest) {
  return http
    .put<TradePlanItem>(`/trade-plans/${planId}`, payload)
    .then((response) => response.data)
}

export function removeTradePlan(planId: number) {
  return http.delete(`/trade-plans/${planId}`).then((response) => response.data)
}

export function getPortfolioOverview(params?: { status?: string }) {
  return http
    .get<PortfolioOverview>('/portfolio/overview', { params })
    .then((response) => response.data)
}

export function getPortfolioProfile() {
  return http
    .get<PortfolioProfileConfig>('/portfolio/profile')
    .then((response) => response.data)
}

export function updatePortfolioProfile(payload: PortfolioProfileConfig) {
  return http
    .put<PortfolioProfileConfig>('/portfolio/profile', payload)
    .then((response) => response.data)
}

export function createPortfolioPosition(payload: PortfolioPositionCreateRequest) {
  return http
    .post<PortfolioPositionItem>('/portfolio/positions', payload)
    .then((response) => response.data)
}

export function updatePortfolioPosition(
  positionId: number,
  payload: PortfolioPositionUpdateRequest,
) {
  return http
    .put<PortfolioPositionItem>(`/portfolio/positions/${positionId}`, payload)
    .then((response) => response.data)
}

export function removePortfolioPosition(positionId: number) {
  return http.delete(`/portfolio/positions/${positionId}`).then((response) => response.data)
}
