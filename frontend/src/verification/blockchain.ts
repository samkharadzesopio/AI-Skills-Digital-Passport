// Provisional c8cc9fd evidence only. This adapter cannot emit a verified claim.
// Final proof DTO, deployment policy and reference binding require backend sign-off.
export type BlockchainAvailability = 'missing' | 'pending' | 'failed' | 'unverifiable' | 'unavailable'
export function blockchainAvailability(value: unknown): BlockchainAvailability {
  if (value === undefined || value === null) return 'missing'
  if (!value || typeof value !== 'object' || Array.isArray(value)) return 'unverifiable'
  const proof = value as Record<string, unknown>
  if (proof.status === 'PENDING_BLOCKCHAIN') return 'pending'
  if (proof.status === 'FAILED') return 'failed'
  if (proof.status === 'UNVERIFIABLE' || proof.status === 'NOT_FOUND') return 'unverifiable'
  // Even CONFIRMED is not sufficient to claim current passport validity.
  return 'unavailable'
}
