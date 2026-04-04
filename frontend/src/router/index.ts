import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'

const DashboardView = () => import('@/views/DashboardView.vue')
const AlertCenterView = () => import('@/views/AlertCenterView.vue')
const StockListView = () => import('@/views/StockListView.vue')
const StockDetailView = () => import('@/views/StockDetailView.vue')
const RecommendationView = () => import('@/views/RecommendationView.vue')
const ReviewView = () => import('@/views/ReviewView.vue')
const TradePlanView = () => import('@/views/TradePlanView.vue')
const PortfolioView = () => import('@/views/PortfolioView.vue')
const WatchlistView = () => import('@/views/WatchlistView.vue')
const StrategyView = () => import('@/views/StrategyView.vue')
const TasksView = () => import('@/views/TasksView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppShell,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: DashboardView,
          meta: { title: '市场看板' },
        },
        {
          path: 'alerts',
          name: 'alerts',
          component: AlertCenterView,
          meta: { title: '提醒中心' },
        },
        {
          path: 'stocks',
          name: 'stocks',
          component: StockListView,
          meta: { title: '股票列表' },
        },
        {
          path: 'stocks/:symbol',
          name: 'stock-detail',
          component: StockDetailView,
          meta: { title: '个股详情' },
        },
        {
          path: 'recommendations',
          name: 'recommendations',
          component: RecommendationView,
          meta: { title: '推荐中心' },
        },
        {
          path: 'review',
          name: 'review',
          component: ReviewView,
          meta: { title: '推荐复盘' },
        },
        {
          path: 'trade-plans',
          name: 'trade-plans',
          component: TradePlanView,
          meta: { title: '交易计划' },
        },
        {
          path: 'portfolio',
          name: 'portfolio',
          component: PortfolioView,
          meta: { title: '组合持仓' },
        },
        {
          path: 'watchlist',
          name: 'watchlist',
          component: WatchlistView,
          meta: { title: '自选池' },
        },
        {
          path: 'strategy',
          name: 'strategy',
          component: StrategyView,
          meta: { title: '策略配置' },
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: TasksView,
          meta: { title: '数据任务' },
        },
      ],
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
