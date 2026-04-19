<script setup lang="ts">
import {
  Bell,
  Clock,
  CollectionTag,
  DataAnalysis,
  DataBoard,
  DataLine,
  Histogram,
  MagicStick,
  Setting,
} from '@element-plus/icons-vue'
import { computed, onMounted } from 'vue'
import dayjs from 'dayjs'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const router = useRouter()
const workspaceStore = useWorkspaceStore()

const menuItems = [
  { path: '/', label: '市场看板', icon: DataBoard },
  { path: '/alerts', label: '提醒中心', icon: Bell },
  { path: '/stocks', label: '股票列表', icon: DataLine },
  { path: '/recommendations', label: '推荐中心', icon: MagicStick },
  { path: '/review', label: '推荐复盘', icon: Histogram },
  { path: '/trade-plans', label: '交易计划', icon: DataAnalysis },
  { path: '/portfolio', label: '组合持仓', icon: Histogram },
  { path: '/watchlist', label: '自选池', icon: CollectionTag },
  { path: '/strategy', label: '策略配置', icon: Setting },
  { path: '/tasks', label: '数据任务', icon: Clock },
]

const pageTitle = computed(() => String(route.meta.title ?? 'Stock Pilot'))
const todayLabel = computed(() => dayjs().format('YYYY年MM月DD日'))
const routerViewKey = computed(() => route.fullPath)

function openTasksPage() {
  void router.push('/tasks')
}

onMounted(() => {
  void workspaceStore.refreshHealth()
})
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="shell-aside" width="252px">
      <div class="brand-card">
        <div class="brand-mark">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div>
          <p class="eyebrow">本地量化工作台</p>
          <h1>Stock Pilot</h1>
          <p class="brand-copy">面向个人研究的 A 股数据、评分和推荐系统。</p>
        </div>
      </div>

      <div class="aside-panel market-panel">
        <span class="panel-label">研究范围</span>
        <strong>{{ workspaceStore.currentMarketLabel }}</strong>
        <span class="panel-hint">聚焦沪深 A 股的日常研究与跟踪。</span>
      </div>

      <el-menu :default-active="route.path" class="nav-menu" router>
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>

      <div class="aside-panel">
        <span class="panel-label">后端状态</span>
        <strong>{{ workspaceStore.backendReady ? '已连接' : '待检查' }}</strong>
        <span class="panel-hint">模式：{{ workspaceStore.modeLabel }}</span>
        <el-button text type="primary" @click="workspaceStore.refreshHealth">
          刷新状态
        </el-button>
      </div>
    </el-aside>

    <el-container>
      <el-header class="shell-header">
        <div>
          <p class="eyebrow page-eyebrow">{{ workspaceStore.currentMarketLabel }}分析系统</p>
          <h2>{{ pageTitle }}</h2>
        </div>

        <div class="header-actions">
          <div class="header-tag">
            <span>{{ todayLabel }}</span>
          </div>
          <el-button type="primary" @click="openTasksPage">运行同步</el-button>
        </div>
      </el-header>

      <el-main class="shell-main">
        <RouterView :key="routerViewKey" />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.shell-aside {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 20px;
  background:
    linear-gradient(180deg, rgba(12, 74, 110, 0.92) 0%, rgba(15, 118, 110, 0.92) 100%);
  color: #f8fcff;
}

.brand-card {
  display: grid;
  gap: 16px;
  padding: 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.brand-mark {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  font-size: 28px;
  background: rgba(255, 255, 255, 0.18);
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.68);
}

.page-eyebrow {
  color: var(--text-faint);
}

.brand-card h1,
.shell-header h2 {
  margin: 0;
  font-family: var(--font-heading);
  letter-spacing: 0.03em;
}

.brand-copy {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.78);
}

.nav-menu {
  flex: 1;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.08);
}

.nav-menu :deep(.el-menu-item) {
  margin: 8px;
  border-radius: 14px;
  color: rgba(255, 255, 255, 0.78);
}

.nav-menu :deep(.el-menu-item.is-active) {
  color: #0f172a;
  background: #f8fcff;
}

.aside-panel {
  display: grid;
  gap: 4px;
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.08);
}

.panel-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.68);
}

.panel-hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.72);
}

.shell-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 28px 32px 18px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-tag {
  padding: 11px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--border);
  color: var(--text-soft);
}

.shell-main {
  padding: 0 32px 32px;
}

@media (max-width: 1120px) {
  .app-shell {
    flex-direction: column;
  }

  .shell-aside {
    width: 100%;
  }
}

@media (max-width: 720px) {
  .shell-header {
    flex-direction: column;
    align-items: flex-start;
    padding-inline: 18px;
  }

  .shell-main {
    padding-inline: 18px;
  }

  .header-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
