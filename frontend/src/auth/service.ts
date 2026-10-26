import { api, ensureCsrfToken, resetCsrfToken } from '../services/api'
import { demoMode } from '../demo/mode'
import { parseAccountSummary, normalizeUniversityEmail } from './contracts'
import { AuthError, sanitizeAuthError } from './errors'
function liveOnly() { if (demoMode) throw new AuthError('demoDisabled') }
export async function requestStudentOtp(email: string): Promise<void> {
  liveOnly()
  const normalized = normalizeUniversityEmail(email)
  if (!normalized) throw new AuthError('invalidInput')
  try {
    const response = await api.post('accounts/otp/request/', { email: normalized })
    if (response.status !== 202 || typeof response.data?.detail !== 'string') throw new AuthError('contract')
  } catch (error) { throw sanitizeAuthError(error, 'request') }
}
export async function verifyStudentOtp(email: string, code: string): Promise<void> {
  liveOnly()
  const normalized = normalizeUniversityEmail(email)
  if (!normalized || !/^[0-9]{6}$/.test(code)) throw new AuthError('invalidCode')
  try {
    const response = await api.post('accounts/otp/verify/', { email: normalized, code })
    if (response.status !== 200 || typeof response.data?.detail !== 'string') throw new AuthError('contract')
    resetCsrfToken() // Django rotates CSRF on login. Bootstrap a fresh token before the next write.
  } catch (error) { throw sanitizeAuthError(error, 'otp') }
}
export async function loginAdministrator(email: string, password: string): Promise<void> {
  liveOnly()
  if (!email.trim() || email.trim().length > 254 || !password || password.length > 256) throw new AuthError('invalidInput')
  try {
    const response = await api.post('accounts/login/', { email: email.trim().toLowerCase(), password })
    if (response.status !== 200) throw new AuthError('contract')
    parseAccountSummary(response.data)
    resetCsrfToken()
  } catch (error) { throw sanitizeAuthError(error, 'login') }
}
export async function logoutAccount(): Promise<void> {
  liveOnly()
  try {
    const response = await api.post('accounts/logout/')
    if (response.status !== 204) throw new AuthError('contract')
    resetCsrfToken()
  } catch (error) { throw sanitizeAuthError(error, 'logout') }
}
export async function prepareAuthentication(): Promise<void> {
  liveOnly()
  try { await ensureCsrfToken() } catch (error) { throw sanitizeAuthError(error, 'request') }
}
