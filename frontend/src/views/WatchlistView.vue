<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  getWatchlist,
  removeFromWatchlist,
  updateWatchlistItem,
} from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import type { WatchlistItem, WatchlistStatus } from '@/types/market'

const router = useRouter()
const loading = ref(false)
const statusFilter = ref<'all' | WatchlistStatus>('all')
const rows = ref<WatchlistItem[]>([])
const savingSymbol = ref<string | null>(null)
const noteDialogVisible = ref(false)
const noteForm = reactive({
  symbol: '',
  name: '',
  notes: '',
})

const filteredRows = computed(() => {
  if (statusFilter.value === 'all') {
    return rows.value
  }
  return rows.value.filter((item) => item.status === statusFilter.value)
})

const summary = computed(() => {
  const active = rows.value.filter((item) => item.status !== 'archived')
  const holding = rows.value.filter((item) => item.status === 'holding')
  const watching = rows.value.filter((item) => item.status === 'watching')
  const withReturn = active.filter((item) => item.current_return !== null)
  const averageReturn = withReturn.length
    ? withReturn.reduce((sum, item) => sum + (item.current_return ?? 0), 0) / withReturn.length
    : null

  return {
    total: rows.value.length,
    active: active.length,
    holding: holding.length,
    watching: watching.length,
    averageReturn,
  }
})

const statusOptions: Array<{ label: string; value: WatchlistStatus }> = [
  { label: '观察中', value: 'watching' },
  { label: '持有中', value: 'holding' },
  { label: '已归档', value: 'archived' },
]

async function loadWatchlist() {
  loading.value = true
  try {
    rows.value = await getWatchlist()
  } finally {
    loading.value = false
  }
}

function openDetail(symbol: string) {
  void router.push(`/stocks/${symbol}`)
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

function replaceRow(updated: WatchlistItem) {
  rows.value = rows.value.map((item) => (item.symbol === updated.symbol ? updated : item))
}

async function handleStatusChange(item: WatchlistItem, nextStatus: WatchlistStatus) {
  const previous = item.status
  item.status = nextStatus
  savingSymbol.value = item.symbol
  try {
    const updated = await updateWatchlistItem(item.symbol, { status: nextStatus })
    replaceRow(updated)
    ElMessage.success('跟踪状态已更新。')
  } catch (error) {
    item.status = previous
    ElMessage.error('状态更新失败，请稍后再试。')
    throw error
  } finally {
    savingSymbol.value = null
  }
}

function openNotes(item: WatchlistItem) {
  noteForm.symbol = item.symbol
  noteForm.name = item.name
  noteForm.notes = item.notes ?? ''
  noteDialogVisible.value = true
}

async function saveNotes() {
  savingSymbol.value = noteForm.symbol
  try {
    const updated = await updateWatchlistItem(noteForm.symbol, { notes: noteForm.notes })
    replaceRow(updated)
    noteDialogVisible.value = false
    ElMessage.success('观察备注已保存。')
  } finally {
    savingSymbol.value = null
  }
}

async function removeItem(item: WatchlistItem) {
  try {
    await ElMessageBox.confirm(
      `确认把 ${item.name} (${item.symbol}) 从自选池移除吗？`,
      '移出自选池',
      { type: 'warning' },
    )
  } catch {
    return
  }

  savingSymbol.value = item.symbol
  try {
    await removeFromWatchlist(item.symbol)
    rows.value = rows.value.filter((row) => row.symbol !== item.symbol)
    ElMessage.success('已移出自选池。')
  } finally {
    savingSymbol.value = null
  }
}

onMounted(() => {
  void loadWatchlist()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="把值得长期盯的标的收进一个池子里持续跟踪"
      description="自选池负责解决两件事：第一是把你关心的股票固定下来，第二是给这些股票明确一个跟踪状态，避免推荐出来以后又散掉。"
    >
      <template #actions>
        <el-button plain @click="loadWatchlist">刷新自选池</el-button>
      </template>
    </PageHeader>

    <section class="review-grid">
      <el-card class="panel-card">
        <span class="review-label">总标的数</span>
        <strong class="review-value">{{ summary.total }}</strong>
        <p>当前自选池里一共管理了多少只股票。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">观察中</span>
        <strong class="review-value">{{ summary.watching }}</strong>
        <p>还在持续跟踪、等待更好时机的候选。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">持有中</span>
        <strong class="review-value">{{ summary.holding }}</strong>
        <p>已经进入重点跟踪或你的持有阶段。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">活动池平均收益</span>
        <strong class="review-value">
          {{ summary.averageReturn === null ? '暂无' : `${summary.averageReturn.toFixed(2)}%` }}
        </strong>
        <p>按当前价格回看非归档标的的整体表现。</p>
      </el-card>
    </section>

    <el-card class="panel-card">
      <div class="filter-row">
        <el-radio-group v-model="statusFilter">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="watching">观察中</el-radio-button>
          <el-radio-button label="holding">持有中</el-radio-button>
          <el-radio-button label="archived">已归档</el-radio-button>
        </el-radio-group>
        <span class="filter-hint">当前显示 {{ filteredRows.length }} 只</span>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table :data="filteredRows" v-loading="loading" empty-text="还没有自选股票">
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column label="名称 / 行业" min-width="180">
          <template #default="{ row }">
            <div class="name-block">
              <strong>{{ row.name }}</strong>
              <span>{{ row.industry ?? row.board ?? '未分类' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="跟踪状态" width="140">
          <template #default="{ row }">
            <el-select
              :model-value="row.status"
              :loading="savingSymbol === row.symbol"
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
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column label="加入价" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.added_price) }}
          </template>
        </el-table-column>
        <el-table-column label="最新价" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.latest_price) }}
          </template>
        </el-table-column>
        <el-table-column label="当前收益" width="110">
          <template #default="{ row }">
            <span :class="row.current_return !== null && row.current_return >= 0 ? 'stat-positive' : 'stat-negative'">
              {{ formatPercent(row.current_return) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="评分" width="90">
          <template #default="{ row }">
            {{ row.score ?? '暂无' }}
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <div class="tag-wrap">
              <el-tag v-for="tag in row.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="200">
          <template #default="{ row }">
            <span class="notes-copy">{{ row.notes || '还没有备注' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="最近更新" width="180" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button text type="primary" @click="openDetail(row.symbol)">详情</el-button>
              <el-button text @click="openNotes(row)">备注</el-button>
              <el-button
                text
                type="danger"
                :loading="savingSymbol === row.symbol"
                @click="removeItem(row)"
              >
                移除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="noteDialogVisible" title="更新观察备注" width="520px">
      <div class="note-dialog">
        <p class="dialog-target">{{ noteForm.name }} · {{ noteForm.symbol }}</p>
        <el-input
          v-model="noteForm.notes"
          type="textarea"
          :rows="5"
          maxlength="240"
          show-word-limit
          placeholder="记录你为什么关注这只股票、关键价位或风险点。"
        />
      </div>
      <template #footer>
        <el-button @click="noteDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="savingSymbol === noteForm.symbol"
          @click="saveNotes"
        >
          保存备注
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
  font-size: 32px;
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
  gap: 16px;
  align-items: center;
}

.filter-hint {
  color: var(--text-faint);
}

.name-block {
  display: grid;
  gap: 6px;
}

.name-block span,
.notes-copy {
  color: var(--text-soft);
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.note-dialog {
  display: grid;
  gap: 12px;
}

.dialog-target {
  margin: 0;
  color: var(--text-soft);
}

@media (max-width: 960px) {
  .review-grid {
    grid-template-columns: 1fr;
  }

  .filter-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
