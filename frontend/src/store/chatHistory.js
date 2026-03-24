/**
 * Chat history store — persists interaction chat history to localStorage.
 * Keyed by simulation_id. Stores per-target history (report_agent, agent_0, etc.).
 */

const STORAGE_KEY = 'mirofish_chat_history'
const MAX_SIMULATIONS = 20

function loadAllFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {
    // Ignore parse errors
  }
  return {}
}

function saveAllToStorage(all) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  } catch {
    // Ignore storage errors (e.g. quota exceeded)
  }
}

export function loadChatHistory(simulationId) {
  if (!simulationId) return {}
  const all = loadAllFromStorage()
  return all[simulationId] || {}
}

export function saveChatHistory(simulationId, cache) {
  if (!simulationId) return
  const all = loadAllFromStorage()
  all[simulationId] = cache

  const keys = Object.keys(all)
  if (keys.length > MAX_SIMULATIONS) {
    const toRemove = keys.slice(0, keys.length - MAX_SIMULATIONS)
    toRemove.forEach(k => delete all[k])
  }

  saveAllToStorage(all)
}

export function clearChatHistory(simulationId) {
  if (!simulationId) return
  const all = loadAllFromStorage()
  delete all[simulationId]
  saveAllToStorage(all)
}
