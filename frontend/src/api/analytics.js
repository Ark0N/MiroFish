import service from './index'

/**
 * Get simulation analytics (sentiment curves, factions, momentum)
 * @param {string} simulationId
 */
export const getSimulationAnalytics = (simulationId) => {
  return service.get(`/api/analytics/simulation/${simulationId}`)
}

/**
 * Get per-agent behavior profiles
 * @param {string} simulationId
 */
export const getAgentProfiles = (simulationId) => {
  return service.get(`/api/analytics/agents/${simulationId}`)
}

/**
 * Get network influence and echo chamber analysis
 * @param {string} simulationId
 */
export const getNetworkAnalytics = (simulationId) => {
  return service.get(`/api/analytics/network/${simulationId}`)
}

/**
 * Get simulation quality score
 * @param {string} simulationId
 */
export const getQualityScore = (simulationId) => {
  return service.get(`/api/analytics/quality/${simulationId}`)
}
