import type { Passport } from './contracts'
import { blockchainAvailability } from '../verification/blockchain'

export function passportState(passport: Passport) {
  const retired = ['REVOKED', 'REPLACED', 'EXPIRED', 'INVALID'].includes(passport.status) ||
    (!!passport.lifecycle_status && passport.lifecycle_status !== 'ACTIVE')
  const availability = blockchainAvailability(passport.blockchain)
  const proof = passport.blockchain && typeof passport.blockchain === 'object' && !Array.isArray(passport.blockchain)
    ? passport.blockchain as Record<string, unknown> : {}
  const currentValid = !retired && passport.lifecycle_status === 'ACTIVE' &&
    passport.status === 'BLOCKCHAIN_VERIFIED' && passport.latest_version?.status === 'ISSUED' &&
    availability === 'verified' && proof.passport_reference === passport.public_reference &&
    proof.version_reference === passport.latest_version.public_reference
  const label = retired ? `Inactive passport: ${passport.lifecycle_status || passport.status}` : currentValid
    ? `Blockchain verified${proof.environment === 'LOCAL_ANVIL' ? ' · Local Anvil' : ' · Polygon Amoy'}`
    : availability === 'pending' ? 'Blockchain confirmation pending'
    : availability === 'failed' ? 'Blockchain proof failed'
    : availability === 'not_configured' ? 'Blockchain not configured'
    : 'Blockchain verification unavailable'
  return { retired, currentValid, availability, label }
}
