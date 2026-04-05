<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createPortfolioPosition,
  getPortfolioOverview,
  removePortfolioPosition,
  updatePortfolioPosition,
  updatePortfolioProfile,
} from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import type {
  PortfolioIndustryExposure,
  PortfolioOverview,
  PortfolioPositionCreateRequest,
  PortfolioPositionItem,
  PortfolioRiskLevel,
  PortfolioPositionSource,
  PortfolioPositionStatus,
  PortfolioProfileConfig,
} from '@/types/market'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const dialogVisible = ref(false)
const savingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const savingProfile = ref(false)
const editingId = ref<number | null>(null)
const statusFilter = ref<'all' | PortfolioPositionStatus>('all')
const overview = ref<PortfolioOverview | null>(null)
const rows = ref<PortfolioPositionItem[]>([])

const profileForm = reactive<PortfolioProfileConfig>({
  name: '本地账户',
  initial_capital: 500000,
  benchmark: '沪深300',
  notes: null,
})

const form = reactive<PortfolioPositionCreateRequest>({
  symbol: '',
  source: 'manual',
  status: 'holding',
  quantity: 100,
  entry_price: 0,
  exit_price: null,
  stop_loss_price: null,
  target_price: null,
  thesis: null,
  notes: null,
})

const statusOptions: Array<{ label: string; value: PortfolioPositionStatus }> = [
  { label: '持有中', value: 'holding' },
  { label: '已平仓', value: 'closed' },
]

const sourceLabels: Record<PortfolioPositionSource, string> = {
  manual: '手动',
  trade_plan: '计划',
  recommendation: '推荐',
  watchlist: '自选',
}

const filteredRows = computed(() => {
  if (statusFilter.value === 'all') {
    return rows.value
  }
  return rows.value.filter((item) => item.status === statusFilter.value)
})

function resetForm() {
  form.symbol = ''
  form.source = 'manual'
  form.status = 'holding'
  form.quantity = 100
  form.entry_price = 0
  form.exit_price = null
  form.stop_loss_price = null
  form.target_price = null
  form.thesis = null
  form.notes = null
}

async function loadOverview(showLoading = true) {
  if (showLoading) {
    loading.value = true
  }
  try {
    const payload = await getPortfolioOverview()
    overview.value = payload
    rows.value = payload.positions
    Object.assign(profileForm, payload.profile)
  } finally {
    if (showLoading) {
      loading.value = false
    }
  }
}

async function saveProfile() {
  savingProfile.value = true
  try {
    const profile = await updatePortfolioProfile({
      name: profileForm.name.trim(),
      initial_capital: profileForm.initial_capital,
      benchmark: profileForm.benchmark.trim(),
      notes: normalizeText(profileForm.notes),
    })
    Object.assign(profileForm, profile)
    await loadOverview(false)
    ElMessage.success('组合账户已更新。')
  } finally {
    savingProfile.value = false
  }
}

function openCreateDialog() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(item: PortfolioPositionItem) {
  editingId.value = item.id
  form.symbol = item.symbol
  form.source = item.source
  form.status = item.status
  form.quantity = item.quantity
  form.entry_price = item.entry_price
  form.exit_price = item.exit_price
  form.stop_loss_price = item.stop_loss_price
  form.target_price = item.target_price
  form.thesis = item.thesis
  form.notes = item.notes
  dialogVisible.value = true
}

function upsertRow(updated: PortfolioPositionItem) {
  const exists = rows.value.some((item) => item.id === updated.id)
  if (!exists) {
    rows.value = [updated, ...rows.value]
  } else {
    rows.value = rows.value.map((item) => (item.id === updated.id ? updated : item))
  }
}

function buildPayload() {
  return {
    symbol: form.symbol.trim(),
    source: form.source,
    status: form.status,
    quantity: form.quantity,
    entry_price: form.entry_price,
    exit_price: form.exit_price,
    stop_loss_price: form.stop_loss_price,
    target_price: form.target_price,
    thesis: normalizeText(form.thesis),
    notes: normalizeText(form.notes),
  }
}

async function savePosition() {
  if (!form.symbol.trim()) {
    ElMessage.warning('请先填写股票代码。')
    return
  }
  if (!form.entry_price || form.entry_price <= 0) {
    ElMessage.warning('请先填写有效的建仓成本。')
    return
  }

  savingId.value = editingId.value ?? -1
  try {
    const payload = buildPayload()
    const row = editingId.value === null
      ? await createPortfolioPosition(payload)
      : await updatePortfolioPosition(editingId.value, payload)
    upsertRow(row)
    dialogVisible.value = false
    await loadOverview(false)
    ElMessage.success(editingId.value === null ? '持仓已录入。' : '持仓已更新。')
  } finally {
    savingId.value = null
  }
}

async function handleStatusChange(item: PortfolioPositionItem, nextStatus: PortfolioPositionStatus) {
  const previous = item.status
  item.status = nextStatus
  savingId.value = item.id
  try {
    const updated = await updatePortfolioPosition(item.id, { status: nextStatus })
    upsertRow(updated)
    await loadOverview(false)
    ElMessage.success('持仓状态已更新。')
  } catch (error) {
    item.status = previous
    ElMessage.error('状态更新失败，请稍后再试。')
    throw error
  } finally {
    savingId.value = null
  }
}

async function removeItem(item: PortfolioPositionItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${item.name} (${item.symbol}) 的持仓记录吗？`,
      '删除持仓',
      { type: 'warning' },
    )
  } catch {
    return
  }

  deletingId.value = item.id
  try {
    await removePortfolioPosition(item.id)
    rows.value = rows.value.filter((row) => row.id !== item.id)
    await loadOverview(false)
    ElMessage.success('持仓记录已删除。')
  } finally {
    deletingId.value = null
  }
}

function openDetail(symbol: string) {
  void router.push(`/stocks/${symbol}`)
}

function formatNumber(value: number | null) {
  if (value === null) {
    return '暂无'
  }
  return value.toFixed(2)
}

function formatPercent(value: number | null) {
  if (value === null) {
    return '暂无'
  }
  return `${value.toFixed(2)}%`
}

function metricClass(value: number | null) {
  if (value === null) {
    return ''
  }
  return value >= 0 ? 'stat-positive' : 'stat-negative'
}

function sourceLabel(source: PortfolioPositionSource) {
  return sourceLabels[source]
}

function riskLevelLabel(level: PortfolioRiskLevel) {
  if (level === 'high') {
    return '高风险'
  }
  if (level === 'medium') {
    return '中风险'
  }
  return '低风险'
}

function riskLevelType(level: PortfolioRiskLevel) {
  if (level === 'high') {
    return 'danger'
  }
  if (level === 'medium') {
    return 'warning'
  }
  return 'success'
}

function topIndustryLabel(item: PortfolioIndustryExposure) {
  return `${item.industry} ${item.weight_pct.toFixed(2)}%`
}

function normalizeText(value: string | null | undefined) {
  if (!value) {
    return null
  }
  const cleaned = value.trim()
  return cleaned || null
}

function pickQueryValue(value: unknown): string | null {
  if (Array.isArray(value)) {
    return value.length ? String(value[0]) : null
  }
  if (value === undefined || value === null) {
    return null
  }
  return String(value)
}

function parseQueryNumber(value: unknown): number | null {
  const text = pickQueryValue(value)
  if (!text) {
    return null
  }
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
}

async function applyRoutePrefill() {
  if (route.path !== '/portfolio') {
    return
  }
  const symbol = pickQueryValue(route.query.symbol)
  if (!symbol) {
    return
  }

  editingId.value = null
  resetForm()
  form.symbol = symbol
  form.source = (pickQueryValue(route.query.source) as PortfolioPositionSource | null) ?? 'manual'
  form.status = (pickQueryValue(route.query.status) as PortfolioPositionStatus | null) ?? 'holding'
  form.entry_price = parseQueryNumber(route.query.entry) ?? 0
  form.exit_price = parseQueryNumber(route.query.exit)
  form.stop_loss_price = parseQueryNumber(route.query.stop)
  form.target_price = parseQueryNumber(route.query.target)
  form.quantity = parseQueryNumber(route.query.quantity) ?? 100
  form.thesis = normalizeText(pickQueryValue(route.query.thesis))
  form.notes = normalizeText(pickQueryValue(route.query.notes))
  dialogVisible.value = true
  await router.replace({ path: '/portfolio', query: {} })
}

watch(
  () => route.fullPath,
  () => {
    void applyRoutePrefill()
  },
  { immediate: true },
)

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="从单只股票视角，升级到组合和持仓视角"
      description="组合页负责回答三个问题：现在一共用了多少仓位、哪几只持仓最拖累或最赚钱、你的整体组合风险是否过度集中。"
    >
      <template #actions>
        <el-button plain @click="loadOverview">刷新组合</el-button>
        <el-button type="primary" @click="openCreateDialog">录入持仓</el-button>
      </template>
    </PageHeader>

    <section class="review-grid" v-if="overview">
      <el-card class="panel-card">
        <span class="review-label">预计总资产</span>
        <strong class="review-value">{{ overview.summary.estimated_total_assets.toFixed(2) }}</strong>
        <p>用初始资金、持仓成本、浮盈亏和已实现盈亏估算组合当前体量。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">预计现金</span>
        <strong class="review-value">{{ overview.summary.estimated_cash.toFixed(2) }}</strong>
        <p>按当前持仓成本粗估，还能继续调动多少现金。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">持仓市值</span>
        <strong class="review-value">{{ overview.summary.market_value.toFixed(2) }}</strong>
        <p>当前持有中仓位按最新价计算出来的总市值。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">仓位利用率</span>
        <strong class="review-value">{{ overview.summary.utilization_pct.toFixed(2) }}%</strong>
        <p>用持仓成本相对初始资金估算当前整体仓位。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">浮动盈亏</span>
        <strong class="review-value" :class="metricClass(overview.summary.unrealized_pnl)">
          {{ overview.summary.unrealized_pnl.toFixed(2) }}
        </strong>
        <p>只统计当前持有中的浮动盈亏。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">已实现盈亏</span>
        <strong class="review-value" :class="metricClass(overview.summary.realized_pnl)">
          {{ overview.summary.realized_pnl.toFixed(2) }}
        </strong>
        <p>只统计已平仓记录的最终盈亏。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">组合总收益</span>
        <strong class="review-value" :class="metricClass(overview.summary.total_return_pct)">
          {{ overview.summary.total_return_pct.toFixed(2) }}%
        </strong>
        <p>基于预计总资产相对初始资金计算的组合总收益率。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">最大持仓权重</span>
        <strong class="review-value">
          {{
            overview.summary.largest_weight_pct === null
              ? '暂无'
              : `${overview.summary.largest_weight_pct.toFixed(2)}%`
          }}
        </strong>
        <p>帮助你快速看组合有没有出现过度集中。</p>
      </el-card>
    </section>

    <section v-if="overview" class="section-grid risk-grid">
      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>风控摘要</span>
            <el-tag :type="riskLevelType(overview.summary.risk_level)" effect="plain">
              {{ riskLevelLabel(overview.summary.risk_level) }}
            </el-tag>
          </div>
        </template>
        <div class="summary-list">
          <div>
            <span>风险持仓数</span>
            <strong>{{ overview.summary.at_risk_position_count }}</strong>
          </div>
          <div>
            <span>止损前风险敞口</span>
            <strong>{{ overview.summary.capital_at_risk.toFixed(2) }}</strong>
          </div>
          <div>
            <span>风险敞口占比</span>
            <strong>{{ overview.summary.capital_at_risk_pct.toFixed(2) }}%</strong>
          </div>
          <div>
            <span>最弱持仓</span>
            <strong>
              {{
                overview.summary.worst_position_name
                  ? `${overview.summary.worst_position_name} ${formatPercent(overview.summary.worst_position_return_pct)}`
                  : '暂无'
              }}
            </strong>
          </div>
          <div>
            <span>盈利 / 亏损</span>
            <strong>{{ overview.summary.winning_count }} / {{ overview.summary.losing_count }}</strong>
          </div>
        </div>
      </el-card>

      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>行业暴露</span>
            <span class="hint">
              {{
                overview.summary.top_industry
                  ? `${overview.summary.top_industry} ${overview.summary.top_industry_weight_pct?.toFixed(2)}%`
                  : '暂无'
              }}
            </span>
          </div>
        </template>
        <div v-if="overview.industry_exposure.length" class="industry-list">
          <div
            v-for="item in overview.industry_exposure.slice(0, 5)"
            :key="item.industry"
            class="industry-item"
          >
            <div>
              <strong>{{ topIndustryLabel(item) }}</strong>
              <p>对应市值 {{ item.market_value.toFixed(2) }}</p>
            </div>
            <el-progress :percentage="Math.min(item.weight_pct, 100)" :show-text="false" :stroke-width="12" />
          </div>
        </div>
        <el-empty v-else description="暂无持有中仓位" />
      </el-card>
    </section>

    <section class="section-grid portfolio-grid">
      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>组合账户</span>
            <el-button type="primary" link :loading="savingProfile" @click="saveProfile">保存账户</el-button>
          </div>
        </template>
        <el-form label-position="top" class="profile-form">
          <el-form-item label="账户名称">
            <el-input v-model="profileForm.name" />
          </el-form-item>
          <el-form-item label="初始资金">
            <el-input-number
              v-model="profileForm.initial_capital"
              :min="1000"
              :step="10000"
              :precision="2"
            />
          </el-form-item>
          <el-form-item label="基准">
            <el-input v-model="profileForm.benchmark" placeholder="例如 沪深300" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input
              v-model="profileForm.notes"
              type="textarea"
              :rows="3"
              placeholder="记录这套组合的目标、风格或风险边界。"
            />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card class="panel-card">
        <template #header>
          <div class="card-head">
            <span>持仓筛选</span>
            <span class="hint">当前 {{ filteredRows.length }} 条</span>
          </div>
        </template>
        <div class="filter-stack">
          <el-radio-group v-model="statusFilter">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="holding">持有中</el-radio-button>
            <el-radio-button label="closed">已平仓</el-radio-button>
          </el-radio-group>
          <div class="summary-list" v-if="overview">
            <div>
              <span>持有中</span>
              <strong>{{ overview.summary.holding_count }}</strong>
            </div>
            <div>
              <span>已平仓</span>
              <strong>{{ overview.summary.closed_count }}</strong>
            </div>
            <div>
              <span>投入成本</span>
              <strong>{{ overview.summary.invested_cost.toFixed(2) }}</strong>
            </div>
          </div>
        </div>
      </el-card>
    </section>

    <el-card class="table-card">
      <el-table :data="filteredRows" v-loading="loading" empty-text="还没有持仓记录">
        <el-table-column label="股票 / 状态" min-width="180">
          <template #default="{ row }">
            <div class="name-block">
              <div class="name-row">
                <el-button link type="primary" @click="openDetail(row.symbol)">
                  {{ row.name }} ({{ row.symbol }})
                </el-button>
              </div>
              <span>{{ row.industry ?? row.board ?? '未分类' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-select
              :model-value="row.status"
              size="small"
              :loading="savingId === row.id"
              @update:model-value="handleStatusChange(row, $event)"
            >
              <el-option
                v-for="option in statusOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            {{ sourceLabel(row.source) }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="90" />
        <el-table-column label="成本 / 最新" width="140">
          <template #default="{ row }">
            <div class="price-pair">
              <span>成本 {{ formatNumber(row.entry_price) }}</span>
              <span>最新 {{ formatNumber(row.latest_price) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="成本市值" width="110">
          <template #default="{ row }">
            {{ row.cost_value.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="当前市值" width="110">
          <template #default="{ row }">
            {{ formatNumber(row.market_value) }}
          </template>
        </el-table-column>
        <el-table-column label="浮动收益" width="120">
          <template #default="{ row }">
            <div class="metric-cell">
              <strong :class="metricClass(row.unrealized_return)">{{ formatPercent(row.unrealized_return) }}</strong>
              <span :class="metricClass(row.unrealized_pnl)">{{ formatNumber(row.unrealized_pnl) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="已实现收益" width="120">
          <template #default="{ row }">
            <div class="metric-cell">
              <strong :class="metricClass(row.realized_return)">{{ formatPercent(row.realized_return) }}</strong>
              <span :class="metricClass(row.realized_pnl)">{{ formatNumber(row.realized_pnl) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="110">
          <template #default="{ row }">
            <el-tag :type="riskLevelType(row.risk_level)" effect="plain">
              {{ riskLevelLabel(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="权重" width="100">
          <template #default="{ row }">
            {{ formatPercent(row.weight_pct) }}
          </template>
        </el-table-column>
        <el-table-column label="止损 / 目标" width="180">
          <template #default="{ row }">
            <div class="price-pair">
              <span>止损 {{ formatNumber(row.stop_loss_price) }}</span>
              <span class="small-note">{{ formatPercent(row.stop_distance_pct) }}</span>
              <span>目标 {{ formatNumber(row.target_price) }}</span>
              <span class="small-note">+{{ formatPercent(row.target_distance_pct) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="评分" width="90">
          <template #default="{ row }">
            {{ row.score ?? '暂无' }}
          </template>
        </el-table-column>
        <el-table-column label="逻辑 / 备注" min-width="240">
          <template #default="{ row }">
            <div class="copy-block">
              <p>{{ row.thesis || '还没有写持仓逻辑' }}</p>
              <span>{{ row.notes || '还没有备注' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <div class="tag-wrap">
              <el-tag v-for="tag in row.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="风险提示" min-width="180">
          <template #default="{ row }">
            <div class="tag-wrap">
              <el-tag
                v-for="flag in row.risk_flags"
                :key="flag"
                :type="row.risk_level === 'high' ? 'danger' : 'warning'"
                effect="plain"
              >
                {{ flag }}
              </el-tag>
              <span v-if="row.risk_flags.length === 0" class="small-note">当前无明显风险提示</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
              <el-button
                link
                type="danger"
                :loading="deletingId === row.id"
                @click="removeItem(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '录入持仓' : '编辑持仓'"
      width="720px"
    >
      <el-form label-position="top" class="position-form">
        <div class="form-grid">
          <el-form-item label="股票代码">
            <el-input v-model="form.symbol" :disabled="editingId !== null" placeholder="例如 300308" />
          </el-form-item>
          <el-form-item label="来源">
            <el-select v-model="form.source">
              <el-option label="手动" value="manual" />
              <el-option label="交易计划" value="trade_plan" />
              <el-option label="推荐" value="recommendation" />
              <el-option label="自选" value="watchlist" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="form.status">
              <el-option
                v-for="option in statusOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="持仓数量">
            <el-input-number v-model="form.quantity" :min="1" :step="100" />
          </el-form-item>
          <el-form-item label="建仓成本">
            <el-input-number v-model="form.entry_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="平仓价格">
            <el-input-number v-model="form.exit_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="止损价">
            <el-input-number v-model="form.stop_loss_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="目标价">
            <el-input-number v-model="form.target_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
        </div>
        <el-form-item label="持仓逻辑">
          <el-input
            v-model="form.thesis"
            type="textarea"
            :rows="3"
            placeholder="写下这笔持仓成立的核心逻辑，比如趋势、板块、业绩或资金结构。"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="form.notes"
            type="textarea"
            :rows="3"
            placeholder="记录你的执行纪律、仓位调整或复盘观察。"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingId !== null" @click="savePosition">
          {{ editingId === null ? '录入持仓' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>
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
  font-size: 34px;
  color: var(--text);
  font-family: var(--font-heading);
}

.review-grid p {
  margin: 12px 0 0;
  color: var(--text-soft);
  line-height: 1.65;
}

.risk-grid {
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
}

.portfolio-grid {
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
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

.profile-form,
.position-form {
  display: grid;
  gap: 6px;
}

.filter-stack {
  display: grid;
  gap: 18px;
}

.summary-list {
  display: grid;
  gap: 14px;
}

.summary-list div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.summary-list span {
  color: var(--text-faint);
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

.name-block {
  display: grid;
  gap: 4px;
}

.name-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.name-block span {
  color: var(--text-soft);
}

.price-pair {
  display: grid;
  gap: 4px;
}

.metric-cell {
  display: grid;
  gap: 4px;
}

.copy-block {
  display: grid;
  gap: 6px;
}

.copy-block p {
  margin: 0;
  color: var(--text);
  line-height: 1.6;
}

.copy-block span {
  color: var(--text-soft);
  line-height: 1.6;
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-row {
  display: flex;
  gap: 8px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.small-note {
  color: var(--text-faint);
}

@media (max-width: 1080px) {
  .review-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .risk-grid,
  .portfolio-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .review-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
