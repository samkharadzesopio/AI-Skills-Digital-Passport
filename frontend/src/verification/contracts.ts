export type ReferenceKind = 'passport' | 'passport-version' | 'credential'
export type VerificationMethod = ReferenceKind | 'document'
export type PublicStatus = 'valid' | 'revoked' | 'expired' | 'invalid' | 'not_found' | 'outdated' | 'unverifiable' | 'pending' | 'replaced' | 'not_issued'
export type FailureReason = 'disconnected' | 'simulated' | 'untrusted' | 'contract' | 'network' | 'server' | 'rate_limit' | 'rejected' | 'auth' | 'canceled' | 'timeout'
export type CredentialStatus = 'valid' | 'revoked' | 'expired' | 'invalid' | 'unverifiable'
export interface PublicResult {
  kind: 'result'; method: VerificationMethod; status: PublicStatus; source: string
  blockchain?: import('./blockchain').BlockchainAvailability
  // Explicit allowlist: no student details, arbitrary backend text or raw response objects.
  publicInfo: { credentialId?: string; authentic?: boolean; passportVersion?: number | null; latestVersion?: number | null; isLatest?: boolean | null; credentialStatus?: CredentialStatus; credentialCounts?: Partial<Record<Exclude<CredentialStatus, 'unverifiable'>, number>> }
}
export interface VerificationFailure { kind: 'failure'; reason: FailureReason; retryAt: number | null }
export type VerificationOutcome = PublicResult | VerificationFailure
export interface VerificationConfig { enabled: boolean; trustedSources: string[] }
