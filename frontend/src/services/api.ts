import axios from 'axios'
import { demoMode } from '../demo/mode'
// No endpoint is assumed. Wire confirmed Django routes here, independently of mock data.
export const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api/', timeout: 15000, withCredentials: true })
api.interceptors.request.use(config => {
  if (demoMode) throw new Error('DEMO_MODE_PRIVATE_API_DISABLED')
  return config
})
