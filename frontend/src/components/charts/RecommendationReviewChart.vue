<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { RecommendationReviewRun } from '@/types/market'

use([BarChart, CanvasRenderer, GridComponent, LineChart, TooltipComponent])

const props = defineProps<{
  runs: RecommendationReviewRun[]
}>()

const option = computed(() => ({
  color: ['#0f766e', '#ea580c'],
  tooltip: {
    trigger: 'axis',
  },
  grid: {
    top: 28,
    left: 24,
    right: 18,
    bottom: 24,
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    data: [...props.runs].reverse().map((run) => run.generated_at.slice(5, 10)),
    axisLine: {
      lineStyle: {
        color: 'rgba(31, 42, 55, 0.16)',
      },
    },
  },
  yAxis: [
    {
      type: 'value',
      name: '收益',
      splitLine: {
        lineStyle: {
          color: 'rgba(31, 42, 55, 0.08)',
        },
      },
    },
    {
      type: 'value',
      name: '评分',
      min: 0,
      max: 100,
      splitLine: {
        show: false,
      },
    },
  ],
  series: [
    {
      name: '平均预期收益',
      type: 'bar',
      data: [...props.runs].reverse().map((run) => run.avg_expected_return),
      itemStyle: {
        color: 'rgba(15, 118, 110, 0.7)',
        borderRadius: [8, 8, 0, 0],
      },
    },
    {
      name: '平均评分',
      type: 'line',
      smooth: true,
      yAxisIndex: 1,
      data: [...props.runs].reverse().map((run) => run.avg_score),
      lineStyle: {
        width: 3,
      },
    },
  ],
}))
</script>

<template>
  <VChart class="chart" :option="option" autoresize />
</template>

<style scoped>
.chart {
  width: 100%;
  min-height: 320px;
}
</style>
