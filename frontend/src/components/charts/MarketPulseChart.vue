<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { MarketPulsePoint } from '@/types/market'

use([BarChart, CanvasRenderer, GridComponent, LegendComponent, LineChart, TooltipComponent])

const props = defineProps<{
  points: MarketPulsePoint[]
}>()

const option = computed(() => ({
  color: ['#0f766e', '#ea580c'],
  tooltip: {
    trigger: 'axis',
  },
  legend: {
    top: 8,
    textStyle: {
      color: '#5c6a77',
    },
  },
  grid: {
    top: 58,
    left: 24,
    right: 18,
    bottom: 24,
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.points.map((point) => point.date.slice(5)),
    axisLine: {
      lineStyle: {
        color: 'rgba(31, 42, 55, 0.16)',
      },
    },
  },
  yAxis: [
    {
      type: 'value',
      name: '评分',
      min: 0,
      max: 100,
      splitLine: {
        lineStyle: {
          color: 'rgba(31, 42, 55, 0.08)',
        },
      },
    },
    {
      type: 'value',
      name: '成交额',
      splitLine: {
        show: false,
      },
    },
  ],
  series: [
    {
      name: '市场评分',
      type: 'line',
      smooth: true,
      data: props.points.map((point) => point.score),
      areaStyle: {
        color: 'rgba(15, 118, 110, 0.12)',
      },
    },
    {
      name: '成交额',
      type: 'bar',
      yAxisIndex: 1,
      data: props.points.map((point) => point.turnover),
      itemStyle: {
        color: 'rgba(234, 88, 12, 0.26)',
        borderRadius: [8, 8, 0, 0],
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
