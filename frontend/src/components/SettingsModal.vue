<template>
  <teleport to="body">
    <div v-if="visible" class="settings-overlay" @click.self="$emit('close')">
      <div class="settings-modal">
        <div class="modal-header">
          <span class="modal-title">Settings</span>
          <button class="close-btn" @click="$emit('close')">&times;</button>
        </div>

        <div class="modal-body">
          <!-- Model Selection -->
          <div class="setting-section">
            <div class="section-label">Analysis Model</div>
            <div class="section-desc">
              Choose which Claude model to use for ontology extraction, profile generation, and report generation.
              Graph building uses the server-configured model. Simulation agents use the local LLM when configured.
            </div>

            <div v-if="loading" class="loading-text">Loading models...</div>
            <div v-else-if="fetchError" class="error-text">{{ fetchError }}</div>

            <div v-else class="model-list">
              <label
                v-for="model in models"
                :key="model.id"
                class="model-option"
                :class="{ selected: selectedModel === model.id }"
              >
                <input
                  type="radio"
                  :value="model.id"
                  v-model="selectedModel"
                  class="model-radio"
                />
                <div class="model-info">
                  <div class="model-name-row">
                    <span class="model-name">{{ model.name }}</span>
                    <span class="model-tier" :class="model.tier">{{ model.tier }}</span>
                  </div>
                  <div class="model-desc">{{ model.description }}</div>
                  <div class="model-pricing">
                    <span class="price-tag">Input: ${{ model.input_cost_per_mtok.toFixed(2) }}/MTok</span>
                    <span class="price-tag">Output: ${{ model.output_cost_per_mtok.toFixed(2) }}/MTok</span>
                    <span class="cost-badge" :class="costClass(model)">{{ costLabel(model) }}</span>
                  </div>
                </div>
              </label>
            </div>
          </div>

          <!-- Cost comparison -->
          <div v-if="models.length > 0 && selectedModelData" class="setting-section cost-section">
            <div class="section-label">Estimated Cost Impact</div>
            <div class="cost-comparison">
              <div class="cost-bar-container">
                <div
                  v-for="model in models"
                  :key="model.id + '-bar'"
                  class="cost-bar-row"
                >
                  <span class="bar-label" :class="{ active: selectedModel === model.id }">{{ model.name }}</span>
                  <div class="bar-track">
                    <div
                      class="bar-fill"
                      :class="{ active: selectedModel === model.id }"
                      :style="{ width: barWidth(model) + '%' }"
                    ></div>
                  </div>
                  <span class="bar-value" :class="{ active: selectedModel === model.id }">{{ model.cost_multiplier }}x</span>
                </div>
              </div>
              <div class="cost-note">
                Cost multiplier relative to the cheapest model. Applies to ontology, profile, config, and report phases only.
              </div>
            </div>
          </div>

          <!-- Simulation Settings -->
          <div class="setting-section sim-section">
            <div class="section-label">Simulation</div>
            <div class="section-desc">
              Control the scale of simulations. Fewer agents and rounds run faster and cost less.
            </div>

            <div class="sim-fields">
              <div class="sim-field">
                <label class="field-label" for="max-agents">Max Agents</label>
                <div class="field-input-row">
                  <input
                    id="max-agents"
                    type="number"
                    v-model.number="maxAgents"
                    min="1"
                    max="10000"
                    placeholder="All"
                    class="field-input"
                  />
                  <span class="field-hint">{{ maxAgents ? maxAgents + ' agents' : 'No limit (use all entities)' }}</span>
                </div>
              </div>

              <div class="sim-field">
                <label class="field-label" for="max-rounds">Max Rounds</label>
                <div class="field-input-row">
                  <input
                    id="max-rounds"
                    type="number"
                    v-model.number="maxRounds"
                    min="1"
                    max="1000"
                    placeholder="Default"
                    class="field-input"
                  />
                  <span class="field-hint">{{ maxRounds ? maxRounds + ' rounds' : 'Server default (10)' }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Prediction Engine -->
          <div class="setting-section">
            <div class="section-label">Prediction Engine</div>
            <div class="section-desc">
              {{ catalogServices.length }} services and {{ catalogEndpoints.length }} endpoints available.
              <button class="toggle-catalog-btn" @click="showCatalog = !showCatalog">
                {{ showCatalog ? 'Hide' : 'Show' }} API Catalog
              </button>
            </div>
            <div v-if="showCatalog" class="catalog-list">
              <div class="catalog-group">
                <div class="catalog-group-title">Services</div>
                <div v-for="svc in catalogServices" :key="svc.name" class="catalog-item">
                  <span class="catalog-name">{{ svc.name }}</span>
                  <span class="catalog-desc">{{ svc.description }}</span>
                </div>
              </div>
              <div class="catalog-group">
                <div class="catalog-group-title">Endpoints</div>
                <div v-for="ep in catalogEndpoints" :key="ep.path" class="catalog-item">
                  <span class="catalog-method">{{ ep.method }}</span>
                  <span class="catalog-path">{{ ep.path }}</span>
                  <span class="catalog-desc">{{ ep.description }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="save-btn" @click="save">Apply</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getAvailableModels } from '../api/settings'
import { getPredictionCatalog } from '../api/report'
import {
  getSelectedModel, setSelectedModel,
  getMaxAgents, setMaxAgents,
  getMaxRounds, setMaxRounds
} from '../store/settings'

const props = defineProps({
  visible: Boolean
})

const emit = defineEmits(['close'])

const models = ref([])
const loading = ref(false)
const showCatalog = ref(false)
const catalogServices = ref([])
const catalogEndpoints = ref([])
const fetchError = ref('')
const selectedModel = ref(getSelectedModel())
const serverDefault = ref('')
const maxAgents = ref(getMaxAgents())
const maxRounds = ref(getMaxRounds())

const selectedModelData = computed(() => models.value.find(m => m.id === selectedModel.value))

const maxMultiplier = computed(() => {
  if (models.value.length === 0) return 1
  return Math.max(...models.value.map(m => m.cost_multiplier))
})

function barWidth(model) {
  return (model.cost_multiplier / maxMultiplier.value) * 100
}

function costLabel(model) {
  if (model.cost_multiplier === 1) return 'baseline'
  return model.cost_multiplier + 'x cost'
}

function costClass(model) {
  if (model.cost_multiplier <= 1) return 'cost-low'
  if (model.cost_multiplier <= 5) return 'cost-mid'
  return 'cost-high'
}

async function fetchModels() {
  loading.value = true
  fetchError.value = ''
  try {
    const res = await getAvailableModels()
    models.value = res.data.models
    serverDefault.value = res.data.current_model
    if (!selectedModel.value) {
      selectedModel.value = serverDefault.value
    }
  } catch (e) {
    fetchError.value = 'Failed to load models. Is the backend running?'
  } finally {
    loading.value = false
  }
}

function save() {
  setSelectedModel(selectedModel.value)
  setMaxAgents(maxAgents.value)
  setMaxRounds(maxRounds.value)
  emit('close')
}

watch(() => props.visible, (val) => {
  if (val && models.value.length === 0) {
    fetchModels()
  }
  if (val) {
    selectedModel.value = getSelectedModel() || serverDefault.value
    maxAgents.value = getMaxAgents()
    maxRounds.value = getMaxRounds()
  }
})

onMounted(async () => {
  if (props.visible) fetchModels()
  try {
    const res = await getPredictionCatalog()
    if (res.data?.success && res.data?.data) {
      catalogServices.value = res.data.data.services || []
      catalogEndpoints.value = res.data.data.endpoints || []
    }
  } catch (e) {}
})
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-modal {
  background: #fff;
  border: 1px solid #e5e5e5;
  width: 560px;
  max-height: 85vh;
  overflow-y: auto;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e5e5;
  background: #000;
  color: #fff;
}

.modal-title {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.5px;
}

.close-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 1.4rem;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.close-btn:hover { opacity: 0.7; }

.modal-body {
  padding: 24px;
}

.setting-section {
  margin-bottom: 24px;
}

.section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  color: #000;
}

.section-desc {
  font-size: 0.82rem;
  color: #666;
  margin-bottom: 16px;
  line-height: 1.5;
}

.loading-text, .error-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  padding: 12px;
}

.error-text { color: #d00; }
.loading-text { color: #666; }

/* Model cards */
.model-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.model-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e5e5e5;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.model-option:hover {
  border-color: #999;
}

.model-option.selected {
  border-color: #000;
  background: #fafafa;
}

.model-radio {
  margin-top: 3px;
  accent-color: #000;
}

.model-info {
  flex: 1;
}

.model-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.model-name {
  font-weight: 600;
  font-size: 0.92rem;
}

.model-tier {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  padding: 2px 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.model-tier.fast {
  background: #e8f5e9;
  color: #2e7d32;
}
.model-tier.balanced {
  background: #e3f2fd;
  color: #1565c0;
}
.model-tier.powerful {
  background: #fff3e0;
  color: #e65100;
}

.model-desc {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 8px;
  line-height: 1.4;
}

.model-pricing {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.price-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #888;
}

.cost-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  padding: 1px 6px;
  font-weight: 600;
}

.cost-low { background: #e8f5e9; color: #2e7d32; }
.cost-mid { background: #fff3e0; color: #e65100; }
.cost-high { background: #fce4ec; color: #c62828; }

/* Cost comparison bars */
.cost-section {
  border-top: 1px solid #e5e5e5;
  padding-top: 20px;
}

.cost-bar-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.cost-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bar-label {
  width: 120px;
  font-size: 0.78rem;
  color: #888;
  text-align: right;
  font-family: 'JetBrains Mono', monospace;
}

.bar-label.active {
  color: #000;
  font-weight: 600;
}

.bar-track {
  flex: 1;
  height: 18px;
  background: #f5f5f5;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #ddd;
  transition: width 0.3s ease;
}

.bar-fill.active {
  background: #000;
}

.bar-value {
  width: 36px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  color: #888;
}

.bar-value.active {
  color: #000;
  font-weight: 600;
}

.cost-note {
  font-size: 0.75rem;
  color: #999;
  line-height: 1.4;
}

/* Simulation settings */
.sim-section {
  border-top: 1px solid #e5e5e5;
  padding-top: 20px;
}

.sim-fields {
  display: flex;
  gap: 20px;
}

.sim-field {
  flex: 1;
}

.field-label {
  display: block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  font-weight: 600;
  margin-bottom: 6px;
  color: #333;
}

.field-input-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #e5e5e5;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  background: #fafafa;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.field-input:focus {
  outline: none;
  border-color: #000;
  background: #fff;
}

.field-input::placeholder {
  color: #bbb;
}

/* Hide number input spinners for cleaner look */
.field-input::-webkit-outer-spin-button,
.field-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.field-input[type=number] {
  -moz-appearance: textfield;
}

.field-hint {
  font-size: 0.72rem;
  color: #999;
  font-family: 'JetBrains Mono', monospace;
}

/* Footer */
.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid #e5e5e5;
  display: flex;
  justify-content: flex-end;
}

.save-btn {
  background: #000;
  color: #fff;
  border: none;
  padding: 10px 28px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.5px;
  transition: opacity 0.15s;
}

.save-btn:hover {
  opacity: 0.85;
}

.toggle-catalog-btn {
  background: transparent;
  border: 1px solid #444;
  color: #aaa;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.7rem;
  margin-left: 0.5rem;
}
.toggle-catalog-btn:hover { color: #fff; border-color: #666; }

.catalog-list {
  margin-top: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
}
.catalog-group { margin-bottom: 0.75rem; }
.catalog-group-title {
  font-size: 0.7rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.3rem;
  border-bottom: 1px solid #2a2a3e;
  padding-bottom: 0.2rem;
}
.catalog-item {
  display: flex;
  gap: 0.4rem;
  padding: 0.15rem 0;
  font-size: 0.68rem;
  align-items: baseline;
}
.catalog-name {
  color: #60a5fa;
  font-family: 'JetBrains Mono', monospace;
  min-width: 180px;
  flex-shrink: 0;
}
.catalog-method {
  color: #4ade80;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  min-width: 30px;
}
.catalog-path {
  color: #ddd;
  font-family: 'JetBrains Mono', monospace;
  min-width: 200px;
  flex-shrink: 0;
}
.catalog-desc { color: #888; }
</style>
