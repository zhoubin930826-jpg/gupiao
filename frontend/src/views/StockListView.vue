<script setup lang="ts">
import { Star } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { addToWatchlist, listStocks, removeFromWatchlist } from '@/api/market'
import PageHeader from '@/components/PageHeader.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import type { StockItem } from '@/types/market'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const togglingSymbol = ref<string | null>(null)
const total = ref(0)
const rows = ref<StockItem[]>([])

const filters = reactive({
  keyword: '',
  board: '全部',
})

const boardOptions = computed(() => {
  if (workspaceStore.selectedMarket === 'hk') {
    return [
      { label: '全部板块', value: '全部' },
      { label: '港股主板', value: '港股主板' },
    ]
  }
  if (workspaceStore.selectedMarket === 'us') {
    return [
      { label: '全部交易所', value: '全部' },
      { label: 'NASDAQ', value: 'NASDAQ' },
      { label: 'NYSE', value: 'NYSE' },
      { label: 'AMEX', value: 'AMEX' },
    ]
  }
  return [
    { label: '全部板块', value: '全部' },
    { label: '主板', value: '主板' },
    { label: '创业板', value: '创业板' },
    { label: '科创板', value: '科创板' },
  ]
})

async function loadStocks() {
  loading.value = true
  try {
    const response = await listStocks({
      keyword: filters.keyword || undefined,
      board: filters.board,
      page: 1,
      page_size: 50,
    })
    rows.value = response.rows
    total.value = response.total
  } finally {
    loading.value = false
  }
}

function openDetail(symbol: string) {
  void router.push(`/stocks/${symbol}`)
}

function handleRowClick(row: StockItem) {
  openDetail(row.symbol)
}

async function toggleWatchlist(row: StockItem) {
  togglingSymbol.value = row.symbol
  try {
    if (row.in_watchlist) {
      await removeFromWatchlist(row.symbol)
      row.in_watchlist = false
      ElMessage.success('已移出自选池。')
      return
    }

    await addToWatchlist({
      symbol: row.symbol,
      source: 'manual',
    })
    row.in_watchlist = true
    ElMessage.success('已加入自选池。')
  } finally {
    togglingSymbol.value = null
  }
}

onMounted(() => {
  void loadStocks()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="先圈定股票池，再进入个股级别的分析"
      description="列表页负责做初筛。这里先放基础过滤、评分排序和主题标签，后面你可以继续加龙虎榜、资金流、财报事件或自选池维度。"
    >
      <template #actions>
        <el-button plain @click="loadStocks">刷新列表</el-button>
      </template>
    </PageHeader>

    <el-card class="panel-card">
      <div class="filter-grid">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="输入股票代码或名称"
          @keyup.enter="loadStocks"
        />
        <el-select v-model="filters.board">
          <el-option
            v-for="option in boardOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button type="primary" @click="loadStocks">开始筛选</el-button>
        <div class="summary-chip">
          当前结果 <span class="mono">{{ total }}</span> 只
        </div>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table :data="rows" v-loading="loading" @row-click="handleRowClick">
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="industry" label="行业" width="120" />
        <el-table-column prop="board" label="板块" width="100" />
        <el-table-column label="最新价" width="120">
          <template #default="{ row }">
            {{ row.latest_price.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="110">
          <template #default="{ row }">
            <span :class="row.change_pct >= 0 ? 'stat-positive' : 'stat-negative'">
              {{ row.change_pct.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="换手率" width="110">
          <template #default="{ row }">
            {{ row.turnover_ratio.toFixed(2) }}%
          </template>
        </el-table-column>
        <el-table-column label="PE(TTM)" width="110">
          <template #default="{ row }">
            {{ row.pe_ttm.toFixed(1) }}
          </template>
        </el-table-column>
        <el-table-column label="评分" width="100">
          <template #default="{ row }">
            <el-tag type="success">{{ row.score }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="自选" width="96">
          <template #default="{ row }">
            <el-button
              circle
              :icon="Star"
              :type="row.in_watchlist ? 'warning' : 'default'"
              :loading="togglingSymbol === row.symbol"
              @click.stop="toggleWatchlist(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <div class="tag-wrap">
              <el-tag v-for="tag in row.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="thesis" label="一句话结论" min-width="260" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.filter-grid {
  display: grid;
  grid-template-columns: 1.4fr 0.9fr auto auto;
  gap: 14px;
  align-items: center;
}

.summary-chip {
  justify-self: end;
  padding: 11px 14px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 960px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .summary-chip {
    justify-self: start;
  }
}
</style>
