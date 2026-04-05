<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDataSourceOverview, listTasks, triggerMarketSync } from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { DataSourceOverview, DataSourceStatusItem, SyncTask } from '@/types/market'

const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const syncSubmitting = ref(false)
const tasks = ref<SyncTask[]>([])
const dataSourceOverview = ref<DataSourceOverview | null>(null)
let pollTimer: number | null = null

async function loadTasks(showLoading = true) {
  if (showLoading) {
    loading.value = true
  }
  try {
    const [taskPayload, providerPayload] = await Promise.all([
      listTasks(),
      getDataSourceOverview(),
    ])
    tasks.value = taskPayload
    dataSourceOverview.value = providerPayload
  } finally {
    if (showLoading) {
      loading.value = false
    }
  }
}

async function runSync() {
  syncSubmitting.value = true
  try {
    const task = await triggerMarketSync()
    ElMessage.success(`${task.name} 已提交，后台会继续执行同步。`)
    await loadTasks(false)
  } finally {
    syncSubmitting.value = false
  }
}

function startPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
  }
  pollTimer = window.setInterval(() => {
    if (tasks.value.some((task) => task.status === 'running')) {
      void loadTasks(false)
    }
  }, 8000)
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function providerLabel(item: DataSourceStatusItem) {
  const capabilities = []
  if (item.supports_snapshot) {
    capabilities.push('快照')
  }
  if (item.supports_history) {
    capabilities.push('历史')
  }
  if (item.supports_fundamental) {
    capabilities.push('财务')
  }
  return capabilities.join(' / ')
}

function providerStatusType(item: DataSourceStatusItem) {
  if (!item.enabled) {
    return 'info'
  }
  if (item.last_status === 'success') {
    return 'success'
  }
  if (item.last_status === 'warning') {
    return 'warning'
  }
  return 'info'
}

function providerStatusLabel(item: DataSourceStatusItem) {
  if (!item.enabled) {
    return '未启用'
  }
  if (item.last_status === 'success') {
    return '健康'
  }
  if (item.last_status === 'warning') {
    return '异常'
  }
  return '待运行'
}

function eventStatusType(status: DataSourceOverview['event_sync']['status']) {
  if (status === 'ready') {
    return 'success'
  }
  if (status === 'partial' || status === 'placeholder') {
    return 'warning'
  }
  return 'info'
}

function eventStatusLabel(status: DataSourceOverview['event_sync']['status']) {
  if (status === 'ready') {
    return '已命中'
  }
  if (status === 'partial') {
    return '部分覆盖'
  }
  if (status === 'placeholder') {
    return '中性占位'
  }
  return '待同步'
}

onMounted(() => {
  void workspaceStore.refreshHealth()
  void loadTasks()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="把采集、分析和推荐刷新都放到一个页面上管理"
      description="数据任务页现在不只告诉你任务有没有成功，还会显示主数据源、回退链和各个数据源的最近健康状态，方便你判断今天的数据到底靠不靠谱。"
    >
      <template #actions>
        <el-button plain @click="loadTasks">刷新任务</el-button>
        <el-button type="primary" :loading="syncSubmitting" @click="runSync">
          提交同步
        </el-button>
      </template>
    </PageHeader>

    <el-alert
      :title="workspaceStore.schedulerEnabled ? '自动调度已开启' : '当前是手动调度模式'"
      :type="workspaceStore.schedulerEnabled ? 'success' : 'warning'"
      :closable="false"
      class="scheduler-alert"
    >
      <template #default>
        <span v-if="workspaceStore.schedulerEnabled">
          后端会按任务计划自动执行市场同步，你仍然可以随时手动提交同步。
        </span>
        <span v-else>
          自动调度已关闭，当前需要你手动点击“提交同步”来刷新数据。
        </span>
      </template>
    </el-alert>

    <section v-if="dataSourceOverview" class="section-grid providers-grid">
      <el-card class="panel-card provider-summary-card">
        <div class="task-top">
          <div>
            <h3>数据源健康度</h3>
            <p>同步会按回退链依次尝试主数据源，失败时自动回退到后备来源；事件层状态也会一起显示在这里。</p>
          </div>
          <el-tag type="primary">
            当前主源：{{ dataSourceOverview.current_provider }}
          </el-tag>
        </div>

        <div class="meta-grid">
          <div>
            <span>回退链</span>
            <strong>{{ dataSourceOverview.fallback_chain.join(' -> ') }}</strong>
          </div>
          <div>
            <span>健康数据源</span>
            <strong>
              {{ dataSourceOverview.items.filter((item) => item.last_status === 'success').length }} 个
            </strong>
          </div>
          <div>
            <span>异常数据源</span>
            <strong>
              {{ dataSourceOverview.items.filter((item) => item.last_status === 'warning').length }} 个
            </strong>
          </div>
          <div>
            <span>总数据源</span>
            <strong>{{ dataSourceOverview.items.length }} 个</strong>
          </div>
        </div>
      </el-card>

      <el-card class="panel-card">
        <div class="task-top">
          <div>
            <h3>事件层状态</h3>
            <p>{{ dataSourceOverview.event_sync.summary }}</p>
          </div>
          <el-tag :type="eventStatusType(dataSourceOverview.event_sync.status)">
            {{ eventStatusLabel(dataSourceOverview.event_sync.status) }}
          </el-tag>
        </div>

        <div class="meta-grid">
          <div>
            <span>接入来源</span>
            <strong>{{ dataSourceOverview.event_sync.configured_sources.join(' / ') }}</strong>
          </div>
          <div>
            <span>当前覆盖</span>
            <strong>
              {{ dataSourceOverview.event_sync.coverage_count }}/{{ dataSourceOverview.event_sync.total_symbols }} 只
            </strong>
          </div>
          <div>
            <span>明确催化</span>
            <strong>{{ dataSourceOverview.event_sync.active_symbols }} 只</strong>
          </div>
          <div>
            <span>事件条目</span>
            <strong>{{ dataSourceOverview.event_sync.total_items }} 条</strong>
          </div>
          <div>
            <span>本次命中来源</span>
            <strong>
              {{
                dataSourceOverview.event_sync.detected_sources.length
                  ? dataSourceOverview.event_sync.detected_sources.join(' / ')
                  : '当前暂无明确命中'
              }}
            </strong>
          </div>
          <div>
            <span>最近同步</span>
            <strong>{{ dataSourceOverview.event_sync.updated_at ?? '尚未同步' }}</strong>
          </div>
        </div>
      </el-card>

      <el-card
        v-for="provider in dataSourceOverview.items"
        :key="provider.provider_key"
        class="panel-card"
      >
        <div class="task-top">
          <div>
            <h3>{{ provider.display_name }}</h3>
            <p>{{ provider.last_message }}</p>
          </div>
          <el-tag :type="providerStatusType(provider)">
            {{ providerStatusLabel(provider) }}
          </el-tag>
        </div>

        <div class="meta-grid">
          <div>
            <span>能力</span>
            <strong>{{ providerLabel(provider) || '暂无' }}</strong>
          </div>
          <div>
            <span>启用状态</span>
            <strong>{{ provider.enabled ? '已启用' : '未启用' }}</strong>
          </div>
          <div>
            <span>最近成功</span>
            <strong>{{ provider.last_success_at ?? '暂无' }}</strong>
          </div>
          <div>
            <span>最近失败</span>
            <strong>{{ provider.last_failure_at ?? '暂无' }}</strong>
          </div>
        </div>
      </el-card>
    </section>

    <div class="section-grid tasks-grid" v-loading="loading">
      <el-card v-for="task in tasks" :key="task.task_key" class="panel-card">
        <div class="task-top">
          <div>
            <h3>{{ task.name }}</h3>
            <p>{{ task.message }}</p>
          </div>
          <el-tag
            :type="
              task.status === 'success'
                ? 'success'
                : task.status === 'warning'
                  ? 'warning'
                  : task.status === 'running'
                    ? 'primary'
                    : 'info'
            "
          >
            {{ task.status }}
          </el-tag>
        </div>

        <div class="meta-grid">
          <div>
            <span>计划</span>
            <strong>{{ task.schedule }}</strong>
          </div>
          <div>
            <span>数据源</span>
            <strong>{{ task.source }}</strong>
          </div>
          <div>
            <span>最近运行</span>
            <strong>{{ task.last_run_at ?? '尚未运行' }}</strong>
          </div>
          <div>
            <span>下次计划</span>
            <strong>{{ task.next_run_at ?? '手动触发' }}</strong>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.providers-grid,
.tasks-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.scheduler-alert {
  margin-bottom: 20px;
}

.provider-summary-card {
  grid-column: 1 / -1;
}

.task-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.task-top h3 {
  margin: 0;
}

.task-top p {
  margin: 10px 0 0;
  line-height: 1.65;
  color: var(--text-soft);
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 20px;
}

.meta-grid span {
  display: block;
  color: var(--text-faint);
  margin-bottom: 4px;
}

@media (max-width: 720px) {
  .meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
