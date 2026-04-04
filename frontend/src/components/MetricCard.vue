<script setup lang="ts">
import { computed } from 'vue'
import type { MetricCard as MetricCardType } from '@/types/market'

const props = defineProps<{
  metric: MetricCardType
}>()

const toneClass = computed(() => {
  if (props.metric.tone === 'positive') {
    return 'stat-positive'
  }
  if (props.metric.tone === 'negative') {
    return 'stat-negative'
  }
  return 'stat-neutral'
})
</script>

<template>
  <el-card class="metric-card">
    <p class="metric-label">{{ metric.label }}</p>
    <div class="metric-row">
      <strong>{{ metric.value }}</strong>
      <span :class="toneClass">{{ metric.change }}</span>
    </div>
    <p class="metric-description">{{ metric.description }}</p>
  </el-card>
</template>

<style scoped>
.metric-card {
  min-height: 154px;
}

.metric-label {
  margin: 0 0 16px;
  color: var(--text-faint);
}

.metric-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

strong {
  font-size: 30px;
  font-family: var(--font-heading);
  color: var(--text);
}

.metric-description {
  margin: 16px 0 0;
  line-height: 1.65;
  color: var(--text-soft);
}
</style>
