import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getHealthStatus } from '@/api/market'
import type { HealthStatus } from '@/types/market'
import {
  MARKET_OPTIONS,
  type MarketScope,
  marketLabel,
  readStoredMarket,
  writeStoredMarket,
} from '@/utils/market'

export const useWorkspaceStore = defineStore('workspace', () => {
  const health = ref<HealthStatus | null>(null)
  const loading = ref(false)
  const selectedMarket = ref<MarketScope>(readStoredMarket())

  const backendReady = computed(() => health.value?.status === 'ok')
  const modeLabel = computed(() => health.value?.mode ?? 'demo')
  const schedulerEnabled = computed(() => health.value?.scheduler_enabled ?? false)
  const currentMarketLabel = computed(() => marketLabel(selectedMarket.value))

  async function refreshHealth() {
    loading.value = true
    try {
      health.value = await getHealthStatus()
    } finally {
      loading.value = false
    }
  }

  function setMarket(nextMarket: MarketScope) {
    selectedMarket.value = nextMarket
    writeStoredMarket(nextMarket)
  }

  return {
    backendReady,
    currentMarketLabel,
    health,
    loading,
    marketOptions: MARKET_OPTIONS,
    modeLabel,
    schedulerEnabled,
    selectedMarket,
    setMarket,
    refreshHealth,
  }
})
