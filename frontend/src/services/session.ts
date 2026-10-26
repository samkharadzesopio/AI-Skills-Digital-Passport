import axios from 'axios'
import { api } from './api'
import { demoMode } from '../demo/mode'
import { parseAccountSummary } from '../auth/contracts'
import type { Session } from '../auth/contracts'
import { AuthError, sanitizeAuthError } from '../auth/errors'
export type { Session } from '../auth/contracts'
export async function getSession(signal?: AbortSignal): Promise<Session> {
  if (demoMode) throw new AuthError('demoDisabled')
  try {
    const response = await api.get('accounts/me/', { signal, headers: { 'Cache-Control': 'no-cache' } })
    if (response.status !== 200) throw new AuthError('contract')
    return { status: 'authenticated', user: parseAccountSummary(response.data) }
  } catch (error) {
    // DRF SessionAuthentication returns 403, rather than necessarily 401, for anonymous /me/.
    if (axios.isAxiosError(error) && [401,403].includes(error.response?.status ?? 0)) return { status: 'anonymous' }
    if (axios.isCancel(error)) throw new AuthError('network')
    throw sanitizeAuthError(error, 'session')
  }
}
