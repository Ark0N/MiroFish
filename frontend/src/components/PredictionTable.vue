<template>
  <div class="prediction-table" v-if="predictions.length > 0">
    <div class="prediction-header">
      <h3>Structured Predictions</h3>
      <div class="sort-controls">
        <button
          :class="{ active: sortBy === 'probability' }"
          @click="sortBy = 'probability'"
        >By Probability</button>
        <button
          :class="{ active: sortBy === 'agreement' }"
          @click="sortBy = 'agreement'"
        >By Agreement</button>
        <button
          :class="{ active: sortBy === 'event' }"
          @click="sortBy = 'event'"
        >By Name</button>
      </div>
    </div>

    <div class="predictions-list">
      <div
        v-for="(pred, idx) in sortedPredictions"
        :key="idx"
        class="prediction-card"
        :class="confidenceClass(pred.probability)"
      >
        <div class="prediction-main">
          <div class="prediction-rank">#{{ idx + 1 }}</div>
          <div class="prediction-content">
            <div class="prediction-event">{{ pred.event }}</div>
            <div class="prediction-meta">
              <span class="timeframe" v-if="pred.timeframe">{{ pred.timeframe }}</span>
            </div>
          </div>
        </div>

        <div class="prediction-metrics">
          <div class="metric probability-metric">
            <div class="metric-label">Probability</div>
            <div class="probability-bar-container">
              <div
                class="probability-bar"
                :style="{ width: (pred.probability * 100) + '%' }"
                :class="probabilityColor(pred.probability)"
              ></div>
              <span class="probability-value">{{ (pred.probability * 100).toFixed(0) }}%</span>
            </div>
            <div class="confidence-interval" v-if="pred.confidence_interval">
              CI: {{ (pred.confidence_interval[0] * 100).toFixed(0) }}% - {{ (pred.confidence_interval[1] * 100).toFixed(0) }}%
            </div>
          </div>

          <div class="metric agreement-metric">
            <div class="metric-label">Agent Agreement</div>
            <div class="probability-bar-container">
              <div
                class="probability-bar agreement-bar"
                :style="{ width: (pred.agent_agreement * 100) + '%' }"
              ></div>
              <span class="probability-value">{{ (pred.agent_agreement * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>

        <div class="prediction-details" v-if="expandedIdx === idx">
          <div class="detail-section" v-if="pred.reasoning">
            <strong>Reasoning:</strong> {{ pred.reasoning }}
          </div>
          <div class="detail-section" v-if="pred.evidence && pred.evidence.length">
            <strong>Evidence:</strong>
            <ul>
              <li v-for="(e, i) in pred.evidence" :key="i">{{ e }}</li>
            </ul>
          </div>
          <div class="detail-section" v-if="pred.risk_factors && pred.risk_factors.length">
            <strong>Risk Factors:</strong>
            <ul>
              <li v-for="(r, i) in pred.risk_factors" :key="i">{{ r }}</li>
            </ul>
          </div>
        </div>

        <button class="expand-btn" @click="toggleExpand(idx)">
          {{ expandedIdx === idx ? 'Collapse' : 'Details' }}
        </button>
      </div>
    </div>

    <div class="overall-confidence" v-if="overallConfidence">
      <strong>Overall Forecast Confidence:</strong> {{ overallConfidence }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  predictions: {
    type: Array,
    default: () => []
  },
  overallConfidence: {
    type: String,
    default: ''
  }
})

const sortBy = ref('probability')
const expandedIdx = ref(null)

const sortedPredictions = computed(() => {
  const preds = [...props.predictions]
  if (sortBy.value === 'probability') {
    preds.sort((a, b) => b.probability - a.probability)
  } else if (sortBy.value === 'agreement') {
    preds.sort((a, b) => b.agent_agreement - a.agent_agreement)
  } else if (sortBy.value === 'event') {
    preds.sort((a, b) => a.event.localeCompare(b.event))
  }
  return preds
})

const toggleExpand = (idx) => {
  expandedIdx.value = expandedIdx.value === idx ? null : idx
}

const confidenceClass = (prob) => {
  if (prob >= 0.75) return 'high-confidence'
  if (prob >= 0.5) return 'medium-confidence'
  return 'low-confidence'
}

const probabilityColor = (prob) => {
  if (prob >= 0.75) return 'bar-high'
  if (prob >= 0.5) return 'bar-medium'
  return 'bar-low'
}
</script>

<style scoped>
.prediction-table {
  margin: 1.5rem 0;
}

.prediction-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.prediction-header h3 {
  margin: 0;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.1rem;
}

.sort-controls {
  display: flex;
  gap: 0.5rem;
}

.sort-controls button {
  padding: 0.3rem 0.8rem;
  border: 1px solid #444;
  background: transparent;
  color: #aaa;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', monospace;
  transition: all 0.2s;
}

.sort-controls button.active {
  background: #333;
  color: #fff;
  border-color: #666;
}

.predictions-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.prediction-card {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 8px;
  padding: 1rem;
  transition: border-color 0.2s;
}

.prediction-card.high-confidence {
  border-left: 3px solid #4ade80;
}

.prediction-card.medium-confidence {
  border-left: 3px solid #fbbf24;
}

.prediction-card.low-confidence {
  border-left: 3px solid #f87171;
}

.prediction-main {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.prediction-rank {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #666;
  min-width: 2rem;
}

.prediction-event {
  font-size: 0.95rem;
  color: #e0e0e0;
  line-height: 1.4;
}

.prediction-meta {
  margin-top: 0.25rem;
}

.timeframe {
  font-size: 0.75rem;
  color: #888;
  background: #2a2a3e;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
}

.prediction-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.metric-label {
  font-size: 0.7rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.25rem;
}

.probability-bar-container {
  position: relative;
  height: 20px;
  background: #2a2a3e;
  border-radius: 4px;
  overflow: hidden;
}

.probability-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.bar-high { background: linear-gradient(90deg, #22c55e, #4ade80); }
.bar-medium { background: linear-gradient(90deg, #eab308, #fbbf24); }
.bar-low { background: linear-gradient(90deg, #dc2626, #f87171); }
.agreement-bar { background: linear-gradient(90deg, #3b82f6, #60a5fa); }

.probability-value {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', monospace;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}

.confidence-interval {
  font-size: 0.65rem;
  color: #666;
  margin-top: 0.2rem;
  font-family: 'JetBrains Mono', monospace;
}

.prediction-details {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #2a2a3e;
}

.detail-section {
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
  color: #bbb;
}

.detail-section strong {
  color: #ddd;
}

.detail-section ul {
  margin: 0.25rem 0 0 1rem;
  padding: 0;
}

.detail-section li {
  margin-bottom: 0.2rem;
}

.expand-btn {
  background: transparent;
  border: none;
  color: #6366f1;
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0.25rem 0;
  font-family: 'JetBrains Mono', monospace;
}

.expand-btn:hover {
  color: #818cf8;
}

.overall-confidence {
  margin-top: 1rem;
  padding: 0.75rem;
  background: #1a1a2e;
  border-radius: 6px;
  font-size: 0.85rem;
  color: #bbb;
}

.overall-confidence strong {
  color: #ddd;
}
</style>
