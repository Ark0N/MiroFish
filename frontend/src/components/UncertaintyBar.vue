<template>
  <div class="uncertainty-bar-wrapper">
    <div class="uncertainty-label">Uncertainty Decomposition</div>
    <div class="uncertainty-bar">
      <div
        class="bar-segment epistemic"
        :style="{ width: epistemicPct + '%' }"
        :title="epistemicTooltip"
      >
        <span v-if="epistemicPct > 15">{{ epistemicPct }}%</span>
      </div>
      <div
        class="bar-segment aleatoric"
        :style="{ width: aleatoricPct + '%' }"
        :title="aleatoricTooltip"
      >
        <span v-if="aleatoricPct > 15">{{ aleatoricPct }}%</span>
      </div>
    </div>
    <div class="uncertainty-legend">
      <div class="legend-item">
        <span class="legend-dot epistemic-dot"></span>
        Epistemic (reducible)
      </div>
      <div class="legend-item">
        <span class="legend-dot aleatoric-dot"></span>
        Aleatoric (irreducible)
      </div>
    </div>
    <div class="uncertainty-recommendation" v-if="recommendation">
      {{ recommendation }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  epistemic: { type: Number, default: 0.3 },
  aleatoric: { type: Number, default: 0.5 },
  recommendation: { type: String, default: '' },
})

const total = computed(() => props.epistemic + props.aleatoric || 1)
const epistemicPct = computed(() => Math.round((props.epistemic / total.value) * 100))
const aleatoricPct = computed(() => 100 - epistemicPct.value)

const epistemicTooltip = computed(() =>
  `Epistemic uncertainty: ${(props.epistemic * 100).toFixed(0)}% — Can be reduced with more data/simulations`
)
const aleatoricTooltip = computed(() =>
  `Aleatoric uncertainty: ${(props.aleatoric * 100).toFixed(0)}% — Inherent randomness, cannot be reduced`
)
</script>

<style scoped>
.uncertainty-bar-wrapper {
  margin: 0.5rem 0;
}

.uncertainty-label {
  font-size: 0.7rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.3rem;
}

.uncertainty-bar {
  display: flex;
  height: 16px;
  border-radius: 4px;
  overflow: hidden;
  background: #1a1a2e;
}

.bar-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6rem;
  font-family: 'JetBrains Mono', monospace;
  color: #fff;
  cursor: help;
  transition: width 0.3s ease;
}

.epistemic { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
.aleatoric { background: linear-gradient(90deg, #6366f1, #818cf8); }

.uncertainty-legend {
  display: flex;
  gap: 1rem;
  margin-top: 0.3rem;
  font-size: 0.65rem;
  color: #888;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}
.epistemic-dot { background: #a78bfa; }
.aleatoric-dot { background: #818cf8; }

.uncertainty-recommendation {
  margin-top: 0.4rem;
  font-size: 0.7rem;
  color: #aaa;
  font-style: italic;
}
</style>
