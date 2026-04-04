<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createTradePlan,
  getTradePlans,
  removeTradePlan,
  updateTradePlanItem,
} from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import type {
  TradePlanCreateRequest,
  TradePlanItem,
  TradePlanSource,
  TradePlanStatus,
} from '@/types/market'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const dialogVisible = ref(false)
const savingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const statusFilter = ref<'all' | TradePlanStatus>('all')
const rows = ref<TradePlanItem[]>([])
const editingId = ref<number | null>(null)

const form = reactive<TradePlanCreateRequest>({
  symbol: '',
  source: 'manual',
  status: 'planned',
  thesis: null,
  notes: null,
  planned_entry_price: null,
  actual_entry_price: null,
  actual_exit_price: null,
  stop_loss_price: null,
  target_price: null,
  planned_position_pct: 10,
})

const statusOptions: Array<{ label: string; value: TradePlanStatus }> = [
  { label: '计划中', value: 'planned' },
  { label: '持有中', value: 'active' },
  { label: '已平仓', value: 'closed' },
  { label: '已取消', value: 'cancelled' },
]

const sourceLabels: Record<TradePlanSource, string> = {
  manual: '手动',
  recommendation: '推荐',
  watchlist: '自选',
}

const filteredRows = computed(() => {
  if (statusFilter.value === 'all') {
    return rows.value
  }
  return rows.value.filter((item) => item.status === statusFilter.value)
})

const summary = computed(() => {
  const active = rows.value.filter((item) => item.status === 'active')
  const planned = rows.value.filter((item) => item.status === 'planned')
  const closed = rows.value.filter((item) => item.status === 'closed')
  const activeWithReturn = active.filter((item) => item.current_return !== null)
  const closedWithReturn = closed.filter((item) => item.realized_return !== null)

  const avgFloating = activeWithReturn.length
    ? activeWithReturn.reduce((sum, item) => sum + (item.current_return ?? 0), 0) / activeWithReturn.length
    : null
  const winRate = closedWithReturn.length
    ? (closedWithReturn.filter((item) => (item.realized_return ?? 0) > 0).length / closedWithReturn.length) * 100
    : null

  return {
    total: rows.value.length,
    planned: planned.length,
    avgFloating,
    winRate,
    active: active.length,
    closed: closed.length,
  }
})

function resetForm() {
  form.symbol = ''
  form.source = 'manual'
  form.status = 'planned'
  form.thesis = null
  form.notes = null
  form.planned_entry_price = null
  form.actual_entry_price = null
  form.actual_exit_price = null
  form.stop_loss_price = null
  form.target_price = null
  form.planned_position_pct = 10
}

async function loadTradePlans(showLoading = true) {
  if (showLoading) {
    loading.value = true
  }
  try {
    rows.value = await getTradePlans()
  } finally {
    if (showLoading) {
      loading.value = false
    }
  }
}

function openCreateDialog() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(item: TradePlanItem) {
  editingId.value = item.id
  form.symbol = item.symbol
  form.source = item.source
  form.status = item.status
  form.thesis = item.thesis
  form.notes = item.notes
  form.planned_entry_price = item.planned_entry_price
  form.actual_entry_price = item.actual_entry_price
  form.actual_exit_price = item.actual_exit_price
  form.stop_loss_price = item.stop_loss_price
  form.target_price = item.target_price
  form.planned_position_pct = item.planned_position_pct
  dialogVisible.value = true
}

function upsertRow(updated: TradePlanItem) {
  const exists = rows.value.some((item) => item.id === updated.id)
  if (!exists) {
    rows.value = [updated, ...rows.value]
    return
  }
  rows.value = rows.value.map((item) => (item.id === updated.id ? updated : item))
}

function buildPayload() {
  return {
    symbol: form.symbol.trim(),
    source: form.source,
    status: form.status,
    thesis: normalizeText(form.thesis),
    notes: normalizeText(form.notes),
    planned_entry_price: form.planned_entry_price,
    actual_entry_price: form.actual_entry_price,
    actual_exit_price: form.actual_exit_price,
    stop_loss_price: form.stop_loss_price,
    target_price: form.target_price,
    planned_position_pct: form.planned_position_pct,
  }
}

async function savePlan() {
  if (!form.symbol.trim()) {
    ElMessage.warning('请先填写股票代码。')
    return
  }

  savingId.value = editingId.value ?? -1
  try {
    const payload = buildPayload()
    const row = editingId.value === null
      ? await createTradePlan(payload)
      : await updateTradePlanItem(editingId.value, payload)
    upsertRow(row)
    dialogVisible.value = false
    ElMessage.success(editingId.value === null ? '交易计划已创建。' : '交易计划已更新。')
  } finally {
    savingId.value = null
  }
}

async function handleStatusChange(item: TradePlanItem, nextStatus: TradePlanStatus) {
  const previous = item.status
  item.status = nextStatus
  savingId.value = item.id
  try {
    const updated = await updateTradePlanItem(item.id, { status: nextStatus })
    upsertRow(updated)
    ElMessage.success('计划状态已更新。')
  } catch (error) {
    item.status = previous
    ElMessage.error('状态更新失败，请稍后再试。')
    throw error
  } finally {
    savingId.value = null
  }
}

async function removeItem(item: TradePlanItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${item.name} (${item.symbol}) 的交易计划吗？`,
      '删除交易计划',
      { type: 'warning' },
    )
  } catch {
    return
  }

  deletingId.value = item.id
  try {
    await removeTradePlan(item.id)
    rows.value = rows.value.filter((row) => row.id !== item.id)
    ElMessage.success('交易计划已删除。')
  } finally {
    deletingId.value = null
  }
}

function openDetail(symbol: string) {
  void router.push(`/stocks/${symbol}`)
}

function pushToPortfolio(item: TradePlanItem) {
  const portfolioStatus = item.status === 'closed' ? 'closed' : 'holding'
  void router.push({
    path: '/portfolio',
    query: {
      symbol: item.symbol,
      source: 'trade_plan',
      status: portfolioStatus,
      entry: String(item.actual_entry_price ?? item.planned_entry_price ?? item.latest_price ?? ''),
      exit: item.actual_exit_price === null ? undefined : String(item.actual_exit_price),
      stop: item.stop_loss_price === null ? undefined : String(item.stop_loss_price),
      target: item.target_price === null ? undefined : String(item.target_price),
      quantity: '100',
      thesis: item.thesis ?? undefined,
      notes: item.notes ?? undefined,
    },
  })
}

function metricLabel(item: TradePlanItem) {
  if (item.status === 'planned') {
    return '计划偏差'
  }
  if (item.status === 'closed') {
    return '已实现收益'
  }
  return '浮动收益'
}

function metricValue(item: TradePlanItem) {
  if (item.status === 'planned') {
    return item.plan_gap_pct
  }
  if (item.status === 'closed') {
    return item.realized_return
  }
  return item.current_return
}

function formatPercent(value: number | null) {
  if (value === null) {
    return '暂无'
  }
  return `${value.toFixed(2)}%`
}

function formatNumber(value: number | null) {
  if (value === null) {
    return '暂无'
  }
  return value.toFixed(2)
}

function metricClass(value: number | null) {
  if (value === null) {
    return ''
  }
  return value >= 0 ? 'stat-positive' : 'stat-negative'
}

function statusTagType(status: TradePlanStatus) {
  if (status === 'active') {
    return 'success'
  }
  if (status === 'closed') {
    return 'info'
  }
  if (status === 'cancelled') {
    return 'warning'
  }
  return ''
}

function sourceLabel(source: TradePlanSource) {
  return sourceLabels[source]
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

function normalizeText(value: string | null | undefined) {
  if (!value) {
    return null
  }
  const cleaned = value.trim()
  return cleaned || null
}

async function applyRoutePrefill() {
  if (route.path !== '/trade-plans') {
    return
  }
  const symbol = pickQueryValue(route.query.symbol)
  if (!symbol) {
    return
  }

  editingId.value = null
  resetForm()
  form.symbol = symbol
  form.source = (pickQueryValue(route.query.source) as TradePlanSource | null) ?? 'manual'
  form.thesis = normalizeText(pickQueryValue(route.query.thesis))
  form.planned_entry_price = parseQueryNumber(route.query.entry)
  form.status = ((pickQueryValue(route.query.status) as TradePlanStatus | null) ?? 'planned')
  dialogVisible.value = true
  await router.replace({ path: '/trade-plans', query: {} })
}

watch(
  () => route.fullPath,
  () => {
    void applyRoutePrefill()
  },
  { immediate: true },
)

onMounted(() => {
  void loadTradePlans()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="把候选股变成真正可执行的计划和持仓记录"
      description="交易计划页解决的是最后一公里问题。推荐再好，如果没有计划价、止损价、目标价和状态跟踪，很快就会从研究候选变成看过就散的列表。"
    >
      <template #actions>
        <el-button plain @click="loadTradePlans">刷新计划</el-button>
        <el-button type="primary" @click="openCreateDialog">新建计划</el-button>
      </template>
    </PageHeader>

    <section class="review-grid">
      <el-card class="panel-card">
        <span class="review-label">计划总数</span>
        <strong class="review-value">{{ summary.total }}</strong>
        <p>你当前一共管理了多少条交易计划和持仓记录。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">计划中</span>
        <strong class="review-value">{{ summary.planned }}</strong>
        <p>还没进场、等待条件满足的计划数量。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">持有中平均浮盈</span>
        <strong class="review-value">
          {{ summary.avgFloating === null ? '暂无' : `${summary.avgFloating.toFixed(2)}%` }}
        </strong>
        <p>用来判断当前活动计划整体处于顺风还是逆风。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">已平仓胜率</span>
        <strong class="review-value">
          {{ summary.winRate === null ? '暂无' : `${summary.winRate.toFixed(1)}%` }}
        </strong>
        <p>基于已平仓记录统计，当前已完成 {{ summary.closed }} 笔。</p>
      </el-card>
    </section>

    <el-card class="panel-card">
      <div class="filter-row">
        <el-radio-group v-model="statusFilter">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="planned">计划中</el-radio-button>
          <el-radio-button label="active">持有中</el-radio-button>
          <el-radio-button label="closed">已平仓</el-radio-button>
          <el-radio-button label="cancelled">已取消</el-radio-button>
        </el-radio-group>
        <span class="filter-hint">当前显示 {{ filteredRows.length }} 条</span>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table :data="filteredRows" v-loading="loading" empty-text="还没有交易计划">
        <el-table-column label="股票 / 状态" min-width="190">
          <template #default="{ row }">
            <div class="name-block">
              <div class="name-row">
                <el-button link type="primary" @click="openDetail(row.symbol)">
                  {{ row.name }} ({{ row.symbol }})
                </el-button>
                <el-tag :type="statusTagType(row.status)" effect="plain">
                  {{ statusOptions.find((item) => item.value === row.status)?.label ?? row.status }}
                </el-tag>
              </div>
              <span>{{ row.industry ?? row.board ?? '未分类' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态切换" width="140">
          <template #default="{ row }">
            <el-select
              :model-value="row.status"
              :loading="savingId === row.id"
              size="small"
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
        <el-table-column label="评分" width="90">
          <template #default="{ row }">
            {{ row.score ?? '暂无' }}
          </template>
        </el-table-column>
        <el-table-column label="计划价" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.planned_entry_price) }}
          </template>
        </el-table-column>
        <el-table-column label="入场价" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.actual_entry_price) }}
          </template>
        </el-table-column>
        <el-table-column label="最新价" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.latest_price) }}
          </template>
        </el-table-column>
        <el-table-column label="止损 / 目标" width="160">
          <template #default="{ row }">
            <div class="price-pair">
              <span>止损 {{ formatNumber(row.stop_loss_price) }}</span>
              <span>目标 {{ formatNumber(row.target_price) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="计划仓位" width="100">
          <template #default="{ row }">
            {{ row.planned_position_pct === null ? '暂无' : `${row.planned_position_pct}%` }}
          </template>
        </el-table-column>
        <el-table-column label="收益" width="120">
          <template #default="{ row }">
            <div class="metric-cell">
              <span class="metric-label">{{ metricLabel(row) }}</span>
              <strong :class="metricClass(metricValue(row))">
                {{ formatPercent(metricValue(row)) }}
              </strong>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="盈亏比" width="100">
          <template #default="{ row }">
            {{ row.risk_reward_ratio === null ? '暂无' : row.risk_reward_ratio.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="交易逻辑 / 备注" min-width="260">
          <template #default="{ row }">
            <div class="copy-block">
              <p>{{ row.thesis || '还没有写交易逻辑' }}</p>
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
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button
                link
                type="success"
                :disabled="row.status === 'cancelled'"
                @click="pushToPortfolio(row)"
              >
                转持仓
              </el-button>
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
      :title="editingId === null ? '新建交易计划' : '编辑交易计划'"
      width="720px"
    >
      <el-form label-position="top" class="plan-form">
        <div class="form-grid">
          <el-form-item label="股票代码">
            <el-input v-model="form.symbol" :disabled="editingId !== null" placeholder="例如 300308" />
          </el-form-item>
          <el-form-item label="来源">
            <el-select v-model="form.source">
              <el-option label="手动" value="manual" />
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
          <el-form-item label="计划仓位 (%)">
            <el-input-number v-model="form.planned_position_pct" :min="1" :max="100" :step="1" />
          </el-form-item>
          <el-form-item label="计划入场价">
            <el-input-number v-model="form.planned_entry_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="实际入场价">
            <el-input-number v-model="form.actual_entry_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="止损价">
            <el-input-number v-model="form.stop_loss_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="目标价">
            <el-input-number v-model="form.target_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="实际离场价">
            <el-input-number v-model="form.actual_exit_price" :min="0" :step="0.01" :precision="2" />
          </el-form-item>
        </div>

        <el-form-item label="交易逻辑">
          <el-input
            v-model="form.thesis"
            type="textarea"
            :rows="3"
            placeholder="写下这笔计划为什么成立，比如趋势、行业、财务或情绪逻辑。"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="form.notes"
            type="textarea"
            :rows="3"
            placeholder="记录执行条件、复盘结论或你自己的交易纪律。"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingId !== null" @click="savePlan">
          {{ editingId === null ? '创建计划' : '保存修改' }}
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

.filter-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.filter-hint {
  color: var(--text-faint);
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

.metric-label {
  color: var(--text-faint);
  font-size: 12px;
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

.plan-form {
  display: grid;
  gap: 6px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

@media (max-width: 1080px) {
  .review-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .review-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .filter-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
