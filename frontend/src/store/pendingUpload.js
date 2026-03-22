/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 *
 * localStorage persistence: only serializable metadata is persisted
 * (simulationRequirement, isPending, and file metadata like name/size/type).
 * Actual File objects cannot be serialized and must remain in memory.
 * After a page refresh, files will need to be re-selected.
 */
import { reactive } from 'vue'

const STORAGE_KEY = 'mirofish_pending_upload'

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return JSON.parse(raw)
    }
  } catch {
    // Ignore parse errors
  }
  return null
}

function saveToStorage(state) {
  try {
    const serializable = {
      simulationRequirement: state.simulationRequirement,
      isPending: state.isPending,
      fileMeta: state.files.map(f => ({
        name: f.name || f,
        size: f.size || 0,
        type: f.type || ''
      }))
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serializable))
  } catch {
    // Ignore storage errors (e.g. quota exceeded)
  }
}

function removeFromStorage() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ignore removal errors
  }
}

// Initialize state, restoring persisted metadata if available
const saved = loadFromStorage()

const state = reactive({
  files: [],
  simulationRequirement: saved?.simulationRequirement || '',
  isPending: saved?.isPending || false,
  // File metadata preserved across refreshes (names, sizes) for display purposes.
  // Actual File objects are NOT available after refresh — user must re-select files.
  fileMeta: saved?.fileMeta || []
})

export function setPendingUpload(files, requirement) {
  state.files = files
  state.simulationRequirement = requirement
  state.isPending = true
  state.fileMeta = files.map(f => ({
    name: f.name || f,
    size: f.size || 0,
    type: f.type || ''
  }))
  saveToStorage(state)
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending,
    fileMeta: state.fileMeta
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.isPending = false
  state.fileMeta = []
  removeFromStorage()
}

export default state
