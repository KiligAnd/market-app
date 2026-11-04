<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择' },
  searchable: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  emptyText: { type: String, default: '没有匹配的选项' }
})

const emit = defineEmits(['update:modelValue', 'change'])
const open = ref(false)
const keyword = ref('')
const rootRef = ref(null)
const searchRef = ref(null)

const normalizedOptions = computed(() =>
  props.options.map((item) => {
    if (item && typeof item === 'object') {
      return {
        value: item.value,
        label: item.label ?? String(item.value ?? ''),
        description: item.description || '',
        tag: item.tag || '',
        disabled: Boolean(item.disabled)
      }
    }
    return { value: item, label: String(item ?? ''), description: '', tag: '', disabled: false }
  })
)

const selected = computed(() =>
  normalizedOptions.value.find((item) => String(item.value) === String(props.modelValue)) || null
)

const filteredOptions = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!props.searchable || !text) return normalizedOptions.value
  return normalizedOptions.value.filter((item) =>
    `${item.label} ${item.description}`.toLowerCase().includes(text)
  )
})

function toggle() {
  if (props.disabled) return
  if (open.value) {
    open.value = false
    return
  }
  keyword.value = ''
  open.value = true
  if (props.searchable) {
    nextTick(() => searchRef.value?.focus())
  }
}

function choose(option) {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
  open.value = false
  keyword.value = ''
}

function handleDocumentClick(event) {
  if (!open.value) return
  if (rootRef.value && !rootRef.value.contains(event.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', handleDocumentClick))
onUnmounted(() => document.removeEventListener('click', handleDocumentClick))
</script>

<template>
  <div ref="rootRef" class="app-select" :class="{ open, disabled }">
    <button
      type="button"
      class="app-select-trigger"
      :class="{ open }"
      :disabled="disabled"
      @click="toggle"
    >
      <span v-if="selected" class="app-select-value" :title="selected.label">
        {{ selected.label }}
      </span>
      <span v-else class="app-select-placeholder">{{ placeholder }}</span>
      <span class="app-select-arrow">▾</span>
    </button>

    <div v-if="open" class="app-select-panel">
      <div v-if="searchable" class="app-select-search">
        <input ref="searchRef" v-model="keyword" placeholder="搜索" />
      </div>
      <div class="app-select-options">
        <button
          v-for="option in filteredOptions"
          :key="String(option.value)"
          type="button"
          class="app-select-option"
          :class="{ active: String(option.value) === String(modelValue), disabled: option.disabled }"
          :disabled="option.disabled"
          @click="choose(option)"
        >
          <span class="app-select-main">
            <strong>{{ option.label }}</strong>
            <small v-if="option.description">{{ option.description }}</small>
          </span>
          <span v-if="option.tag" class="app-select-tag">{{ option.tag }}</span>
          <span
            v-if="String(option.value) === String(modelValue)"
            class="app-select-check"
          >✓</span>
        </button>
        <div v-if="!filteredOptions.length" class="app-select-empty">{{ emptyText }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-select {
  position: relative;
  width: 100%;
  z-index: 30;
}

.app-select-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #d0e3f7;
  border-radius: 6px;
  background: #fff;
  color: #4a5f75;
  font: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.app-select-trigger:not(:disabled):hover,
.app-select-trigger.open {
  border-color: #1e88e5;
  box-shadow: 0 0 0 2px rgba(30, 136, 229, 0.12);
}

.app-select-trigger:disabled {
  border-color: #e3edf7;
  background: #f7f9fc;
  color: #a9bccd;
  cursor: not-allowed;
}

.app-select-value {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select-placeholder {
  flex: 1;
  color: #9bb0c5;
}

.app-select-arrow {
  color: #8aa0b6;
  font-size: 11px;
  flex: 0 0 auto;
}

.app-select-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 40;
  width: 100%;
  min-width: 180px;
  max-width: 320px;
  border: 1px solid #dbeaf9;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(26, 58, 92, 0.14);
}

.app-select-search {
  padding: 6px;
  border-bottom: 1px solid #eef4fa;
}

.app-select-search input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #d0e3f7;
  border-radius: 4px;
  font-size: 12px;
}

.app-select-options {
  display: grid;
  gap: 4px;
  max-height: 220px;
  overflow: auto;
  padding: 6px;
}

.app-select-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 9px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: #fff;
  color: #1a3a5c;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.app-select-option:hover {
  background: #f5faff;
  border-color: #dbeaf9;
}

.app-select-option.active {
  border-color: #1e88e5;
  background: #eef7ff;
}

.app-select-option.disabled {
  color: #a9bccd;
  background: #f7f9fc;
  cursor: not-allowed;
}

.app-select-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.app-select-main strong {
  font-size: 12px;
  font-weight: 600;
}

.app-select-main small {
  color: #7b8ea6;
  font-size: 11px;
}

.app-select-tag {
  padding: 1px 5px;
  border-radius: 3px;
  background: #fff3e0;
  color: #e65100;
  font-size: 10px;
  flex: 0 0 auto;
}

.app-select-check {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #1e88e5;
  color: #fff;
  font-size: 10px;
  flex: 0 0 16px;
}

.app-select-empty {
  padding: 10px;
  color: #8aa0b6;
  font-size: 11px;
  text-align: center;
}
</style>
