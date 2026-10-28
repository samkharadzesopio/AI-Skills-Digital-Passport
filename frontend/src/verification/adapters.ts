import { demoMode } from '../demo/mode'
import { blockchainAvailability } from './blockchain'
import type { CredentialStatus, PublicResult, PublicStatus, VerificationFailure, VerificationMethod, VerificationOutcome } from './contracts'
export const registrySources = {
  credential: 'POSTGRESQL_CREDENTIAL_REGISTRY', passport: 'POSTGRESQL_PASSPORT_REGISTRY',
  'passport-version': 'POSTGRESQL_PASSPORT_REGISTRY', document: 'POSTGRESQL_DOCUMENT_REGISTRY',
} as const
export const failure = (reason: VerificationFailure['reason'], retryAt: number | null = null): VerificationFailure => ({ kind: 'failure', reason, retryAt })
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const positiveInteger = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0
const statuses: Record<string, PublicStatus> = { VALID: 'valid', REVOKED: 'revoked', EXPIRED: 'expired', INVALID: 'invalid', NOT_FOUND: 'not_found', OUTDATED: 'outdated', UNVERIFIABLE: 'unverifiable', PENDING_BLOCKCHAIN: 'pending', REPLACED: 'replaced', NOT_ISSUED: 'not_issued' }
const credentialStatuses = ['VALID', 'REVOKED', 'EXPIRED', 'INVALID', 'UNVERIFIABLE']

/** Actual Django public serializers projected onto an explicit public allowlist.
 * No aggregate decision is calculated from counts in React. Future/private fields
 * and arbitrary message text never enter UI state. */
export function parseVerification(value: unknown, method: VerificationMethod, trustedSources: string[], expectedReference?: string): VerificationOutcome {
  if (demoMode) return failure('disconnected')
  if (!record(value) || typeof value.source !== 'string' || typeof value.status !== 'string' || !Object.hasOwn(statuses, value.status)) return failure('contract')
  if (/SIMULATED|MOCK|DEMO|TEST/i.test(value.source)) return failure('simulated')
  if (!trustedSources.includes(value.source) || value.source !== registrySources[method]) return failure('untrusted')
  if (method === 'credential') {
    if (!['VALID','REVOKED','EXPIRED','INVALID','NOT_FOUND'].includes(value.status) || typeof value.verified !== 'boolean' || value.verified !== (value.status === 'VALID') || typeof value.credential_id !== 'string' || value.credential_id.length > 512 || !expectedReference || value.credential_id !== expectedReference) return failure('contract')
    return { kind: 'result', method, status: statuses[value.status], source: value.source, publicInfo: { credentialId: value.credential_id } }
  }
  if (method === 'document' && (value.status === 'NOT_FOUND' || typeof value.message !== 'string')) return failure('contract')
  if (typeof value.authentic !== 'boolean' || (value.is_latest !== null && typeof value.is_latest !== 'boolean') || typeof value.credential_status !== 'string' || !credentialStatuses.includes(value.credential_status) || !record(value.credential_counts)) return failure('contract')
  const hasVersions = positiveInteger(value.passport_version) && positiveInteger(value.latest_version)
  if (!hasVersions && (value.passport_version !== null || value.latest_version !== null)) return failure('contract')
  if (hasVersions && (Number(value.passport_version) > Number(value.latest_version) || (value.is_latest !== null && value.is_latest !== (value.passport_version === value.latest_version) && !(value.is_latest === false && ['REVOKED','REPLACED'].includes(value.status))))) return failure('contract')
  if (!hasVersions && value.is_latest !== null) return failure('contract')
  if (!value.authentic && (hasVersions || value.is_latest !== null || value.credential_status !== 'UNVERIFIABLE' || Object.keys(value.credential_counts).length)) return failure('contract')
  if (['NOT_FOUND','NOT_ISSUED'].includes(value.status) && value.authentic) return failure('contract')
  if (value.status === 'VALID' && (!value.authentic || value.is_latest !== true || value.credential_status !== 'VALID')) return failure('contract')
  if (value.status === 'OUTDATED' && (!value.authentic || value.is_latest !== false || value.credential_status !== 'VALID')) return failure('contract')
  if (['REVOKED','EXPIRED'].includes(value.status) && value.authentic && !Object.hasOwn(value, 'blockchain') && value.credential_status !== value.status) return failure('contract')
  const counts: PublicResult['publicInfo']['credentialCounts'] = {}
  const keys = Object.keys(value.credential_counts)
  if (keys.length && (keys.length !== 4 || !['VALID','REVOKED','EXPIRED','INVALID'].every(k => Object.hasOwn(value.credential_counts as object, k)))) return failure('contract')
  for (const [key, count] of Object.entries(value.credential_counts)) {
    if (!['VALID','REVOKED','EXPIRED','INVALID'].includes(key) || typeof count !== 'number' || !Number.isSafeInteger(count) || count < 0) return failure('contract')
    counts[key.toLowerCase() as keyof typeof counts] = count
  }
  const blockchain = blockchainAvailability(value.blockchain)
  if (blockchain === 'verified' && expectedReference) {
    const proof = value.blockchain as Record<string, unknown>
    if (proof[method === 'passport' ? 'passport_reference' : 'version_reference'] !== expectedReference) return failure('contract')
  }
  // Registry/lifecycle decisions belong to Django. Legacy registry-only deployments
  // can report VALID while chain proof is unconfigured; show both facts separately.
  // A positive blockchain label still requires the complete proof guard above.
  const status = statuses[value.status]
  return { kind: 'result', method, status, source: value.source, ...(Object.hasOwn(value, 'blockchain') ? { blockchain } : {}), publicInfo: {
    authentic: value.authentic, isLatest: value.is_latest as boolean | null,
    passportVersion: value.passport_version as number | null, latestVersion: value.latest_version as number | null,
    credentialStatus: value.credential_status.toLowerCase() as CredentialStatus, credentialCounts: counts,
  } }
}
