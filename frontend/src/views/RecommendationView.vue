<script setup lang="ts">
import { Star } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  addToWatchlist,
  getRecommendationJournal,
  getRecommendations,
  removeFromWatchlist,
} from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import type { EventTone, MoveBias, RecommendationItem, RecommendationJournalItem } from '@/types/market'

const router = useRouter()
const loading = ref(false)
const togglingSymbol = ref<string | null>(null)
const rows = ref<RecommendationItem[]>([])
const journal = ref<RecommendationJournalItem[]>([])
const hasLiveJournal = computed(() => journal.value.some((item) => item.data_mode === 'live'))
const hasDemoJournal = computed(() => journal.value.some((item) => item.data_mode === 'demo'))
const journalStatsMode = computed<'demo' | 'live' | null>(() => {
  if (!journal.value.length) {
    return null
  }
  return hasLiveJournal.value ? 'live' : 'demo'
})
const journalStatsRows = computed(() =>
  journalStatsMode.value === null
    ? []
    : journal.value.filter((item) => item.data_mode === journalStatsMode.value),
)
const maturedRows = computed(() =>
  journalStatsRows.value.filter((item) => item.is_matured_for_expected_window),
)
const trackingRows = computed(() =>
  journalStatsRows.value.filter((item) => !item.is_matured_for_expected_window),
)
const journalTrustAlert = computed(() => {
  if (!journal.value.length || !hasDemoJournal.value) {
    return null
  }
  if (hasLiveJournal.value) {
    return {
      title: '当前统计仅基于真实记录',
      type: 'success' as const,
      message: '这些示例记录只用于流程演示，不计入上方三项统计。',
    }
  }
  return {
    title: '当前推荐记录来自示例数据',
    type: 'warning' as const,
    message: '这些记录适合验证流程和页面，不适合直接判断策略有没有真实优势。',
  }
})

const trackingSnapshotStats = computed(() => {
  const maturedWithReturn = maturedRows.value.filter((item) => item.current_return !== null)
  const maturedHitRate = maturedWithReturn.length
    ? (maturedWithReturn.filter((item) => (item.current_return ?? 0) > 0).length / maturedWithReturn.length) * 100
    : null
  const maturedAverageReturn = maturedWithReturn.length
    ? maturedWithReturn.reduce((sum, item) => sum + (item.current_return ?? 0), 0) / maturedWithReturn.length
    : null
  const bestTrade = maturedWithReturn.length
    ? Math.max(...maturedWithReturn.map((item) => item.current_return ?? 0))
    : null
  return {
    maturedHitRate,
    maturedAverageReturn,
    bestTrade,
  }
})

async function loadRecommendations() {
  loading.value = true
  try {
    const [recommendations, journalRows] = await Promise.all([
      getRecommendations(),
      getRecommendationJournal(),
    ])
    rows.value = recommendations
    journal.value = journalRows
  } finally {
    loading.value = false
  }
}

function openDetail(symbol: string) {
  void router.push(`/stocks/${symbol}`)
}

function openTradePlan(item: RecommendationItem) {
  void router.push({
    path: '/trade-plans',
    query: {
      symbol: item.symbol,
      source: 'recommendation',
      thesis: item.thesis,
      entry: item.latest_price ?? undefined,
      status: 'planned',
    },
  })
}

async function toggleWatchlist(item: RecommendationItem) {
  togglingSymbol.value = item.symbol
  try {
    if (item.in_watchlist) {
      await removeFromWatchlist(item.symbol)
      item.in_watchlist = false
      ElMessage.success('已移出自选池。')
      return
    }

    await addToWatchlist({
      symbol: item.symbol,
      source: 'recommendation',
    })
    item.in_watchlist = true
    ElMessage.success('已加入自选池。')
  } finally {
    togglingSymbol.value = null
  }
}

function formatPercent(value: number | null) {
  if (value === null) {
    return '暂无'
  }
  return `${value.toFixed(2)}%`
}

function moveBiasLabel(value: MoveBias | null) {
  if (value === 'bullish') {
    return '偏多'
  }
  if (value === 'cautious') {
    return '偏谨慎'
  }
  return '待确认'
}

function moveBiasType(value: MoveBias | null) {
  if (value === 'bullish') {
    return 'success'
  }
  if (value === 'cautious') {
    return 'danger'
  }
  return 'warning'
}

function eventToneLabel(value: EventTone | null) {
  if (value === 'positive') {
    return '催化偏正面'
  }
  if (value === 'caution') {
    return '催化偏谨慎'
  }
  return '催化中性'
}

function eventToneType(value: EventTone | null) {
  if (value === 'positive') {
    return 'success'
  }
  if (value === 'caution') {
    return 'danger'
  }
  return 'info'
}

onMounted(() => {
  void loadRecommendations()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="把原始评分翻译成可以落地的推荐清单"
      description="推荐中心更像一个候选池，不是直接替你下单。这里会把高分股票整理成带理由、带持有预期、带风险提示的结果，方便你每天复盘和跟踪。"
    >
      <template #actions>
        <el-button plain @click="loadRecommendations">刷新推荐</el-button>
      </template>
    </PageHeader>

    <el-alert
      v-if="journalTrustAlert"
      :title="journalTrustAlert.title"
      :type="journalTrustAlert.type"
      :closable="false"
    >
      <template #default>
        {{ journalTrustAlert.message }}
      </template>
    </el-alert>

    <el-alert title="运行中跟踪快照" type="info" :closable="false">
      <template #default>
        顶部卡片只反映当前推荐日志的跟踪状态，不替代复盘页的正式验证结论。
      </template>
    </el-alert>

    <section class="review-grid">
      <el-card class="panel-card">
        <span class="review-label">已成熟样本</span>
        <strong class="review-value">
          {{ maturedRows.length }}
        </strong>
        <p>已经走完预期持有窗口的推荐数。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">成熟样本命中率</span>
        <strong class="review-value">
          {{
            trackingSnapshotStats.maturedHitRate === null
              ? '暂无'
              : `${trackingSnapshotStats.maturedHitRate.toFixed(1)}%`
          }}
        </strong>
        <p>只统计已成熟样本，避免把跟踪中样本误解为正式结论。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">跟踪中样本</span>
        <strong class="review-value">
          {{ trackingRows.length }}
        </strong>
        <p>这些样本仍在运行中，当前收益只适合作为观察快照。</p>
      </el-card>
    </section>

    <div class="section-grid recommendation-grid" v-loading="loading">
      <el-card
        v-for="item in rows"
        :key="item.symbol"
        class="recommend-card"
        @click="openDetail(item.symbol)"
      >
        <div class="card-top">
          <div>
            <p class="symbol">{{ item.symbol }}</p>
            <h3>{{ item.name }}</h3>
          </div>
          <div class="top-actions">
            <el-button
              circle
              :icon="Star"
              :type="item.in_watchlist ? 'warning' : 'default'"
              :loading="togglingSymbol === item.symbol"
              @click.stop="toggleWatchlist(item)"
            />
            <div class="score-pill">{{ item.score }}</div>
          </div>
        </div>

        <p class="thesis">{{ item.thesis }}</p>

        <div class="driver-block">
          <div class="driver-head">
            <span class="driver-title">最强证据</span>
            <el-tag size="small" effect="plain">
              {{ item.data_mode === 'live' ? '真实快照' : '示例快照' }}
            </el-tag>
          </div>
          <ul class="copy-list">
            <li v-for="signal in item.strongest_signals" :key="`${item.symbol}-${signal.dimension}`">
              {{ signal.dimension }} {{ signal.score }} 分，{{ signal.takeaway }}
            </li>
          </ul>
          <p class="trust-copy">{{ item.confidence_notice }}</p>
        </div>

        <div v-if="item.move_summary" class="driver-block">
          <div class="driver-head">
            <span class="driver-title">涨跌归因</span>
            <el-tag
              v-if="item.move_bias"
              size="small"
              effect="dark"
              :type="moveBiasType(item.move_bias)"
            >
              {{ moveBiasLabel(item.move_bias) }}
            </el-tag>
          </div>
          <p>{{ item.move_summary }}</p>
        </div>

        <div v-if="item.event_summary && item.event_tone !== 'neutral'" class="driver-block event-block">
          <div class="driver-head">
            <span class="driver-title">事件层</span>
            <el-tag
              v-if="item.event_tone"
              size="small"
              effect="dark"
              :type="eventToneType(item.event_tone)"
            >
              {{ eventToneLabel(item.event_tone) }}
            </el-tag>
          </div>
          <p>{{ item.event_summary }}</p>
        </div>

        <div class="meta-grid">
          <div>
            <span>关注窗口</span>
            <strong>{{ item.entry_window }}</strong>
          </div>
          <div>
            <span>预计持有</span>
            <strong>{{ item.expected_holding_days }} 天</strong>
          </div>
          <div>
            <span>最新价格</span>
            <strong>{{ item.latest_price?.toFixed(2) ?? '暂无' }}</strong>
          </div>
          <div>
            <span>近 5 日</span>
            <strong :class="item.recent_return_5d !== null && item.recent_return_5d >= 0 ? 'stat-positive' : 'stat-negative'">
              {{ formatPercent(item.recent_return_5d) }}
            </strong>
          </div>
          <div>
            <span>近 20 日</span>
            <strong :class="item.recent_return_20d !== null && item.recent_return_20d >= 0 ? 'stat-positive' : 'stat-negative'">
              {{ formatPercent(item.recent_return_20d) }}
            </strong>
          </div>
        </div>

        <div class="tag-row">
          <el-tag v-for="tag in item.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
        </div>

        <div class="risk-block">
          <span>风险提醒</span>
          <p>{{ item.primary_risk }}</p>
        </div>

        <div class="card-actions">
          <el-button type="primary" plain @click.stop="openTradePlan(item)">加入计划</el-button>
        </div>
      </el-card>
    </div>

    <el-card class="table-card">
      <template #header>
        <div class="table-head">
          <span>最近推荐记录</span>
          <span class="table-hint">用来追踪系统过去推了什么、现在表现怎样</span>
        </div>
      </template>
      <el-table :data="journal" empty-text="还没有推荐记录">
        <el-table-column prop="generated_at" label="生成时间" width="180" />
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="score" label="评分" width="90" />
        <el-table-column label="发布价" width="100">
          <template #default="{ row }">
            {{ row.price_at_publish.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="当前价" width="100">
          <template #default="{ row }">
            {{ row.current_price?.toFixed(2) ?? '暂无' }}
          </template>
        </el-table-column>
        <el-table-column label="当前收益" width="110">
          <template #default="{ row }">
            <span :class="row.current_return !== null && row.current_return >= 0 ? 'stat-positive' : 'stat-negative'">
              {{ formatPercent(row.current_return) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="跟踪状态" width="120">
          <template #default="{ row }">
            {{ row.is_matured_for_expected_window ? '已成熟' : '跟踪中' }}
          </template>
        </el-table-column>
        <el-table-column prop="entry_window" label="关注窗口" width="160" />
        <el-table-column prop="thesis" label="推荐理由" min-width="260" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.review-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.review-label {
  display: block;
  color: var(--text-faint);
  margin-bottom: 10px;
}

.review-value {
  display: block;
  font-size: 34px;
  color: var(--text);
  font-family: var(--font-heading);
}

.review-grid p {
  margin: 12px 0 0;
  color: var(--text-soft);
  line-height: 1.65;
}

.recommendation-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.recommend-card {
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.recommend-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 38px rgba(24, 42, 62, 0.1);
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.symbol {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--text-faint);
}

h3 {
  margin: 0;
}

.score-pill {
  min-width: 58px;
  padding: 10px 0;
  border-radius: 18px;
  text-align: center;
  font-size: 24px;
  font-family: var(--font-heading);
  color: var(--accent);
  background: rgba(15, 118, 110, 0.1);
}

.thesis {
  margin: 18px 0;
  line-height: 1.7;
  color: var(--text-soft);
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.meta-grid span,
.risk-block span,
.driver-title {
  display: block;
  color: var(--text-faint);
  margin-bottom: 4px;
}

.meta-grid strong {
  color: var(--text);
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 18px 0;
}

.risk-block {
  padding: 14px;
  border-radius: 16px;
  background: rgba(234, 88, 12, 0.08);
}

.driver-block {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  margin-bottom: 16px;
  background: rgba(15, 118, 110, 0.08);
}

.event-block {
  background: rgba(180, 83, 9, 0.08);
}

.driver-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.driver-block p {
  margin: 0;
  color: var(--text-soft);
  line-height: 1.65;
}

.copy-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  color: var(--text-soft);
  line-height: 1.65;
}

.trust-copy {
  color: var(--text-soft);
}

.risk-block p {
  margin: 0;
  color: #9a3412;
  line-height: 1.65;
}

.card-actions {
  margin-top: 16px;
}

.table-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.table-hint {
  color: var(--text-faint);
  font-size: 13px;
}

@media (max-width: 960px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
