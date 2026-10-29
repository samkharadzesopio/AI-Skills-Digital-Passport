import axios from 'axios'
import { demoMode } from '../demo/mode'
import type { ReferenceKind, VerificationConfig, VerificationFailure, VerificationOutcome } from './contracts'
import { isPublicApiBaseSafe, normalizeReference, retryDeadline, validatePdf } from './validation'
import { failure, parseVerification, registrySources } from './adapters'
export { failure, parseVerification, registrySources } from './adapters'
const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/'
const sourceConfig: string = import.meta.env.VITE_PUBLIC_VERIFICATION_SOURCES ?? [...new Set(Object.values(registrySources))].join(',')
export const verificationConfig: VerificationConfig = {
  enabled: !demoMode && import.meta.env.VITE_PUBLIC_VERIFICATION_ENABLED !== 'false' && isPublicApiBaseSafe(apiBase, import.meta.env.DEV),
  trustedSources: sourceConfig.split(',').map(s => s.trim()).filter(Boolean),
}
// Public traffic never uses the private session/CSRF client, cookie jar or redirects.
const publicApi = axios.create({
  baseURL: apiBase, timeout: 30000, adapter: 'fetch', withCredentials: false,
  fetchOptions: { credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer', cache: 'no-store' },
  headers: { Accept: 'application/json' },
})
export function mapVerificationError(error: unknown, now = Date.now()): VerificationFailure {
  if (axios.isCancel(error)) return failure('canceled')
  if (!axios.isAxiosError(error)) return failure('contract')
  const status = error.response?.status
  if (status === 429) return failure('rate_limit', retryDeadline(error.response?.headers?.['retry-after'], now))
  if (status === 401 || status === 403) return failure('auth')
  if (status && [400,413,415,422].includes(status)) return failure('rejected')
  if (status) return failure('server') // HTTP 404 is not an authoritative NOT_FOUND result.
  return failure(error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT' ? 'timeout' : 'network')
}
export async function lookupReference(reference: string, kind: ReferenceKind, signal: AbortSignal): Promise<VerificationOutcome> {
  if (demoMode || !verificationConfig.enabled || !verificationConfig.trustedSources.length) return failure('disconnected')
  const normalized = normalizeReference(reference, kind)
  if (!normalized) return failure('rejected')
  const prefix = normalized.kind === 'credential' ? '' : `${normalized.kind}/`
  try {
    const response = await publicApi.get(`verification/${prefix}${encodeURIComponent(normalized.reference)}/`, { signal })
    return parseVerification(response.data, normalized.kind, verificationConfig.trustedSources, normalized.reference)
  } catch (error) { return mapVerificationError(error) }
}
export async function uploadPdf(file: File, signal: AbortSignal, progress: (percent: number | null) => void): Promise<VerificationOutcome> {
  if (demoMode || !verificationConfig.enabled || !verificationConfig.trustedSources.length) return failure('disconnected')
  if (validatePdf(file)) return failure('rejected')
  const body = new FormData()
  // The registry hashes bytes; the student's filename is unnecessary.
  body.append('file', file.type === 'application/pdf' ? file : new File([file], 'passport.pdf', { type: 'application/pdf' }), 'passport.pdf')
  try {
    // Native multipart keeps a usable Content-Length through the Vite/WSGI path.
    // Fetch progress tracking can replace it with a chunked request stream, which
    // Django's development server cannot parse. Show indeterminate feedback.
    progress(null)
    const response = await publicApi.post('verification/document/', body, { signal })
    return parseVerification(response.data, 'document', verificationConfig.trustedSources)
  } catch (error) { return mapVerificationError(error) }
}
