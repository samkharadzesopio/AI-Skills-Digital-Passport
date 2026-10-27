export type VerificationMethod = 'passport' | 'credential' | 'document'
export type PublicStatus = 'valid' | 'revoked' | 'expired' | 'invalid' | 'not_found' | 'outdated' | 'unverifiable' | 'replaced' | 'pending' | 'failed'
export type FailureReason = 'disconnected' | 'passport_endpoint_missing' | 'simulated' | 'untrusted' | 'contract' | 'network' | 'server' | 'rate_limit' | 'rejected' | 'auth' | 'canceled' | 'timeout'
export interface PublicResult {
  blockchain?: import('./blockchain').BlockchainAvailability
  kind: 'result'; method: VerificationMethod; status: PublicStatus; source: string
  // Explicit allowlist: no student details, arbitrary backend text or raw response objects.
  publicInfo: { credentialId?: string; passportVersion?: number; latestVersion?: number; isLatest?: boolean }
}
export interface VerificationFailure { kind: 'failure'; reason: FailureReason; retryAt: number | null }
export type VerificationOutcome = PublicResult | VerificationFailure
export interface VerificationConfig { enabled: boolean; trustedSources: string[] }
