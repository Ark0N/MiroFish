<template>
  <div class="scenario-compare" v-if="scenarios">
    <h3 class="compare-title">Scenario Analysis</h3>
    <div class="scenario-cards">
      <div
        v-for="scenario in displayScenarios"
        :key="scenario.scenario_id"
        class="scenario-card"
        :class="scenario.label"
      >
        <div class="scenario-header">
          <span class="scenario-label">{{ formatLabel(scenario.label) }}</span>
          <span class="scenario-prob">{{ (scenario.joint_probability * 100).toFixed(1) }}%</span>
        </div>
        <div class="scenario-bar-container">
          <div
            class="scenario-bar"
            :style="{ width: Math.max(2, scenario.joint_probability * 100) + '%' }"
          ></div>
        </div>
        <div class="scenario-events">
          <div
            v-for="node in scenario.nodes"
            :key="node.prediction_idx"
            class="event-row"
          >
            <span class="event-outcome" :class="node.outcome ? 'yes' : 'no'">
              {{ node.outcome ? 'Y' : 'N' }}
            </span>
            <span class="event-name">{{ node.event }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="scenario-footer" v-if="scenarios.total_scenarios > 3">
      {{ scenarios.total_scenarios }} total scenarios from {{ scenarios.num_predictions }} predictions
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  scenarios: { type: Object, default: null },
})

const displayScenarios = computed(() => {
  if (!props.scenarios) return []
  const items = []
  if (props.scenarios.best_case) items.push(props.scenarios.best_case)
  if (props.scenarios.most_likely) items.push(props.scenarios.most_likely)
  if (props.scenarios.worst_case) items.push(props.scenarios.worst_case)
  return items
})

const formatLabel = (label) => {
  const labels = {
    best_case: 'Best Case',
    worst_case: 'Worst Case',
    most_likely: 'Most Likely',
  }
  return labels[label] || label
}
</script>

<style scoped>
.scenario-compare {
  margin: 1.5rem 0;
}

.compare-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  margin-bottom: 0.75rem;
  color: #e0e0e0;
}

.scenario-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
}

.scenario-card {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 8px;
  padding: 0.75rem;
}

.scenario-card.best_case { border-top: 3px solid #4ade80; }
.scenario-card.most_likely { border-top: 3px solid #60a5fa; }
.scenario-card.worst_case { border-top: 3px solid #f87171; }

.scenario-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.scenario-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #aaa;
}

.scenario-prob {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: #fff;
}

.scenario-bar-container {
  height: 4px;
  background: #2a2a3e;
  border-radius: 2px;
  margin-bottom: 0.5rem;
}

.scenario-bar {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  transition: width 0.3s ease;
}

.scenario-events {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.event-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
}

.event-outcome {
  width: 18px;
  height: 18px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6rem;
  font-family: 'JetBrains Mono', monospace;
  font-weight: bold;
  flex-shrink: 0;
}
.event-outcome.yes { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
.event-outcome.no { background: rgba(248, 113, 113, 0.2); color: #f87171; }

.event-name {
  color: #bbb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scenario-footer {
  margin-top: 0.5rem;
  font-size: 0.65rem;
  color: #666;
  text-align: center;
}
</style>
