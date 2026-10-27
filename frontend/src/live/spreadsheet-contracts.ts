import { object, rows, text } from '../services/product'
import type { RecordData } from '../services/product'
import { uuidPattern } from './passport'

export function parsePreview(value: unknown): RecordData {
  const data = object(value), report = object(data.report)
  if (!uuidPattern.test(text(data.id)) || !/^[a-f0-9]{64}$/.test(text(data.snapshot_sha256)) ||
    !['READY', 'PROCESSING', 'COMPLETED', 'FAILED'].includes(text(data.state)) ||
    !Number.isFinite(Date.parse(text(data.expires_at)))) throw new Error('PREVIEW_CONTRACT_ERROR')
  for (const key of ['valid_records', 'duplicate_records', 'invalid_records', 'review_records']) {
    if (!Number.isSafeInteger(report[key]) || Number(report[key]) < 0) throw new Error('PREVIEW_CONTRACT_ERROR')
  }
  rows(report.rows)
  if (data.result !== null) object(data.result)
  return data
}
