/**
 * Settings store — persists user preferences to localStorage.
 * Currently stores the selected LLM model for analysis phases.
 */
import { reactive } from 'vue'

const STORAGE_KEY = 'mirofish_settings'

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {
    // Ignore parse errors
  }
  return null
}

function saveToStorage(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      modelName: state.modelName
    }))
  } catch {
    // Ignore storage errors
  }
}

const saved = loadFromStorage()

const state = reactive({
  // null means "use server default" (whatever LLM_MODEL_NAME is set to)
  modelName: saved?.modelName || null
})

export function getSelectedModel() {
  return state.modelName
}

export function setSelectedModel(modelName) {
  state.modelName = modelName || null
  saveToStorage(state)
}

export default state
