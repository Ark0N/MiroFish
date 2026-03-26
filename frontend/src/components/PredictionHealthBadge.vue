<template>
  <div class="health-badge" :class="statusClass">
    <span class="health-dot"></span>
    <span class="health-label">{{ statusLabel }}</span>
    <span class="health-detail" v-if="showDetail">
      {{ decayFactor }}x | {{ daysText }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  healthStatus: { type: String, default: 'fresh' },
  decayFactor: { type: Number, default: 1.0 },
  daysSinceEvidence: { type: Number, default: 0 },
  evidenceCount: { type: Number, default: 0 },
  showDetail: { type: Boolean, default: true },
})

const statusClass = computed(() => `status-${props.healthStatus}`)

const statusLabel = computed(() => {
  const labels = {
    fresh: 'Fresh',
    aging: 'Aging',
    stale: 'Stale',
    boosted: 'Boosted',
  }
  return labels[props.healthStatus] || props.healthStatus
})

const daysText = computed(() => {
  if (props.daysSinceEvidence < 1) return 'today'
  if (props.daysSinceEvidence < 2) return '1d ago'
  return `${Math.round(props.daysSinceEvidence)}d ago`
})
</script>

<style scoped>
.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', monospace;
  border: 1px solid;
}

.health-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-fresh {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.3);
  color: #4ade80;
}
.status-fresh .health-dot { background: #4ade80; }

.status-boosted {
  background: rgba(96, 165, 250, 0.1);
  border-color: rgba(96, 165, 250, 0.3);
  color: #60a5fa;
}
.status-boosted .health-dot { background: #60a5fa; }

.status-aging {
  background: rgba(251, 191, 36, 0.1);
  border-color: rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}
.status-aging .health-dot { background: #fbbf24; }

.status-stale {
  background: rgba(248, 113, 113, 0.1);
  border-color: rgba(248, 113, 113, 0.3);
  color: #f87171;
}
.status-stale .health-dot { background: #f87171; }

.health-detail {
  color: #888;
  font-size: 0.65rem;
}
</style>
