import { record, uuid } from '../../student/contracts'
import { integer, items, text } from './contracts'

function choice<T extends string>(v: unknown, values: readonly T[]): T { if (!values.includes(v as T)) throw new Error('SPREADSHEET_CONTRACT'); return v as T }
function digest(v: unknown) { const s = text(v); if (!/^[a-f0-9]{64}$/.test(s)) throw new Error('SPREADSHEET_CONTRACT'); return s }
function code(v: unknown) { const s = text(v); if (!/^[A-Z0-9_]{1,100}$/.test(s)) throw new Error('SPREADSHEET_CONTRACT'); return s }
function positive(v: unknown) { const n = integer(v); if (!n) throw new Error('SPREADSHEET_CONTRACT'); return n }
export interface ImportProfile { id: string; key: string; version: number; source: 'BTU_EXCEL' | 'BTU_GOOGLE_SHEETS'; kind: 'COMPLETION' | 'SKILL_AWARD' }
export function profile(v: unknown): ImportProfile { const r = record(v), key = text(r.key); if (!/^[a-zA-Z0-9_-]{1,80}$/.test(key)) throw new Error('SPREADSHEET_CONTRACT'); return { id: uuid(r.id), key, version: positive(r.version), source: choice(r.source, ['BTU_EXCEL', 'BTU_GOOGLE_SHEETS']), kind: choice(r.kind, ['COMPLETION', 'SKILL_AWARD']) } }
export interface PreviewRow { row: number; status: 'VALID' | 'INVALID' | 'REVIEW' | 'DUPLICATE'; code: string; message: string }
export interface ImportPreview {
  id: string; snapshot_sha256: string; state: 'READY' | 'PROCESSING' | 'COMPLETED' | 'FAILED'; expires_at: string
  report: { profile_id: string; profile_key: string; profile_version: number; source: ImportProfile['source']; kind: ImportProfile['kind']; header_row: number; columns: Record<string, number>; total_rows: number; valid_records: number; duplicate_records: number; invalid_records: number; review_records: number; rows: PreviewRow[] }
  result: null | { import_id: number; counts: Record<string, number>; errors: { row: number; code: string }[] }
}
export function parsePreview(v: unknown): ImportPreview {
  const r = record(v), p = record(r.report), identity = profile({ id: p.profile_id, key: p.profile_key, version: p.profile_version, source: p.source, kind: p.kind }), expires = text(r.expires_at)
  if (!Number.isFinite(Date.parse(expires))) throw new Error('SPREADSHEET_CONTRACT')
  const columns: Record<string, number> = {}, allowed = ['external_student_id','source_event_id','skill_code','earned_on','approval_status','approval_reference','first_name','last_name','email','student_status','skill_name','category','stamp_type','course_id','completion_status','grade','passed','completion_date']
  for (const [field, value] of Object.entries(record(p.columns))) { const n = positive(value); if (!allowed.includes(field) || n > 26) throw new Error('SPREADSHEET_CONTRACT'); columns[field] = n }
  const rows = items(p.rows, value => { const row = record(value), message = text(row.message); if (message.length > 500) throw new Error('SPREADSHEET_CONTRACT'); return { row: positive(row.row), status: choice(row.status, ['VALID','INVALID','REVIEW','DUPLICATE']), code: code(row.code), message } })
  const report = { profile_id: identity.id, profile_key: identity.key, profile_version: identity.version, source: identity.source, kind: identity.kind, header_row: positive(p.header_row), columns, total_rows: integer(p.total_rows), valid_records: integer(p.valid_records), duplicate_records: integer(p.duplicate_records), invalid_records: integer(p.invalid_records), review_records: integer(p.review_records), rows }
  if (rows.length > 5000 || report.total_rows !== rows.length || report.total_rows !== report.valid_records + report.duplicate_records + report.invalid_records + report.review_records || rows.some((row, index) => rows.findIndex(v => v.row === row.row) !== index) || (['VALID','INVALID','REVIEW','DUPLICATE'] as const).some((s, i) => rows.filter(row => row.status === s).length !== [report.valid_records, report.invalid_records, report.review_records, report.duplicate_records][i])) throw new Error('SPREADSHEET_CONTRACT')
  let result: ImportPreview['result'] = null
  if (r.result !== null) { const value = record(r.result); result = { import_id: positive(value.import_id), counts: Object.fromEntries(['processed','awarded','issued','skipped','failed'].map(key => [key, integer(value[key])])), errors: items(value.errors, value => { const e = record(value); return { row: positive(e.row), code: code(e.code) } }) } }
  const state = choice(r.state, ['READY','PROCESSING','COMPLETED','FAILED'])
  if (state === 'COMPLETED' && result === null) throw new Error('SPREADSHEET_CONTRACT')
  return { id: uuid(r.id), snapshot_sha256: digest(r.snapshot_sha256), state, expires_at: expires, report, result }
}

export interface AutomaticSource {
  profile_id: string; profile_key: string; profile_version: number; profile_enabled: boolean
  enabled: boolean; interval_seconds: number; state: string; error_code: string
  last_checked_at: string | null; next_poll_at: string | null
}
const automaticStates = ['IDLE','PROCESSING','COMPLETED','UNCHANGED','EXCLUDED','FAILED','DISABLED'] as const
function optionalDate(v: unknown) { if (v === null) return null; const s = text(v); if (!Number.isFinite(Date.parse(s))) throw new Error('SPREADSHEET_CONTRACT'); return s }
function optionalCode(v: unknown) { return v === '' ? '' : code(v) }
export function automaticSource(v: unknown): AutomaticSource {
  const r = record(v), id = profile({id:r.profile_id,key:r.profile_key,version:r.profile_version,source:'BTU_GOOGLE_SHEETS',kind:'SKILL_AWARD'}), seconds=integer(r.interval_seconds)
  if (typeof r.enabled !== 'boolean' || typeof r.profile_enabled !== 'boolean' || seconds < 60 || seconds > 86400) throw new Error('SPREADSHEET_CONTRACT')
  return {profile_id:id.id,profile_key:id.key,profile_version:id.version,profile_enabled:r.profile_enabled,enabled:r.enabled,interval_seconds:seconds,state:choice(r.state,automaticStates),error_code:optionalCode(r.error_code),last_checked_at:optionalDate(r.last_checked_at),next_poll_at:optionalDate(r.next_poll_at)}
}
export interface AutomaticPoll { id:string; state:string; counts:Record<string,number>; error_code:string; started_at:string; finished_at:string|null; preview_id:string|null }
export function automaticPoll(v:unknown):AutomaticPoll {
  const r=record(v), counts:Record<string,number>={}, started=optionalDate(r.started_at)
  if (!started) throw new Error('SPREADSHEET_CONTRACT')
  for(const [key,value] of Object.entries(record(r.counts))) { if(!['total_rows','valid_records','duplicate_records','invalid_records','review_records','processed','awarded','issued','skipped','failed'].includes(key)) throw new Error('SPREADSHEET_CONTRACT'); counts[key]=integer(value) }
  return {id:uuid(r.id),state:choice(r.state,automaticStates),counts,error_code:optionalCode(r.error_code),started_at:started,finished_at:optionalDate(r.finished_at),preview_id:r.preview_id===null?null:uuid(r.preview_id)}
}
