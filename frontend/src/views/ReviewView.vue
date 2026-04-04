<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getRecommendationReview } from '@/api/market'
import RecommendationReviewChart from '@/components/charts/RecommendationReviewChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import type {
  RecommendationReviewResponse,
  RecommendationReviewSample,
} from '@/types/market'

const router = useRouter()
const loading = ref(false)
const review = ref<RecommendationReviewResponse | null>(null)

const metricMap = computed(() => {
  const buckets = new Map<number, RecommendationReviewResponse['window_metrics'][number]>()
  for (const item of review.value?.window_metrics ?? []) {
    buckets.set(item.window_days, item)
  }
  return buckets
})

const reviewCards = computed(() => [
  {
    label: '5 日命中率',
    value:
      metricMap.value.get(5)?.win_rate === null || metricMap.value.get(5)?.win_rate === undefined
        ? '暂无'
        : `${metricMap.value.get(5)?.win_rate?.toFixed(1)}%`,
    copy: '看推荐发出后 5 个交易日内，正收益样本占比。',
  },
  {
    label: '10 日平均收益',
    value:
      metricMap.value.get(10)?.avg_return === null || metricMap.value.get(10)?.avg_return === undefined
        ? '暂无'
        : `${metricMap.value.get(10)?.avg_return?.toFixed(2)}%`,
    copy: '帮助判断推荐在中短周期里的兑现力度。',
  },
  {
    label: '20 日命中率',
    value:
      metricMap.value.get(20)?.win_rate === null || metricMap.value.get(20)?.win_rate === undefined
        ? '暂无'
        : `${metricMap.value.get(20)?.win_rate?.toFixed(1)}%`,
    copy: '更接近你做波段跟踪时会关心的有效性。',
  },
  {
    label: '总样本数',
    value: `${review.value?.total_samples ?? 0}`,
    copy: '当前参与复盘计算的推荐样本数量。',
  },
])

const sampleRows = computed(() => review.value?.samples ?? [])
const topHits = computed(() => review.value?.top_hits ?? [])
const topMisses = computed(() => review.value?.top_misses ?? [])
const recentRuns = computed(() => review.value?.recent_runs ?? [])

async function loadReview() {
  loading.value = true
  try {
    review.value = await getRecommendationReview()
  } finally {
    loading.value = false
  }
}

function openDetail(symbol: string) {
  void router.push(`/stocks/${symbol}`)
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '暂无'
  }
  return `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '暂无'
  }
  return value.toFixed(2)
}

function cardToneClass(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return ''
  }
  return value >= 0 ? 'stat-positive' : 'stat-negative'
}

function rowClassName({ row }: { row: RecommendationReviewSample }) {
  if (row.expected_return === null) {
    return ''
  }
  return row.expected_return >= 0 ? 'row-positive' : 'row-negative'
}

onMounted(() => {
  void loadReview()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="不是只看系统推了什么，还要回头验证它推得怎么样"
      description="复盘页会把历史推荐样本拉出来，按 5 日、10 日、20 日和预期持有窗口看收益，帮助你判断这套规则是短线有效、中期有效，还是只在个别阶段碰巧有效。"
    >
      <template #actions>
        <el-button plain @click="loadReview">刷新复盘</el-button>
      </template>
    </PageHeader>

    <section class="review-grid">
      <el-card v-for="card in reviewCards" :key="card.label" class="panel-card">
        <span class="review-label">{{ card.label }}</span>
        <strong class="review-value">{{ card.value }}</strong>
        <p>{{ card.copy }}</p>
      </el-card>
    </section>

    <section class="section-grid review-layout" v-loading="loading">
      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>批次表现</span>
            <span class="hint">按推荐批次看评分和预期收益</span>
          </div>
        </template>
        <RecommendationReviewChart :runs="recentRuns" />
      </el-card>

      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>窗口统计</span>
            <span class="hint">看不同持有周期的稳定性</span>
          </div>
        </template>
        <div class="window-list">
          <div
            v-for="item in review?.window_metrics ?? []"
            :key="item.window_days"
            class="window-item"
          >
            <strong>{{ item.window_days }} 日窗口</strong>
            <p>样本数：{{ item.sample_size }}</p>
            <p>命中率：{{ item.win_rate === null ? '暂无' : `${item.win_rate.toFixed(1)}%` }}</p>
            <p>平均收益：<span :class="cardToneClass(item.avg_return)">{{ formatPercent(item.avg_return) }}</span></p>
            <p>最佳 / 最差：{{ formatPercent(item.best_return) }} / {{ formatPercent(item.worst_return) }}</p>
          </div>
        </div>
      </el-card>
    </section>

    <section class="section-grid review-layout">
      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>最佳样本</span>
            <span class="hint">按预期持有窗口收益排序</span>
          </div>
        </template>
        <div class="sample-list">
          <div
            v-for="item in topHits"
            :key="`${item.run_key}-${item.symbol}`"
            class="sample-item"
            @click="openDetail(item.symbol)"
          >
            <div class="sample-head">
              <strong>{{ item.name }}</strong>
              <span class="stat-positive">{{ formatPercent(item.expected_return) }}</span>
            </div>
            <p>{{ item.symbol }} · {{ item.generated_at.slice(0, 10) }}</p>
            <p>{{ item.thesis }}</p>
          </div>
        </div>
      </el-card>

      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>最差样本</span>
            <span class="hint">优先找规则的失真点</span>
          </div>
        </template>
        <div class="sample-list">
          <div
            v-for="item in topMisses"
            :key="`${item.run_key}-${item.symbol}`"
            class="sample-item"
            @click="openDetail(item.symbol)"
          >
            <div class="sample-head">
              <strong>{{ item.name }}</strong>
              <span class="stat-negative">{{ formatPercent(item.expected_return) }}</span>
            </div>
            <p>{{ item.symbol }} · {{ item.generated_at.slice(0, 10) }}</p>
            <p>{{ item.thesis }}</p>
          </div>
        </div>
      </el-card>
    </section>

    <el-card class="table-card">
      <template #header>
        <div class="card-head">
          <span>推荐样本明细</span>
          <span class="hint">逐条看发出后的收益表现</span>
        </div>
      </template>
      <el-table
        :data="sampleRows"
        empty-text="还没有足够的复盘样本"
        :row-class-name="rowClassName"
      >
        <el-table-column prop="generated_at" label="生成时间" width="180" />
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="score" label="评分" width="90" />
        <el-table-column label="发布价" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.price_at_publish) }}
          </template>
        </el-table-column>
        <el-table-column label="5 日收益" width="110">
          <template #default="{ row }">
            <span :class="cardToneClass(row.return_5d)">{{ formatPercent(row.return_5d) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="10 日收益" width="110">
          <template #default="{ row }">
            <span :class="cardToneClass(row.return_10d)">{{ formatPercent(row.return_10d) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="20 日收益" width="110">
          <template #default="{ row }">
            <span :class="cardToneClass(row.return_20d)">{{ formatPercent(row.return_20d) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="预期窗口收益" width="130">
          <template #default="{ row }">
            <span :class="cardToneClass(row.expected_return)">{{ formatPercent(row.expected_return) }}</span>
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.review-label {
  display: block;
  color: var(--text-faint);
  margin-bottom: 10px;
}

.review-value {
  display: block;
  font-size: 32px;
  color: var(--text);
  font-family: var(--font-heading);
}

.review-grid p {
  margin: 12px 0 0;
  color: var(--text-soft);
  line-height: 1.65;
}

.review-layout {
  grid-template-columns: minmax(0, 1.7fr) minmax(300px, 1fr);
}

.card-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.hint {
  color: var(--text-faint);
  font-size: 13px;
}

.window-list,
.sample-list {
  display: grid;
  gap: 14px;
}

.window-item,
.sample-item {
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 118, 110, 0.06);
}

.window-item p,
.sample-item p {
  margin: 8px 0 0;
  color: var(--text-soft);
  line-height: 1.6;
}

.sample-item {
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.sample-item:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 32px rgba(24, 42, 62, 0.08);
}

.sample-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

:deep(.row-positive) {
  --el-table-tr-bg-color: rgba(15, 118, 110, 0.04);
}

:deep(.row-negative) {
  --el-table-tr-bg-color: rgba(234, 88, 12, 0.05);
}

@media (max-width: 960px) {
  .review-grid,
  .review-layout {
    grid-template-columns: 1fr;
  }
}
</style>
