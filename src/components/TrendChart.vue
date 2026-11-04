<script setup>
import { computed } from 'vue'

const props = defineProps({
  series: { type: Array, default: () => [] }
})

const W = 960
const H = 300
const PL = 64
const PR = 20
const PT = 20
const PB = 34

const fmt = (value) => Math.round(value).toLocaleString('en-US')

const layout = computed(() => {
  if (!props.series.length) return null

  const plotW = W - PL - PR
  const plotH = H - PT - PB
  const values = props.series.map((item) => Number(item.avg))
  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const pad = Math.max((maxV - minV) * 0.12, 60)
  const step =
    [100, 200, 250, 500, 1000, 2000].find(
      (candidate) => (maxV + pad - (minV - pad)) / candidate <= 6
    ) || 2000
  const lo = Math.floor((minV - pad) / step) * step
  const hi = Math.ceil((maxV + pad) / step) * step

  const x = (index) =>
    PL + (props.series.length === 1 ? plotW / 2 : (index / (props.series.length - 1)) * plotW)
  const y = (value) => PT + ((hi - value) / (hi - lo)) * plotH

  const ticks = []
  for (let value = lo; value <= hi; value += step) {
    ticks.push({ value, y: y(value), label: fmt(value) })
  }

  const lastIndex = props.series.length - 1
  const labelStep = Math.max(1, Math.ceil(lastIndex / 5))
  const xLabels = []
  for (let index = 0; index < props.series.length; index += labelStep) {
    xLabels.push({
      x: x(index),
      label: props.series[index].date.slice(5),
      anchor: 'middle'
    })
  }
  if (lastIndex % labelStep !== 0) {
    xLabels.push({
      x: x(lastIndex),
      label: props.series[lastIndex].date.slice(5),
      anchor: 'end'
    })
  }

  const points = props.series.map((item, index) => ({
    x: x(index),
    y: y(Number(item.avg)),
    title: `${item.date} · 均价 ${fmt(item.avg)} 元/吨`
  }))

  const linePath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(' ')
  const bottom = (PT + plotH).toFixed(1)
  const areaPath = props.series.length > 1
    ? `${linePath} L${x(lastIndex).toFixed(1)} ${bottom} L${PL} ${bottom} Z`
    : ''
  const lastPoint = points[points.length - 1]

  return { ticks, xLabels, points, linePath, areaPath, lastPoint, lastValue: values[lastIndex] }
})
</script>

<template>
  <svg
    v-if="layout"
    class="trend-chart"
    :viewBox="`0 0 ${W} ${H}`"
    role="img"
    aria-label="行情价格趋势"
  >
    <defs>
      <linearGradient id="trendArea" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#1e88e5" stop-opacity="0.2" />
        <stop offset="100%" stop-color="#1e88e5" stop-opacity="0.02" />
      </linearGradient>
    </defs>

    <g v-for="tick in layout.ticks" :key="`tick-${tick.value}`">
      <line
        :x1="PL"
        :y1="tick.y"
        :x2="W - PR"
        :y2="tick.y"
        stroke="#eef4fa"
        stroke-width="1"
      />
      <text
        :x="PL - 10"
        :y="tick.y + 4"
        text-anchor="end"
        font-size="12"
        fill="#999"
      >
        {{ tick.label }}
      </text>
    </g>

    <text
      v-for="label in layout.xLabels"
      :key="`x-${label.label}-${label.x}`"
      :x="label.x"
      :y="H - 12"
      :text-anchor="label.anchor"
      font-size="12"
      fill="#999"
    >
      {{ label.label }}
    </text>

    <path v-if="layout.areaPath" :d="layout.areaPath" fill="url(#trendArea)" />
    <path
      :d="layout.linePath"
      fill="none"
      stroke="#1e88e5"
      stroke-width="2.5"
      stroke-linejoin="round"
      stroke-linecap="round"
    />

    <circle
      v-for="(point, index) in layout.points"
      :key="`point-${index}`"
      :cx="point.x"
      :cy="point.y"
      r="8"
      fill="transparent"
      pointer-events="all"
    >
      <title>{{ point.title }}</title>
    </circle>

    <circle
      :cx="layout.lastPoint.x"
      :cy="layout.lastPoint.y"
      r="4.5"
      fill="#fff"
      stroke="#1e88e5"
      stroke-width="2.5"
    />
    <text
      :x="layout.lastPoint.x - 8"
      :y="layout.lastPoint.y - 12"
      text-anchor="end"
      font-size="13"
      font-weight="600"
      fill="#1e88e5"
    >
      {{ fmt(layout.lastValue) }}
    </text>
  </svg>
</template>
