/**
 * Settings store — persists user preferences to localStorage.
 * Stores: selected LLM model, max agents, max rounds.
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
      modelName: state.modelName,
      maxAgents: state.maxAgents,
      maxRounds: state.maxRounds
    }))
  } catch {
    // Ignore storage errors
  }
}

const saved = loadFromStorage()

const state = reactive({
  // null means "use server default"
  modelName: saved?.modelName || null,
  // null means "use all entities from graph" (no limit)
  maxAgents: saved?.maxAgents || null,
  // null means "use server default" (OASIS_DEFAULT_MAX_ROUNDS, default 10)
  maxRounds: saved?.maxRounds || null
})

export function getSelectedModel() {
  return state.modelName
}

export function setSelectedModel(modelName) {
  state.modelName = modelName || null
  saveToStorage(state)
}

export function getMaxAgents() {
  return state.maxAgents
}

export function setMaxAgents(val) {
  state.maxAgents = val ? parseInt(val, 10) : null
  saveToStorage(state)
}

export function getMaxRounds() {
  return state.maxRounds
}

export function setMaxRounds(val) {
  state.maxRounds = val ? parseInt(val, 10) : null
  saveToStorage(state)
}

export default state
