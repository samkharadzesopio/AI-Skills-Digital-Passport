import { object, text } from '../services/product'
import type { RecordData } from '../services/product'

export function passportPresentation(data: RecordData, current: boolean) {
  const status = text(data.status), lifecycle = text(data.lifecycle_status)
  const retired = ['REVOKED', 'REPLACED', 'EXPIRED', 'INVALID'].includes(status) || (!!lifecycle && lifecycle !== 'ACTIVE')
  const version = data.latest_version ? object(data.latest_version) : null
  // Current selection belongs to Django. A history/list result never selects itself.
  const legacyCurrent = current && !lifecycle && status === 'ISSUED' && !data.blockchain
  const currentValid = legacyCurrent && version?.status === 'ISSUED'
  const canPrepare = current && !retired && version?.status === 'ISSUED' &&
    (legacyCurrent || (lifecycle === 'ACTIVE' && ['PENDING_BLOCKCHAIN', 'BLOCKCHAIN_VERIFIED'].includes(status)))
  const title = retired ? 'Inactive passport record' : !current ? 'Historical passport record' : currentValid ? 'Current passport' : 'Passport awaiting confirmation'
  return { title, currentValid, canPrepare, retired, version }
}

export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
