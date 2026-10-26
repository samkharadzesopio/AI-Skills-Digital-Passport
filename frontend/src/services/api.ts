import axios from 'axios'
import { demoMode } from '../demo/mode'
// Private/auth traffic is same-origin. Vite proxies /api; production must route it to Django.
export const api = axios.create({ baseURL: '/api/', timeout: 15000, withCredentials: true, adapter: 'fetch', fetchOptions: { cache: 'no-store', redirect: 'error' }, headers: { Accept: 'application/json' } })
let csrfToken: string | null = null
let csrfRequest: Promise<string> | null = null
export function resetCsrfToken() { csrfToken = null; csrfRequest = null }
export async function ensureCsrfToken(): Promise<string> {
  if (demoMode) throw new Error('DEMO_MODE_PRIVATE_API_DISABLED')
  if (csrfToken) return csrfToken
  if (!csrfRequest) {
    const request = api.get('accounts/csrf/').then(response => {
      const value: unknown = response.data?.csrfToken
      if (typeof value !== 'string' || !/^[a-zA-Z0-9]{64}$/.test(value)) throw new Error('CSRF_CONTRACT_ERROR')
      if (csrfRequest === request) csrfToken = value
      return value
    }).finally(() => { if (csrfRequest === request) csrfRequest = null })
    csrfRequest = request
  }
  return csrfRequest
}
api.interceptors.request.use(async config => {
  if (demoMode) throw new Error('DEMO_MODE_PRIVATE_API_DISABLED')
  // Do not allow callers to redirect credential-bearing private requests off-origin.
  if (config.baseURL !== '/api/' || !config.url || /^(?:[a-z]+:|\/\/)/i.test(config.url)) throw new Error('PRIVATE_API_ORIGIN_BLOCKED')
  if (!['get','head','options'].includes((config.method ?? 'get').toLowerCase())) config.headers.set('X-CSRFToken', await ensureCsrfToken())
  return config
})
api.interceptors.response.use(response => response, error => {
  if (axios.isAxiosError(error) && error.response?.status === 403) resetCsrfToken()
  return Promise.reject(error)
})
