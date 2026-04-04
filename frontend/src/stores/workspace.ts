import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getHealthStatus } from '@/api/market'
import type { HealthStatus } from '@/types/market'

export const useWorkspaceStore = defineStore('workspace', () => {
  const health = ref<HealthStatus | null>(null)
  const loading = ref(false)

  const backendReady = computed(() => health.value?.status === 'ok')
  const modeLabel = computed(() => health.value?.mode ?? 'demo')
  const schedulerEnabled = computed(() => health.value?.scheduler_enabled ?? false)

  async function refreshHealth() {
    loading.value = true
    try {
      health.value = await getHealthStatus()
    } finally {
      loading.value = false
    }
  }

  return {
    backendReady,
    health,
    loading,
    modeLabel,
    schedulerEnabled,
    refreshHealth,
  }
})
