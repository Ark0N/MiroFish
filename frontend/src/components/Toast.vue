<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast-item"
        :class="'toast-' + toast.type"
      >
        <span class="toast-icon">{{ iconFor(toast.type) }}</span>
        <span class="toast-message">{{ toast.message }}</span>
        <button class="toast-close" @click="removeToast(toast.id)">&times;</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useToast } from '@/composables/useToast'

const { toasts, removeToast } = useToast()

function iconFor(type) {
  switch (type) {
    case 'success': return '\u2713'
    case 'error': return '\u2717'
    case 'warning': return '\u26A0'
    case 'info': return '\u2139'
    default: return '\u2139'
  }
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 420px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-radius: 8px;
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
  font-size: 14px;
  line-height: 1.4;
  color: #f0f0f0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  pointer-events: auto;
  min-width: 280px;
}

.toast-success {
  background-color: #1a3a2a;
  border-left: 4px solid #4ade80;
}

.toast-error {
  background-color: #3a1a1a;
  border-left: 4px solid #f87171;
}

.toast-warning {
  background-color: #3a2f1a;
  border-left: 4px solid #fbbf24;
}

.toast-info {
  background-color: #1a2a3a;
  border-left: 4px solid #60a5fa;
}

.toast-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  word-break: break-word;
}

.toast-close {
  background: none;
  border: none;
  color: #999;
  font-size: 20px;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  flex-shrink: 0;
  transition: color 0.2s;
}

.toast-close:hover {
  color: #fff;
}

/* Transition animations */
.toast-enter-active {
  transition: all 0.3s ease-out;
}

.toast-leave-active {
  transition: all 0.25s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}

.toast-move {
  transition: transform 0.3s ease;
}
</style>
