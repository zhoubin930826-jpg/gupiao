<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAlertOverview, getDashboardSummary } from '@/api/market'
import MarketPulseChart from '@/components/charts/MarketPulseChart.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import type { AlertItem, AlertOverview, DashboardSummary } from '@/types/market'

const router = useRouter()
const loading = ref(false)
const summary = ref<DashboardSummary | null>(null)
const alertOverview = ref<AlertOverview | null>(null)
const activeAlerts = computed(() => alertOverview.value?.items ?? [])

async function loadSummary() {
  loading.value = true
  try {
    const [summaryPayload, alertPayload] = await Promise.all([
      getDashboardSummary(),
      getAlertOverview({ status: 'active', limit: 5 }),
    ])
    summary.value = summaryPayload
    alertOverview.value = alertPayload
  } finally {
    loading.value = false
  }
}

function severityLabel(severity: AlertItem['severity']) {
  if (severity === 'critical') {
    return '高优先级'
  }
  if (severity === 'warning') {
    return '待处理'
  }
  return '信息'
}

function severityType(severity: AlertItem['severity']) {
  if (severity === 'critical') {
    return 'danger'
  }
  if (severity === 'warning') {
    return 'warning'
  }
  return 'info'
}

function openAlertsPage() {
  void router.push('/alerts')
}

function openAlert(item: AlertItem) {
  if (item.symbol) {
    void router.push(`/stocks/${item.symbol}`)
    return
  }
  if (item.action_path) {
    void router.push(item.action_path)
  }
}

onMounted(() => {
  void loadSummary()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="从行情、因子到推荐结果，一眼看到当日研究节奏"
      description="这个页面先给你放市场脉搏、行业热度和系统产出的候选股票。后面我们把真实采集接进来时，这里会自然演进成每日开盘前和收盘后的主工作台。"
    >
      <template #actions>
        <el-button plain @click="loadSummary">刷新看板</el-button>
      </template>
    </PageHeader>

    <el-skeleton :loading="loading" animated :rows="10">
      <template #default>
        <template v-if="summary">
          <section class="hero glass-card">
            <div>
              <p class="hero-kicker">今日节奏</p>
              <h3>{{ summary.headline }}</h3>
              <p class="hero-copy">
                最近一次更新：{{ summary.updated_at }}。系统会结合技术、基本面、资金和情绪四条线索输出今日候选。
              </p>
            </div>
            <div class="risk-list">
              <span v-for="flag in summary.risk_flags" :key="flag">{{ flag }}</span>
            </div>
          </section>

          <section class="metric-grid">
            <MetricCard
              v-for="metric in summary.market_overview"
              :key="metric.label"
              :metric="metric"
            />
          </section>

          <section class="section-grid chart-grid">
            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>市场温度</span>
                  <span class="hint">20 个交易日节奏</span>
                </div>
              </template>
              <MarketPulseChart :points="summary.market_pulse" />
            </el-card>

            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>行业热度</span>
                  <span class="hint">评分越高越强</span>
                </div>
              </template>
              <div class="industry-list">
                <div
                  v-for="industry in summary.hot_industries"
                  :key="industry.industry"
                  class="industry-item"
                >
                  <div>
                    <strong>{{ industry.industry }}</strong>
                    <p>{{ industry.momentum }}</p>
                  </div>
                  <el-progress
                    :percentage="industry.score"
                    :stroke-width="12"
                    :show-text="false"
                  />
                </div>
              </div>
            </el-card>
          </section>

          <el-card class="panel-card">
            <template #header>
              <div class="card-head">
                <span>待处理提醒</span>
                <div class="alert-head-meta">
                  <span class="hint">
                    {{ alertOverview?.active_count ?? 0 }} 条待处理
                  </span>
                  <el-button link type="primary" @click="openAlertsPage">打开提醒中心</el-button>
                </div>
              </div>
            </template>
            <div v-if="activeAlerts.length" class="alert-list">
              <div v-for="item in activeAlerts" :key="item.id" class="alert-item">
                <div class="alert-copy">
                  <div class="alert-title-row">
                    <el-tag :type="severityType(item.severity)" effect="plain">
                      {{ severityLabel(item.severity) }}
                    </el-tag>
                    <strong>{{ item.title }}</strong>
                  </div>
                  <p>{{ item.message }}</p>
                </div>
                <el-button plain @click="openAlert(item)">查看</el-button>
              </div>
            </div>
            <el-empty v-else description="当前没有待处理提醒" />
          </el-card>

          <el-card class="table-card">
            <template #header>
              <div class="card-head">
                <span>今日高分候选</span>
                <span class="hint">适合作为人工复核池</span>
              </div>
            </template>
            <el-table :data="summary.top_recommendations">
              <el-table-column prop="symbol" label="代码" width="110" />
              <el-table-column prop="name" label="名称" width="120" />
              <el-table-column prop="score" label="评分" width="100" />
              <el-table-column prop="entry_window" label="关注窗口" width="160" />
              <el-table-column prop="expected_holding_days" label="持有天数" width="100" />
              <el-table-column prop="thesis" label="推荐理由" min-width="260" />
            </el-table>
          </el-card>
        </template>
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 28px;
}

.hero-kicker {
  margin: 0 0 8px;
  color: var(--accent);
}

.hero h3 {
  margin: 0;
  font-size: 34px;
  max-width: 640px;
}

.hero-copy {
  margin: 16px 0 0;
  line-height: 1.7;
  max-width: 680px;
  color: var(--text-soft);
}

.risk-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  max-width: 320px;
  align-content: flex-start;
}

.risk-list span {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(234, 88, 12, 0.1);
  color: #9a3412;
}

.metric-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.chart-grid {
  grid-template-columns: minmax(0, 1.8fr) minmax(300px, 1fr);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.hint {
  color: var(--text-faint);
  font-size: 13px;
}

.industry-list {
  display: grid;
  gap: 16px;
}

.industry-item {
  display: grid;
  gap: 10px;
}

.industry-item p {
  margin: 6px 0 0;
  color: var(--text-soft);
}

.alert-head-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.alert-list {
  display: grid;
  gap: 14px;
}

.alert-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 16px 0;
  border-top: 1px solid var(--border);
}

.alert-item:first-child {
  padding-top: 0;
  border-top: none;
}

.alert-copy {
  display: grid;
  gap: 8px;
}

.alert-title-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.alert-copy p {
  margin: 0;
  color: var(--text-soft);
  line-height: 1.65;
}

@media (max-width: 960px) {
  .hero {
    flex-direction: column;
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
