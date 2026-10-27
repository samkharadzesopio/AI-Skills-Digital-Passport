import { blockchainAvailability } from './blockchain'
import axios from 'axios'
import { demoMode } from '../demo/mode'
import type { VerificationConfig, VerificationFailure, VerificationOutcome } from './contracts'
import { isPublicApiBaseSafe, retryDeadline, validatePdf, validateReference, normalizePassportReference } from './validation'
const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/'
export const verificationConfig: VerificationConfig = {
  enabled: !demoMode && import.meta.env.VITE_PUBLIC_VERIFICATION_ENABLED === 'true' && isPublicApiBaseSafe(apiBase, import.meta.env.DEV),
  trustedSources: (import.meta.env.VITE_PUBLIC_VERIFICATION_SOURCES ?? '').split(',').map((s: string) => s.trim()).filter(Boolean),
}
// Public AllowAny endpoints, independent of private API clients and login cookies.
const publicApi = axios.create({
  baseURL: apiBase, timeout: 30000,
  adapter: 'fetch', withCredentials: false,
  fetchOptions: { credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer', cache: 'no-store' },
  headers: { Accept: 'application/json' },
})
export const failure = (reason: VerificationFailure['reason'], retryAt: number | null = null): VerificationFailure => ({ kind: 'failure', reason, retryAt })
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const positiveInteger = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n > 0
export function parseVerification(value: unknown, method: 'credential' | 'document' | 'passport', trustedSources: string[], expectedReference?: string): VerificationOutcome {
  if (demoMode) return failure('disconnected')
  if (!record(value) || typeof value.source !== 'string' || value.source.length > 200) return failure('contract')
  if (/SIMULATED|MOCK|DEMO|TEST/i.test(value.source)) return failure('simulated')
  if (!trustedSources.includes(value.source)) return failure('untrusted')
  if (method === 'credential') {
    const statuses = { VALID: 'valid', REVOKED: 'revoked', EXPIRED: 'expired', INVALID: 'invalid', NOT_FOUND: 'not_found' } as const
    if (typeof value.status !== 'string' || !Object.hasOwn(statuses, value.status) || typeof value.verified !== 'boolean' || value.verified !== (value.status === 'VALID') || typeof value.credential_id !== 'string' || value.credential_id.length > 512 || !expectedReference || value.credential_id !== expectedReference) return failure('contract')
    return { kind: 'result', method, status: statuses[value.status as keyof typeof statuses], source: value.source, publicInfo: { credentialId: value.credential_id } }
  }
  const statuses = { VALID: 'valid', OUTDATED: 'outdated', INVALID: 'invalid', UNVERIFIABLE: 'unverifiable', REVOKED: 'revoked', EXPIRED: 'expired', NOT_FOUND: 'not_found', REPLACED: 'replaced', PENDING_BLOCKCHAIN: 'pending', NOT_ISSUED: 'not_issued' } as const
  if (typeof value.status !== 'string' || !Object.hasOwn(statuses, value.status) || typeof value.authentic !== 'boolean' || (method === 'document' && typeof value.message !== 'string')) return failure('contract')
  if (['VALID', 'OUTDATED'].includes(value.status) && !value.authentic) return failure('contract')
  if (['NOT_FOUND', 'NOT_ISSUED'].includes(value.status) && value.authentic) return failure('contract')
  if (value.authentic) {
    if (!positiveInteger(value.passport_version) || !positiveInteger(value.latest_version) || value.passport_version > value.latest_version || typeof value.is_latest !== 'boolean' || (value.is_latest && value.passport_version !== value.latest_version) || (!value.is_latest && value.passport_version === value.latest_version && !['REVOKED', 'REPLACED', 'EXPIRED', 'INVALID', 'UNVERIFIABLE', 'PENDING_BLOCKCHAIN'].includes(value.status)) || (value.status === 'VALID' && !value.is_latest) || (value.status === 'OUTDATED' && value.is_latest)) return failure('contract')
    const availability = blockchainAvailability(value.blockchain)
    const proof = Object.hasOwn(value, 'blockchain') && availability === 'missing' ? 'unavailable' : availability
    const reported = statuses[value.status as keyof typeof statuses]
    const status = (reported === 'valid' || reported === 'pending' || reported === 'unverifiable') && proof !== 'missing' && proof !== 'verified' ? (proof === 'failed' ? 'failed' : proof === 'pending' ? 'pending' : 'unverifiable') : reported
    return { kind: 'result', method, status, blockchain: proof, source: value.source, publicInfo: { passportVersion: value.passport_version, latestVersion: value.latest_version, isLatest: value.is_latest } }
  }
  if (['PENDING_BLOCKCHAIN', 'UNVERIFIABLE'].includes(value.status)) {
    const proof = blockchainAvailability(value.blockchain)
    return { kind: 'result', method, status: proof === 'failed' ? 'failed' : proof === 'pending' ? 'pending' : 'unverifiable', source: value.source, blockchain: proof === 'verified' ? 'unverifiable' : proof, publicInfo: {} }
  }
  if (value.is_latest !== null || value.passport_version !== null || value.latest_version !== null) return failure('contract')
  return { kind: 'result', method, status: statuses[value.status as keyof typeof statuses], source: value.source, blockchain: blockchainAvailability(value.blockchain), publicInfo: {} }
}
export function mapVerificationError(error: unknown, now = Date.now()): VerificationFailure {
  if (axios.isCancel(error)) return failure('canceled')
  if (!axios.isAxiosError(error)) return failure('contract')
  const status = error.response?.status
  if (status === 429) return failure('rate_limit', retryDeadline(error.response?.headers?.['retry-after'], now))
  if (status === 401 || status === 403) return failure('auth')
  // Bare HTTP 404 is a missing route/technical failure, not authoritative NOT_FOUND.
  if (status && [400,413,415,422].includes(status)) return failure('rejected')
  if (status) return failure('server')
  return failure(error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT' ? 'timeout' : 'network')
}
export async function lookupReference(reference: string, method: 'passport' | 'credential', signal: AbortSignal): Promise<VerificationOutcome> {
  if (demoMode) return failure('disconnected')
  if (validateReference(reference, method)) return failure('rejected')
  if (!verificationConfig.enabled || !verificationConfig.trustedSources.length) return failure('disconnected')
  try {
    if (method === 'passport') {
      const normalized = normalizePassportReference(reference)!
      const [kind, id] = normalized.split(':')
      const response = await publicApi.get(`verification/${kind}/${encodeURIComponent(id)}/`, { signal })
      const proof = record(response.data) && record(response.data.blockchain) ? response.data.blockchain : null
      if (blockchainAvailability(proof) === 'verified' && proof?.[kind === 'passport' ? 'passport_reference' : 'version_reference'] !== id) return failure('contract')
      return parseVerification(response.data, 'passport', verificationConfig.trustedSources)
    }
    const response = await publicApi.get(`verification/${encodeURIComponent(reference.trim())}/`, { signal })
    return parseVerification(response.data, 'credential', verificationConfig.trustedSources, reference.trim())
  } catch (error) { return mapVerificationError(error) }
}
export async function uploadPdf(file: File, signal: AbortSignal, progress: (percent: number | null) => void): Promise<VerificationOutcome> {
  if (demoMode) return failure('disconnected')
  if (validatePdf(file)) return failure('rejected')
  if (!verificationConfig.enabled || !verificationConfig.trustedSources.length) return failure('disconnected')
  const body = new FormData()
  // Empty browser MIME is permitted locally; Django requires application/pdf.
  body.append('file', file.type === 'application/pdf' ? file : new File([file], file.name, { type: 'application/pdf' }))
  try {
    const response = await publicApi.post('verification/document/', body, { signal, onUploadProgress: e => progress(e.total ? Math.min(100, Math.round(e.loaded / e.total * 100)) : null) })
    return parseVerification(response.data, 'document', verificationConfig.trustedSources)
  } catch (error) { return mapVerificationError(error) }
}
