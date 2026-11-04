<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  sub: { type: String, default: '' },
  subColor: { type: String, default: '' }
})
</script>

<template>
  <div class="stat-card">
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
    <div v-if="sub" class="sub" :style="subColor ? { color: subColor } : undefined">
      {{ sub }}
    </div>
  </div>
</template>
