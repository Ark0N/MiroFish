import service, { requestWithRetry } from './index'
import { getSelectedModel } from '../store/settings'

function _withModel(data) {
  const model = getSelectedModel()
  return model ? { ...data, model_name: model } : data
}

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/generate', _withModel(data)), 3, 1000)
}

/**
 * 获取报告生成状态
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/api/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * Get structured predictions for a report
 * @param {string} reportId
 */
export const getPredictions = (reportId) => {
  return service.get(`/api/report/${reportId}/predictions`)
}

/**
 * Get prediction health dashboard
 * @param {string} reportId
 */
export const getPredictionHealth = (reportId) => {
  return service.get(`/api/report/${reportId}/health`)
}

/**
 * Compare predictions across reports
 * @param {string[]} reportIds
 */
export const comparePredictions = (reportIds) => {
  return service.post('/api/report/compare-predictions', { report_ids: reportIds })
}

/**
 * Get ensemble predictions for a project
 * @param {string} projectId
 */
export const getEnsemblePredictions = (projectId) => {
  return service.get(`/api/report/ensemble/${projectId}`)
}

/**
 * Rate a prediction
 * @param {string} reportId
 * @param {number} predictionIdx
 * @param {number} rating - 1-5
 * @param {string} feedback
 */
export const ratePrediction = (reportId, predictionIdx, rating, feedback = '') => {
  return service.post(`/api/report/${reportId}/predictions/${predictionIdx}/rate`, { rating, feedback })
}

/**
 * Add analyst note to a prediction
 * @param {string} reportId
 * @param {number} predictionIdx
 * @param {string} note
 */
export const addPredictionNote = (reportId, predictionIdx, note) => {
  return service.post(`/api/report/${reportId}/predictions/${predictionIdx}/note`, { note })
}

/**
 * Get scenario tree for a report
 * @param {string} reportId
 */
export const getScenarios = (reportId) => {
  return service.get(`/api/report/${reportId}/scenarios`)
}

/**
 * Get prediction service catalog
 */
export const getPredictionCatalog = () => {
  return service.get('/api/report/catalog')
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/chat', _withModel(data)), 3, 1000)
}
