import axios from 'axios'
export type AuthErrorCode = 'network' | 'timeout' | 'rateLimit' | 'csrf' | 'invalidCode' | 'invalidCredentials' | 'invalidInput' | 'unavailable' | 'contract' | 'demoDisabled'
export class AuthError extends Error {
  readonly code: AuthErrorCode
  readonly retryAt: number | null
  constructor(code: AuthErrorCode, retryAt: number | null = null) { super(code); this.name = 'AuthError'; this.code = code; this.retryAt = retryAt }
}
export function authRetryAt(value: unknown, now = Date.now()): number {
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) { const seconds = Number(value); if (Number.isSafeInteger(seconds) && seconds < 31536000) return now + seconds * 1000 }
  if (typeof value === 'string') { const timestamp = Date.parse(value); if (Number.isFinite(timestamp) && timestamp > now) return timestamp }
  return now + 60000
}
/** Do not retain Axios request config, passwords, OTPs or raw response bodies in UI errors. */
export function sanitizeAuthError(error: unknown, operation: 'otp' | 'login' | 'request' | 'session' | 'logout'): AuthError {
  if (error instanceof AuthError) return error
  if (!axios.isAxiosError(error)) return new AuthError('contract')
  const status = error.response?.status
  if (status === 429) return new AuthError('rateLimit', authRetryAt(error.response?.headers?.['retry-after']))
  if (status === 403) return new AuthError('csrf')
  if (operation === 'otp' && status === 400) return new AuthError('invalidCode')
  if (operation === 'login' && (status === 400 || status === 401)) return new AuthError('invalidCredentials')
  if (status === 400) return new AuthError('invalidInput')
  if (status) return new AuthError('unavailable')
  return new AuthError(error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT' ? 'timeout' : 'network')
}
