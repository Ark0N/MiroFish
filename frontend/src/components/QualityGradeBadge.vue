<template>
  <div class="quality-badge" :class="gradeClass" v-if="grade">
    <span class="grade-letter">{{ grade }}</span>
    <div class="grade-details" v-if="showDetails">
      <div class="detail-row" v-for="(val, key) in components" :key="key">
        <span class="detail-label">{{ formatLabel(key) }}</span>
        <div class="detail-bar-bg">
          <div class="detail-bar" :style="{ width: (val * 100) + '%' }"></div>
        </div>
        <span class="detail-val">{{ (val * 100).toFixed(0) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  grade: { type: String, default: '' },
  components: { type: Object, default: () => ({}) },
  showDetails: { type: Boolean, default: true },
})

const gradeClass = computed(() => {
  const g = props.grade
  if (g === 'A') return 'grade-a'
  if (g === 'B') return 'grade-b'
  if (g === 'C') return 'grade-c'
  return 'grade-low'
})

const formatLabel = (key) => {
  return key.replace(/_/g, ' ').replace(/\bnon\b/, '').trim()
}
</script>

<style scoped>
.quality-badge {
  display: inline-flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  border: 1px solid;
}

.grade-a { background: rgba(74, 222, 128, 0.08); border-color: rgba(74, 222, 128, 0.3); }
.grade-b { background: rgba(96, 165, 250, 0.08); border-color: rgba(96, 165, 250, 0.3); }
.grade-c { background: rgba(251, 191, 36, 0.08); border-color: rgba(251, 191, 36, 0.3); }
.grade-low { background: rgba(248, 113, 113, 0.08); border-color: rgba(248, 113, 113, 0.3); }

.grade-letter {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.8rem;
  font-weight: 700;
  line-height: 1;
}
.grade-a .grade-letter { color: #4ade80; }
.grade-b .grade-letter { color: #60a5fa; }
.grade-c .grade-letter { color: #fbbf24; }
.grade-low .grade-letter { color: #f87171; }

.grade-details { flex: 1; min-width: 120px; }

.detail-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  margin-bottom: 0.2rem;
}

.detail-label {
  font-size: 0.6rem;
  color: #888;
  min-width: 65px;
  text-transform: capitalize;
}

.detail-bar-bg {
  flex: 1;
  height: 4px;
  background: #2a2a3e;
  border-radius: 2px;
}

.detail-bar {
  height: 100%;
  border-radius: 2px;
  background: #6366f1;
  transition: width 0.3s;
}

.detail-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: #aaa;
  min-width: 25px;
  text-align: right;
}
</style>
