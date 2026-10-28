/** Backend proof facts, never a locally inferred chain verdict. */
export type BlockchainAvailability = 'missing' | 'pending' | 'failed' | 'unverifiable' | 'unavailable' | 'not_configured' | 'verified'
export function blockchainAvailability(value: unknown): BlockchainAvailability {
  if (value === undefined || value === null) return 'missing'
  if (typeof value !== 'object' || Array.isArray(value)) return 'unverifiable'
  const proof = value as Record<string, unknown>
  if (proof.status === 'NOT_CONFIGURED') return 'not_configured'
  const confirmations = proof.confirmations, required = proof.required_confirmations ?? 1
  if (proof.status === 'CONFIRMED' && proof.blockchain_verified === true &&
      proof.institutional_issuer_approved === true && proof.issuer_key_authorized === true &&
      proof.source === 'POLYGON_PDF_COMMITMENT_V1' && proof.passport_status === 'ACTIVE' &&
      proof.onchain_status === 'ACTIVE' && proof.registry_status === 'VALID' && proof.credential_status === 'VALID' &&
      ((proof.environment === 'LOCAL_ANVIL' && proof.chain_id === 31337) ||
       (proof.environment === 'POLYGON_AMOY' && proof.chain_id === 80002)) &&
      typeof proof.transaction_hash === 'string' && /^0x[0-9a-f]{64}$/i.test(proof.transaction_hash) &&
      typeof confirmations === 'number' && Number.isSafeInteger(confirmations) &&
      typeof required === 'number' && Number.isSafeInteger(required) && required > 0 && confirmations >= required) return 'verified'
  if (proof.status === 'PENDING_BLOCKCHAIN') return 'pending'
  if (proof.status === 'FAILED') return 'failed'
  if (proof.status === 'UNVERIFIABLE' || proof.status === 'NOT_FOUND') return 'unverifiable'
  return 'unavailable'
}
