import service from './index'

/**
 * Fetch available models with pricing info
 */
export const getAvailableModels = () => {
  return service.get('/api/settings/models')
}
