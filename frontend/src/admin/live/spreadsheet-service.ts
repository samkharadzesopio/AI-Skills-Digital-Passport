import axios from 'axios'
import { api } from '../../services/api'
import { demoMode } from '../../demo/mode'
import { parsePage, uuid } from '../../student/contracts'
import { AdminError } from './service'
import { automaticPoll, automaticSource, parsePreview, profile } from './spreadsheet-contracts'
import type { ImportPreview, ImportProfile } from './spreadsheet-contracts'

const problems: Record<string, string> = {
  PREVIEW_DIGEST_MISMATCH: 'The snapshot does not match the reviewed preview. Create and review a new preview.',
  SOURCE_CHANGED_REVIEW_REQUIRED: 'The Google source changed. Create and review a new preview before importing.',
  PREVIEW_EXPIRED: 'This preview expired. Create and review a new preview.',
  PREVIEW_EXPIRED_OR_ATTEMPTS_EXHAUSTED: 'This preview expired or reached its retry limit. Create a new preview and inspect import history.',
  IMPORT_ALREADY_RUNNING: 'This import is processing. Refresh its outcome and check history before retrying.',
  IMPORT_LEASE_LOST: 'Another attempt owns this import. Refresh its outcome and check history.',
  NO_ELIGIBLE_RECORDS: 'There are no eligible records to import. Correct the source or obtain institutional confirmation.',
  GOOGLE_SOURCE_UNAVAILABLE: 'Google Sheets is unavailable. An administrator must configure the approved source and read-only provider credentials.',
  SOURCE_PROFILE_DISABLED_OR_CHANGED: 'This approved profile was disabled or changed. Refresh the profiles and create a new preview.',
  INSTITUTIONAL_SOURCE_OR_ISSUER_NOT_CONFIGURED: 'The institutional source or trusted issuer needs configuration. Contact the administrator.',
  INVALID_SPREADSHEET_OR_MAPPING: 'The workbook does not match the approved profile. Check the worksheet, header aliases, dates and file format.',
  INVALID_AUTOMATION_CONTROL: 'Select a polling interval from 60 to 86400 seconds, provide an authorization reference and explicitly confirm continuing source processing.',
  AUTOMATION_APPROVED_AWARD_PROFILE_REQUIRED: 'Automatic polling requires an independently approved Google awarded-skill profile.',
}
export class SpreadsheetError extends AdminError {
  constructor(status: number, code: string, retryAfter: number) { super(status, retryAfter); this.message = problems[code] ?? this.message }
}
async function request<T>(method: 'get' | 'post', path: string, parse: (v: unknown) => T, body?: unknown, signal?: AbortSignal): Promise<T> {
  if (demoMode) throw new AdminError()
  try { const response = method === 'get' ? await api.get(path, { signal }) : await api.post(path, body, { signal }); return parse(response.data) }
  catch (e) { if (axios.isCancel(e)) throw e; if (axios.isAxiosError(e)) { const n = Number(e.response?.headers['retry-after']), value: unknown = e.response?.data?.code; throw new SpreadsheetError(e.response?.status ?? 0, typeof value === 'string' && Object.hasOwn(problems, value) ? value : '', Number.isFinite(n) ? Math.min(3600, Math.max(0, n)) : 0) } throw new AdminError() }
}
export function getProfiles(page: number, signal?: AbortSignal) { if (!Number.isSafeInteger(page) || page < 1) throw new AdminError(400); return request('get', `integrations/import/profiles/?page=${page}`, v => parsePage(v, profile), undefined, signal) }
export function previewImport(selected: ImportProfile, file: File | null, signal?: AbortSignal) {
  const id = uuid(selected.id)
  if (selected.source === 'BTU_GOOGLE_SHEETS') return request('post', 'integrations/import/google-sheets/preview/', parsePreview, { profile_id: id }, signal)
  if (!file || !file.name.toLowerCase().endsWith('.xlsx') || !file.size || file.size > 5 * 1024 * 1024) throw new AdminError(400)
  const body = new FormData(); body.append('profile_id', id); body.append('file', file, 'approved-evidence.xlsx')
  return request('post', 'integrations/import/excel/preview/', parsePreview, body, signal)
}
export function refreshPreview(id: string, signal?: AbortSignal) { return request('get', `integrations/import/previews/${uuid(id)}/`, parsePreview, undefined, signal) }
export function confirmPreview(preview: ImportPreview, signal?: AbortSignal) {
  if (!/^[a-f0-9]{64}$/.test(preview.snapshot_sha256) || !['READY','FAILED'].includes(preview.state) || Date.parse(preview.expires_at) <= Date.now() || preview.report.valid_records < 1) throw new AdminError(409)
  return request('post', `integrations/import/previews/${uuid(preview.id)}/confirm/`, parsePreview, { confirm: true, snapshot_sha256: preview.snapshot_sha256 }, signal)
}
export function getAutomaticSources(page:number,signal?:AbortSignal) { if(!Number.isSafeInteger(page)||page<1) throw new AdminError(400); return request('get',`integrations/import/automatic-sources/?page=${page}`,v=>parsePage(v,automaticSource),undefined,signal) }
export function configureAutomaticSource(id:string, enabled:boolean, interval:number, reference:string, signal?:AbortSignal) {
  if(enabled&&(!Number.isSafeInteger(interval)||interval<60||interval>86400||!reference.trim()||reference.length>255)) throw new AdminError(400)
  return request('post',`integrations/import/automatic-sources/${uuid(id)}/`,automaticSource,enabled?{enabled:true,confirm:true,interval_seconds:interval,authorization_reference:reference.trim()}:{enabled:false},signal)
}
export function getAutomaticHistory(id:string,page:number,signal?:AbortSignal) { if(!Number.isSafeInteger(page)||page<1) throw new AdminError(400); return request('get',`integrations/import/automatic-sources/${uuid(id)}/history/?page=${page}`,v=>parsePage(v,automaticPoll),undefined,signal) }
