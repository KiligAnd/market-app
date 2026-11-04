<script setup>
defineProps({
  text: { type: String, default: '' },
  type: { type: String, default: 'info' }
})

const classMap = {
  success: 'status-success',
  warning: 'status-warning',
  info: 'status-info',
  danger: 'status-danger'
}
</script>

<template>
  <span class="status-tag" :class="classMap[type] || classMap.info">{{ text }}</span>
</template>
