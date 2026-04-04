<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listTasks, triggerMarketSync } from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { SyncTask } from '@/types/market'

const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const syncSubmitting = ref(false)
const tasks = ref<SyncTask[]>([])
let pollTimer: number | null = null

async function loadTasks(showLoading = true) {
  if (showLoading) {
    loading.value = true
  }
  try {
    tasks.value = await listTasks()
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
      description="数据任务页会告诉你什么时候自动同步、用的是什么数据源、最近一次任务结果如何。你也可以随时手动提交一次同步，把计划内和计划外动作放在同一个入口管理。"
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
.tasks-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.scheduler-alert {
  margin-bottom: 20px;
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
