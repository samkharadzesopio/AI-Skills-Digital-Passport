import { parseAchievement, parseCredential, parseDashboard, parseProfile, record, uuid } from '../../student/contracts'
import type { Achievement, Counts, Credential } from '../../student/contracts'
export { parseAchievement, parseDashboard, parseProfile }
export function text(v: unknown): string { if (typeof v !== 'string') throw new Error('ADMIN_CONTRACT'); return v }
export function integer(v: unknown): number { if (typeof v !== 'number' || !Number.isSafeInteger(v) || v < 0) throw new Error('ADMIN_CONTRACT'); return v }
export function boolean(v: unknown): boolean { if (typeof v !== 'boolean') throw new Error('ADMIN_CONTRACT'); return v }
export function items<T>(v: unknown, parse: (v: unknown) => T): T[] { if (!Array.isArray(v)) throw new Error('ADMIN_CONTRACT'); return v.map(parse) }
function choice<T extends string>(v: unknown, choices: readonly T[]): T { if (!choices.includes(v as T)) throw new Error('ADMIN_CONTRACT'); return v as T }
export interface AdminCredential extends Credential { student_id: string }
export function credential(v: unknown): AdminCredential { const r = record(v), result = parseCredential(r); choice(result.validity_status, ['VALID','EXPIRED','REVOKED','INVALID']); choice(result.status, ['ISSUED','REVOKED']); return { ...result, student_id: uuid(r.student_id) } }
export interface EligibleAchievement extends Achievement { credential_count: number }
export function achievement(v: unknown): EligibleAchievement { const r = record(v), a = parseAchievement(r); if (a.verification_status !== 'VERIFIED') throw new Error('ADMIN_CONTRACT'); return { ...a, credential_count: integer(r.credential_count) } }
export interface Statistics { students: number; passports: number; recognized_skills: number; verified_achievements: number; credentials: Counts }
export function statistics(v: unknown): Statistics { const r = record(v), counts = record(r.credentials); return { students: integer(r.students), passports: integer(r.passports), recognized_skills: integer(r.recognized_skills), verified_achievements: integer(r.verified_achievements), credentials: Object.fromEntries(['total','valid','expired','revoked','invalid'].map(k => [k, integer(counts[k])])) as unknown as Counts } }
export interface Mapping { course_id: string; course_name: string; minimum_grade: number; skill_codes: string[]; enabled: boolean }
export function mappings(v: unknown): Mapping[] { const r = record(v); if (r.source !== 'BACKEND_CONTROLLED_COURSE_MAPPINGS') throw new Error('ADMIN_CONTRACT'); return items(r.results, v => { const m = record(v); if (typeof m.minimum_grade !== 'number' || !Number.isFinite(m.minimum_grade) || m.minimum_grade < 0 || m.minimum_grade > 100) throw new Error('ADMIN_CONTRACT'); return { course_id: text(m.course_id), course_name: text(m.course_name), minimum_grade: m.minimum_grade, skill_codes: items(m.skill_codes, text), enabled: boolean(m.enabled) } }) }
export interface Event { id: string; source: string; source_event_id: string; state: string; attempts: number; retryable: boolean; next_retry_at: string | null; error_code: string; credential_id: string | null }
export function event(v: unknown): Event { const r = record(v); return { id: uuid(r.id), source: choice(r.source, ['BTU_CLASSROOM','BTU_EXCEL','BTU_GOOGLE_SHEETS']), source_event_id: text(r.source_event_id), state: choice(r.state, ['RECEIVED','PROCESSING','ACHIEVEMENTS_RECORDED','CREDENTIAL_ISSUED','FAILED']), attempts: integer(r.attempts), retryable: boolean(r.retryable), next_retry_at: r.next_retry_at === null ? null : text(r.next_retry_at), error_code: code(r.error_code), credential_id: r.credential_id === null ? null : uuid(r.credential_id) } }
export interface CursorPage<T> { results: T[]; next: string | null; previous: string | null }
function cursor(v: unknown): string | null {
  if (v === null) return null
  // Extract a bounded cursor only. Never navigate/fetch a server supplied URL.
  const u = new URL(text(v), 'http://pagination.invalid'), values = u.searchParams.getAll('cursor')
  if (values.length !== 1 || !/^[A-Za-z0-9+/=_:-]{1,1024}$/.test(values[0])) throw new Error('ADMIN_CONTRACT')
  return values[0]
}
export function cursorPage<T>(v: unknown, parse: (v: unknown) => T): CursorPage<T> { const r = record(v); return { results: items(r.results, parse), next: cursor(r.next), previous: cursor(r.previous) } }
function code(v: unknown): string { const s = text(v); if (!/^[A-Za-z0-9_]{0,100}$/.test(s)) throw new Error('ADMIN_CONTRACT'); return s }
export interface RowError { row: number; code: string }
export interface Summary { counts: Record<string, number>; errors: RowError[]; import_id?: number; error?: string }
export function summary(v: unknown): Summary { const r = record(v), counts: Record<string, number> = {}; for (const key of ['processed','awarded','issued','skipped','failed','would_issue','eligible_count','current_issued','current_failed','current_pending']) if (r[key] !== undefined) counts[key] = integer(r[key]); return { counts, errors: r.errors === undefined ? [] : items(r.errors, v => { const e = record(v); return { row: integer(e.row), code: code(e.type) } }), ...(r.import_id === undefined ? {} : { import_id: integer(r.import_id) }), ...(r.error === undefined ? {} : { error: code(r.error) }) } }
export interface ImportRun { id: number; source: string; state: string; summary: Summary; validation_errors: RowError[] }
export function importRun(v: unknown): ImportRun { const r = record(v); return { id: integer(r.id), source: choice(r.source, ['BTU_EXCEL','BTU_GOOGLE_SHEETS']), state: choice(r.state, ['RUNNING','COMPLETED','PARTIAL','FAILED']), summary: summary(r.summary), validation_errors: items(r.validation_errors, v => { const e = record(v); return { row: integer(e.row), code: code(e.code) } }) } }
// Only known validator text is shown. Provider exceptions and arbitrary messages
// cannot become UI diagnostics (the backend also persists sanitized codes).
function rowMessage(v: unknown): string { const s = text(v); return /^(Invalid (external_student_id|course_id|source_event_id|completion date)|Invalid or future completion date|Course is not completed|Course was not passed|Grade must be a finite number between 0 and 100)$/.test(s) ? s : 'Invalid completion evidence row' }
export function imported(v: unknown) { const r = record(v); choice(r.source, ['BTU_EXCEL','BTU_GOOGLE_SHEETS']); return { result: summary(r.result), validation_errors: items(r.validation_errors, v => { const e = record(v); return { row: integer(e.row), code: rowMessage(e.error) } }) } }
export function syncResult(v: unknown) { const r = record(v); if (r.source !== 'SIMULATED_BTU_CLASSROOM') throw new Error('ADMIN_CONTRACT'); return { status: choice(r.status, ['preview','completed']), counts: Object.fromEntries(['processed','issued','skipped','failed','would_issue','eligible_count'].map(k => [k, integer(r[k])])), errors: items(r.errors, v => { const e = record(v); return { event_id: e.event_id === null ? null : text(e.event_id), code: code(e.code) } }) } }
export function completions(v: unknown) { const r = record(v); if (r.source !== 'SIMULATED_BTU_CLASSROOM') throw new Error('ADMIN_CONTRACT'); integer(r.count); return items(r.results, v => { const c = record(v); if (c.grade !== null && (typeof c.grade !== 'number' || !Number.isFinite(c.grade))) throw new Error('ADMIN_CONTRACT'); return { event_id: text(c.event_id), student_id: text(c.student_id), course_id: text(c.course_id), course_name: text(c.course_name), enrollment_status: text(c.enrollment_status), completion_status: text(c.completion_status), grade: c.grade as number | null, passed: boolean(c.passed), completion_date: c.completion_date === null ? null : text(c.completion_date) } }) }
export function retryResult(v: unknown) { const r = record(v); return { result: choice(r.result, ['issued','skipped','failed']), state: text(r.state), error_code: code(r.error_code) } }
export function lifecycle(v: unknown) { const r = record(v); return { id: uuid(r.id), event_type: choice(r.event_type, ['ISSUED','REVOKED']), occurred_at: text(r.occurred_at) } }
