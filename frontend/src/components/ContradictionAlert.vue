<template>
  <div class="contradiction-alert" v-if="contradictions.length > 0">
    <div class="alert-header">
      <span class="alert-icon">!</span>
      <span class="alert-title">{{ contradictions.length }} Contradiction{{ contradictions.length > 1 ? 's' : '' }} Detected</span>
    </div>
    <div
      v-for="(c, idx) in contradictions"
      :key="idx"
      class="contradiction-item"
      :class="`severity-${c.severity}`"
    >
      <div class="contradiction-events">
        <span class="event-label">{{ c.event_a }}</span>
        <span class="vs">vs</span>
        <span class="event-label">{{ c.event_b }}</span>
      </div>
      <div class="contradiction-meta">
        <span class="severity-badge" :class="`badge-${c.severity}`">{{ c.severity }}</span>
        <span class="recommendation">{{ c.recommendation }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  contradictions: { type: Array, default: () => [] },
})
</script>

<style scoped>
.contradiction-alert {
  margin: 1rem 0;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 8px;
  background: rgba(248, 113, 113, 0.05);
  padding: 0.75rem;
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.alert-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f87171;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: bold;
}

.alert-title {
  color: #f87171;
  font-size: 0.85rem;
  font-weight: 600;
}

.contradiction-item {
  padding: 0.5rem;
  border-radius: 6px;
  margin-bottom: 0.5rem;
  border-left: 3px solid;
}

.severity-high { border-color: #ef4444; background: rgba(239, 68, 68, 0.05); }
.severity-medium { border-color: #f59e0b; background: rgba(245, 158, 11, 0.05); }
.severity-low { border-color: #6b7280; background: rgba(107, 114, 128, 0.05); }

.contradiction-events {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.3rem;
}

.event-label {
  font-size: 0.8rem;
  color: #ddd;
}

.vs {
  font-size: 0.65rem;
  color: #888;
  text-transform: uppercase;
}

.contradiction-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.severity-badge {
  font-size: 0.6rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  text-transform: uppercase;
  font-family: 'JetBrains Mono', monospace;
}
.badge-high { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.badge-medium { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
.badge-low { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }

.recommendation {
  font-size: 0.7rem;
  color: #888;
}
</style>
