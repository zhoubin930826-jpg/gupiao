<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { PricePoint } from '@/types/market'

use([
  BarChart,
  CanvasRenderer,
  CandlestickChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  TooltipComponent,
])

const props = defineProps<{
  points: PricePoint[]
}>()

const option = computed(() => ({
  legend: {
    top: 6,
  },
  tooltip: {
    trigger: 'axis',
  },
  grid: [
    {
      left: 16,
      right: 16,
      top: 48,
      height: '58%',
      containLabel: true,
    },
    {
      left: 16,
      right: 16,
      top: '74%',
      height: '18%',
      containLabel: true,
    },
  ],
  xAxis: [
    {
      type: 'category',
      data: props.points.map((point) => point.date.slice(5)),
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: 'rgba(31, 42, 55, 0.16)',
        },
      },
    },
    {
      type: 'category',
      gridIndex: 1,
      data: props.points.map((point) => point.date.slice(5)),
      boundaryGap: false,
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
    },
  ],
  yAxis: [
    {
      scale: true,
      splitLine: {
        lineStyle: {
          color: 'rgba(31, 42, 55, 0.08)',
        },
      },
    },
    {
      gridIndex: 1,
      scale: true,
      splitLine: { show: false },
    },
  ],
  dataZoom: [
    {
      type: 'inside',
      xAxisIndex: [0, 1],
      start: 40,
      end: 100,
    },
  ],
  series: [
    {
      name: 'K线',
      type: 'candlestick',
      data: props.points.map((point) => [
        point.open,
        point.close,
        point.low,
        point.high,
      ]),
      itemStyle: {
        color: '#0f766e',
        color0: '#ea580c',
        borderColor: '#0f766e',
        borderColor0: '#ea580c',
      },
    },
    {
      name: 'MA5',
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: props.points.map((point) => point.ma5),
      lineStyle: {
        width: 1.4,
        color: '#155e75',
      },
    },
    {
      name: 'MA20',
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: props.points.map((point) => point.ma20),
      lineStyle: {
        width: 1.4,
        color: '#d97706',
      },
    },
    {
      name: '成交量',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: props.points.map((point) => point.volume),
      itemStyle: {
        color: 'rgba(15, 118, 110, 0.28)',
        borderRadius: [6, 6, 0, 0],
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
  min-height: 420px;
}
</style>
