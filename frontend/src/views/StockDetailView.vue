<script setup lang="ts">
import { Star } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { addToWatchlist, getStockDetail, removeFromWatchlist } from '@/api/market'
import CandlestickChart from '@/components/charts/CandlestickChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import type { StockDetail } from '@/types/market'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const watchlistSubmitting = ref(false)
const detail = ref<StockDetail | null>(null)

const symbol = computed(() => String(route.params.symbol ?? ''))

function formatMaybePercent(value: number | null) {
  return value === null ? '暂无' : `${value.toFixed(1)}%`
}

function formatMaybeNumber(value: number | null) {
  return value === null ? '暂无' : value.toFixed(2)
}

async function loadDetail() {
  if (!symbol.value) {
    return
  }

  loading.value = true
  try {
    detail.value = await getStockDetail(symbol.value)
  } finally {
    loading.value = false
  }
}

async function toggleWatchlist() {
  if (!detail.value) {
    return
  }

  watchlistSubmitting.value = true
  try {
    if (detail.value.in_watchlist) {
      await removeFromWatchlist(detail.value.symbol)
      detail.value.in_watchlist = false
      ElMessage.success('已移出自选池。')
      return
    }

    await addToWatchlist({
      symbol: detail.value.symbol,
      source: 'manual',
    })
    detail.value.in_watchlist = true
    ElMessage.success('已加入自选池。')
  } finally {
    watchlistSubmitting.value = false
  }
}

function openTradePlan() {
  if (!detail.value) {
    return
  }
  void router.push({
    path: '/trade-plans',
    query: {
      symbol: detail.value.symbol,
      source: detail.value.in_watchlist ? 'watchlist' : 'manual',
      thesis: detail.value.thesis,
      entry: detail.value.latest_price,
      status: 'planned',
    },
  })
}

watch(
  symbol,
  () => {
    void loadDetail()
  },
  { immediate: true },
)
</script>

<template>
  <div class="page">
    <PageHeader
      :title="detail ? `${detail.name} · ${detail.symbol}` : '个股详情'"
      description="详情页重点解决两个问题：这只股票为什么会进池，以及现在值不值得你进一步人工复核。这里先放价格结构、信号拆解和风险提示。"
    >
      <template #actions>
        <el-button
          :icon="Star"
          :type="detail?.in_watchlist ? 'warning' : 'default'"
          :loading="watchlistSubmitting"
          @click="toggleWatchlist"
        >
          {{ detail?.in_watchlist ? '移出自选' : '加入自选' }}
        </el-button>
        <el-button type="primary" plain @click="openTradePlan">加入计划</el-button>
        <el-button plain @click="loadDetail">刷新个股</el-button>
      </template>
    </PageHeader>

    <el-skeleton :loading="loading" animated :rows="12">
      <template #default>
        <template v-if="detail">
          <section class="detail-hero glass-card">
            <div class="hero-main">
              <div class="headline-row">
                <div>
                  <h3>{{ detail.name }}</h3>
                  <p>{{ detail.industry }} · {{ detail.board }}</p>
                </div>
                <div class="price-block">
                  <strong>{{ detail.latest_price.toFixed(2) }}</strong>
                  <span :class="detail.change_pct >= 0 ? 'stat-positive' : 'stat-negative'">
                    {{ detail.change_pct.toFixed(2) }}%
                  </span>
                </div>
              </div>
              <p class="thesis">{{ detail.thesis }}</p>
              <div class="tag-row">
                <el-tag v-for="tag in detail.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
                <el-tag v-if="detail.in_watchlist" type="warning">已在自选池</el-tag>
              </div>
            </div>
            <div class="score-panel">
              <span>综合评分</span>
              <strong>{{ detail.score }}</strong>
              <p>用于推荐排序，不代替你的最终交易判断。</p>
            </div>
          </section>

          <section class="section-grid detail-grid">
            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>价格结构</span>
                  <span class="hint">示例 K 线与均线</span>
                </div>
              </template>
              <CandlestickChart :points="detail.price_series" />
            </el-card>

            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>信号拆解</span>
                  <span class="hint">四维度评分</span>
                </div>
              </template>
              <div class="signal-list">
                <div
                  v-for="signal in detail.signal_breakdown"
                  :key="signal.dimension"
                  class="signal-item"
                >
                  <div class="signal-head">
                    <strong>{{ signal.dimension }}</strong>
                    <span>{{ signal.score }} 分</span>
                  </div>
                  <el-progress
                    :percentage="signal.score"
                    :stroke-width="10"
                    :show-text="false"
                  />
                  <p>{{ signal.takeaway }}</p>
                </div>
              </div>
            </el-card>
          </section>

          <section class="section-grid detail-grid">
            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>推荐逻辑</span>
                  <span class="hint">适合写到推荐理由里</span>
                </div>
              </template>
              <ul class="copy-list">
                <li v-for="point in detail.thesis_points" :key="point">{{ point }}</li>
              </ul>
            </el-card>

            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>风险提示</span>
                  <span class="hint">不忽略不利条件</span>
                </div>
              </template>
              <ul class="copy-list warning-list">
                <li v-for="note in detail.risk_notes" :key="note">{{ note }}</li>
              </ul>
            </el-card>
          </section>

          <section v-if="detail.fundamental" class="section-grid detail-grid">
            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>财务快照</span>
                  <span class="hint">{{ detail.fundamental.report_period ?? '最新报告期' }}</span>
                </div>
              </template>
              <div class="fundamental-grid">
                <div class="fundamental-item">
                  <span>营收同比</span>
                  <strong>{{ formatMaybePercent(detail.fundamental.revenue_growth) }}</strong>
                </div>
                <div class="fundamental-item">
                  <span>净利润同比</span>
                  <strong>{{ formatMaybePercent(detail.fundamental.net_profit_growth) }}</strong>
                </div>
                <div class="fundamental-item">
                  <span>扣非利润同比</span>
                  <strong>{{ formatMaybePercent(detail.fundamental.deduct_profit_growth) }}</strong>
                </div>
                <div class="fundamental-item">
                  <span>ROE</span>
                  <strong>{{ formatMaybePercent(detail.fundamental.roe) }}</strong>
                </div>
                <div class="fundamental-item">
                  <span>毛利率</span>
                  <strong>{{ formatMaybePercent(detail.fundamental.gross_margin) }}</strong>
                </div>
                <div class="fundamental-item">
                  <span>资产负债率</span>
                  <strong>{{ formatMaybePercent(detail.fundamental.debt_ratio) }}</strong>
                </div>
                <div class="fundamental-item">
                  <span>EPS</span>
                  <strong>{{ formatMaybeNumber(detail.fundamental.eps) }}</strong>
                </div>
                <div class="fundamental-item">
                  <span>每股经营现金流</span>
                  <strong>{{ formatMaybeNumber(detail.fundamental.operating_cashflow_per_share) }}</strong>
                </div>
              </div>
            </el-card>

            <el-card class="panel-card">
              <template #header>
                <div class="card-head">
                  <span>财务解读</span>
                  <span class="hint">帮助你扫一眼质量和成长</span>
                </div>
              </template>
              <ul class="copy-list">
                <li>营收和净利润增速更适合判断业绩兑现和景气是否同步。</li>
                <li>ROE 和毛利率偏质量维度，适合筛掉景气弱但情绪高的标的。</li>
                <li>资产负债率和经营现金流可以帮助你快速识别财务压力。</li>
              </ul>
            </el-card>
          </section>
        </template>
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
.detail-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 18px;
  padding: 28px;
}

.headline-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.headline-row h3 {
  margin: 0;
  font-size: 32px;
}

.headline-row p {
  margin: 8px 0 0;
  color: var(--text-soft);
}

.price-block {
  text-align: right;
}

.price-block strong {
  display: block;
  font-size: 40px;
  font-family: var(--font-heading);
}

.thesis {
  margin: 18px 0 0;
  line-height: 1.75;
  color: var(--text-soft);
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.score-panel {
  display: grid;
  align-content: center;
  gap: 6px;
  padding: 22px;
  border-radius: 22px;
  background: rgba(15, 118, 110, 0.08);
}

.score-panel strong {
  font-size: 52px;
  color: var(--accent);
  font-family: var(--font-heading);
}

.score-panel p {
  margin: 0;
  line-height: 1.6;
  color: var(--text-soft);
}

.detail-grid {
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
}

.signal-list {
  display: grid;
  gap: 18px;
}

.fundamental-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.fundamental-item {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 118, 110, 0.06);
}

.fundamental-item span {
  color: var(--text-faint);
}

.fundamental-item strong {
  font-size: 24px;
  color: var(--text);
  font-family: var(--font-heading);
}

.signal-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.signal-item p,
.copy-list {
  color: var(--text-soft);
}

.copy-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 12px;
  line-height: 1.7;
}

.warning-list li {
  color: #9a3412;
}

.card-head {
  display: flex;
  justify-content: space-between;
}

.hint {
  color: var(--text-faint);
  font-size: 13px;
}

@media (max-width: 960px) {
  .detail-hero,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .fundamental-grid {
    grid-template-columns: 1fr;
  }

  .headline-row {
    flex-direction: column;
  }

  .price-block {
    text-align: left;
  }
}
</style>
