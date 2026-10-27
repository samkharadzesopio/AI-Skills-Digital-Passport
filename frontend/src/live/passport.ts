import { object, text } from '../services/product'
import type { RecordData } from '../services/product'
import { blockchainAvailability } from '../verification/blockchain'

export function passportPresentation(data: RecordData, current: boolean) {
  const status = text(data.status), lifecycle = text(data.lifecycle_status)
  const retired = ['REVOKED', 'REPLACED', 'EXPIRED', 'INVALID'].includes(status) || (!!lifecycle && lifecycle !== 'ACTIVE')
  const version = data.latest_version ? object(data.latest_version) : null
  const proof = data.blockchain && typeof data.blockchain === 'object' && !Array.isArray(data.blockchain) ? object(data.blockchain) : null
  // Current selection belongs to Django. A history/list result never selects itself.
  const legacyCurrent = current && !lifecycle && status === 'ISSUED' && !data.blockchain
  const currentValid = current && !retired && version?.status === 'ISSUED' &&
    (legacyCurrent || (lifecycle === 'ACTIVE' && status === 'BLOCKCHAIN_VERIFIED' && blockchainAvailability(proof) === 'verified' &&
      proof?.passport_reference === data.public_reference && proof?.version_reference === version.public_reference))
  const canPrepare = current && !retired && version?.status === 'ISSUED' &&
    (legacyCurrent || (lifecycle === 'ACTIVE' && ['PENDING_BLOCKCHAIN', 'BLOCKCHAIN_VERIFIED', 'UNVERIFIABLE', 'ISSUED'].includes(status)))
  const title = status === 'NOT_ISSUED' ? 'No passport issued yet' : retired ? 'Inactive passport record' : !current ? 'Historical passport record' : currentValid ? 'Current passport' : 'Passport awaiting confirmation'
  return { title, currentValid, canPrepare, retired, version }
}

export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
