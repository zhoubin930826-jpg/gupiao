<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { evaluateAlerts, getAlertOverview, updateAlertItem } from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import type {
  AlertCategory,
  AlertItem,
  AlertOverview,
  AlertSeverity,
  AlertStatus,
} from '@/types/market'

const router = useRouter()
const loading = ref(false)
const refreshing = ref(false)
const savingId = ref<number | null>(null)
const overview = ref<AlertOverview | null>(null)
const statusFilter = ref<'all' | AlertStatus>('active')
const severityFilter = ref<'all' | AlertSeverity>('all')
const categoryFilter = ref<'all' | AlertCategory>('all')

async function loadOverview(showLoading = true) {
  if (showLoading) {
    loading.value = true
  }
  try {
    overview.value = await getAlertOverview({
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      severity: severityFilter.value === 'all' ? undefined : severityFilter.value,
      category: categoryFilter.value === 'all' ? undefined : categoryFilter.value,
      limit: 120,
    })
  } finally {
    if (showLoading) {
      loading.value = false
    }
  }
}

async function refreshAlerts() {
  refreshing.value = true
  try {
    overview.value = await evaluateAlerts()
    ElMessage.success('提醒已根据最新数据刷新。')
    await loadOverview(false)
  } finally {
    refreshing.value = false
  }
}

async function changeStatus(item: AlertItem, status: AlertStatus) {
  savingId.value = item.id
  try {
    await updateAlertItem(item.id, { status })
    await loadOverview(false)
    ElMessage.success('提醒状态已更新。')
  } finally {
    savingId.value = null
  }
}

function openStock(item: AlertItem) {
  if (!item.symbol) {
    return
  }
  void router.push(`/stocks/${item.symbol}`)
}

function openContext(item: AlertItem) {
  if (item.action_path) {
    void router.push(item.action_path)
    return
  }
  if (item.symbol) {
    void router.push(`/stocks/${item.symbol}`)
  }
}

function severityLabel(severity: AlertSeverity) {
  if (severity === 'critical') {
    return '高优先级'
  }
  if (severity === 'warning') {
    return '待处理'
  }
  return '信息'
}

function severityType(severity: AlertSeverity) {
  if (severity === 'critical') {
    return 'danger'
  }
  if (severity === 'warning') {
    return 'warning'
  }
  return 'info'
}

function statusLabel(status: AlertStatus) {
  if (status === 'active') {
    return '待处理'
  }
  if (status === 'handled') {
    return '已处理'
  }
  return '已解决'
}

function statusType(status: AlertStatus) {
  if (status === 'active') {
    return 'danger'
  }
  if (status === 'handled') {
    return 'success'
  }
  return 'info'
}

function categoryLabel(category: AlertCategory) {
  if (category === 'trade_plan') {
    return '交易计划'
  }
  if (category === 'portfolio') {
    return '组合持仓'
  }
  return '自选池'
}

function formatNumber(value: number | null) {
  if (value === null) {
    return '暂无'
  }
  return value.toFixed(2)
}

watch([statusFilter, severityFilter, categoryFilter], () => {
  void loadOverview(false)
})

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="把每天真正需要处理的股票动作集中到一个地方"
      description="提醒中心把计划触发、止损风险、目标接近、仓位过重和自选池转强这些事件统一收拢，让你不用在多个页面里自己找变化。"
    >
      <template #actions>
        <el-button plain @click="loadOverview">刷新列表</el-button>
        <el-button type="primary" :loading="refreshing" @click="refreshAlerts">
          重新评估提醒
        </el-button>
      </template>
    </PageHeader>

    <section class="review-grid" v-if="overview">
      <el-card class="panel-card">
        <span class="review-label">待处理</span>
        <strong class="review-value">{{ overview.active_count }}</strong>
        <p>默认优先处理这部分，它们是当前仍在触发中的提醒。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">高优先级</span>
        <strong class="review-value">{{ overview.critical_count }}</strong>
        <p>通常是止损、计划失效或需要优先复核的事件。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">已处理</span>
        <strong class="review-value">{{ overview.handled_count }}</strong>
        <p>你已经看过并手动压掉的提醒，会留痕但不再占用主注意力。</p>
      </el-card>
      <el-card class="panel-card">
        <span class="review-label">最近评估</span>
        <strong class="review-value small-value">
          {{ overview.latest_evaluated_at ?? '暂无' }}
        </strong>
        <p>每次同步完成后会自动刷新，也可以在这里手动重新评估。</p>
      </el-card>
    </section>

    <el-card class="panel-card">
      <div class="filter-row">
        <div class="filter-group">
          <el-select v-model="statusFilter" style="width: 150px">
            <el-option label="只看待处理" value="active" />
            <el-option label="全部状态" value="all" />
            <el-option label="已处理" value="handled" />
            <el-option label="已解决" value="resolved" />
          </el-select>
          <el-select v-model="severityFilter" style="width: 150px">
            <el-option label="全部优先级" value="all" />
            <el-option label="高优先级" value="critical" />
            <el-option label="待处理" value="warning" />
            <el-option label="信息" value="info" />
          </el-select>
          <el-select v-model="categoryFilter" style="width: 150px">
            <el-option label="全部来源" value="all" />
            <el-option label="交易计划" value="trade_plan" />
            <el-option label="组合持仓" value="portfolio" />
            <el-option label="自选池" value="watchlist" />
          </el-select>
        </div>
        <span class="filter-hint">
          当前显示 {{ overview?.filtered_count ?? 0 }} / {{ overview?.total_count ?? 0 }} 条
        </span>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table :data="overview?.items ?? []" v-loading="loading" empty-text="当前没有符合条件的提醒">
        <el-table-column label="优先级 / 状态" width="170">
          <template #default="{ row }">
            <div class="status-stack">
              <el-tag :type="severityType(row.severity)" effect="plain">
                {{ severityLabel(row.severity) }}
              </el-tag>
              <el-tag :type="statusType(row.status)" effect="plain">
                {{ statusLabel(row.status) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            {{ categoryLabel(row.category) }}
          </template>
        </el-table-column>
        <el-table-column label="股票" width="150">
          <template #default="{ row }">
            <div class="name-block">
              <strong>{{ row.name ?? '未命名' }}</strong>
              <span>{{ row.symbol ?? '无代码' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="提醒内容" min-width="320">
          <template #default="{ row }">
            <div class="copy-block">
              <p>{{ row.title }}</p>
              <span>{{ row.message }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前值 / 阈值" width="150">
          <template #default="{ row }">
            <div class="value-block">
              <strong>{{ formatNumber(row.last_value) }}</strong>
              <span>阈值 {{ formatNumber(row.threshold_value) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最近出现" width="170">
          <template #default="{ row }">
            {{ row.last_seen_at }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button link type="primary" @click="openStock(row)" :disabled="!row.symbol">
                看个股
              </el-button>
              <el-button link @click="openContext(row)">打开页面</el-button>
              <el-button
                v-if="row.status !== 'handled'"
                link
                type="success"
                :loading="savingId === row.id"
                @click="changeStatus(row, 'handled')"
              >
                标记已处理
              </el-button>
              <el-button
                v-else
                link
                type="warning"
                :loading="savingId === row.id"
                @click="changeStatus(row, 'active')"
              >
                恢复待处理
              </el-button>
              <el-button
                v-if="row.status !== 'resolved'"
                link
                type="info"
                :loading="savingId === row.id"
                @click="changeStatus(row, 'resolved')"
              >
                标记已解决
              </el-button>
            </div>
          </template>
        </el-table-column>
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
  font-size: 34px;
  color: var(--text);
  font-family: var(--font-heading);
}

.small-value {
  font-size: 20px;
  line-height: 1.5;
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

.filter-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-hint {
  color: var(--text-faint);
}

.status-stack,
.value-block,
.name-block,
.copy-block {
  display: grid;
  gap: 6px;
}

.name-block span,
.value-block span,
.copy-block span {
  color: var(--text-soft);
}

.copy-block p {
  margin: 0;
  color: var(--text);
  line-height: 1.6;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 1080px) {
  .review-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-row {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 720px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
