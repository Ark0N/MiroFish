<template>
  <div class="diff-table" v-if="diffs.length > 0">
    <h3 class="diff-title">Prediction Changes Between Reports</h3>
    <div class="diff-list">
      <div
        v-for="(diff, idx) in diffs"
        :key="idx"
        class="diff-row"
      >
        <div class="diff-event">{{ diff.event }}</div>
        <div class="diff-metrics">
          <div class="metric-pair">
            <span class="metric-label">Probability</span>
            <span class="metric-old">{{ (diff.base_probability * 100).toFixed(0) }}%</span>
            <span class="metric-arrow" :class="deltaClass(diff.probability_delta)">
              {{ diff.probability_delta > 0 ? '+' : '' }}{{ (diff.probability_delta * 100).toFixed(1) }}%
            </span>
            <span class="metric-new">{{ (diff.compare_probability * 100).toFixed(0) }}%</span>
          </div>
          <div class="metric-pair">
            <span class="metric-label">Agreement</span>
            <span class="metric-old">{{ (diff.base_agreement * 100).toFixed(0) }}%</span>
            <span class="metric-arrow" :class="deltaClass(diff.agreement_delta)">
              {{ diff.agreement_delta > 0 ? '+' : '' }}{{ (diff.agreement_delta * 100).toFixed(1) }}%
            </span>
            <span class="metric-new">{{ (diff.compare_agreement * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="diff-empty">
    No matching predictions found between selected reports.
  </div>
</template>

<script setup>
defineProps({
  diffs: { type: Array, default: () => [] },
})

const deltaClass = (delta) => {
  if (delta > 0.05) return 'delta-up'
  if (delta < -0.05) return 'delta-down'
  return 'delta-flat'
}
</script>

<style scoped>
.diff-table { margin: 1rem 0; }

.diff-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  color: #e0e0e0;
  margin-bottom: 0.75rem;
}

.diff-list { display: flex; flex-direction: column; gap: 0.5rem; }

.diff-row {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
}

.diff-event {
  font-size: 0.85rem;
  color: #ddd;
  margin-bottom: 0.4rem;
}

.diff-metrics { display: flex; gap: 1.5rem; }

.metric-pair {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', monospace;
}

.metric-label {
  color: #666;
  min-width: 65px;
}

.metric-old { color: #888; }
.metric-new { color: #ddd; font-weight: 600; }

.metric-arrow {
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-weight: 600;
}

.delta-up { color: #4ade80; background: rgba(74, 222, 128, 0.1); }
.delta-down { color: #f87171; background: rgba(248, 113, 113, 0.1); }
.delta-flat { color: #888; background: rgba(136, 136, 136, 0.1); }

.diff-empty {
  color: #666;
  font-size: 0.8rem;
  text-align: center;
  padding: 1rem;
}
</style>
