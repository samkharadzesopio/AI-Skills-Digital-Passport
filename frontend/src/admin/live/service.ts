import axios from 'axios'
import { api } from '../../services/api'
import { demoMode } from '../../demo/mode'
import { parsePage, parsePassport, parsePDF, parseSkill, parseVersion, uuid as parseUUID } from '../../student/contracts'
import * as dto from './contracts'

export class AdminError extends Error {
  status: number; retryAfter: number; retryAt: number
  constructor(status = 0, retryAfter = 0, configuration = false) {
    super(status === 401 || status === 403 ? 'Your session, permission or CSRF protection requires attention. Refresh your session or sign in again.' : configuration || status === 503 ? 'The required source, trusted issuer, Google Sheets configuration or storage is unavailable. Contact the local administrator.' : status === 400 ? 'The submitted fields or completion evidence were rejected. Check the required format and approved records.' : status === 404 ? 'This record or page is unavailable.' : status === 409 ? 'This operation conflicts with an existing request or is still processing. Check status before retrying.' : status === 422 ? 'The issued snapshot does not fit the BTU PDF template. Contact the university.' : status === 429 ? 'Too many requests. Wait before retrying.' : 'University records are unavailable. Retry when connected. No demo records have been substituted.')
    this.status = status; this.retryAfter = retryAfter; this.retryAt = Date.now() + retryAfter * 1000
  }
}
function uuid(v: unknown): string { try { return parseUUID(v) } catch { throw new AdminError(400) } }
function failure(e: unknown): never { if (axios.isCancel(e)) throw e; if (axios.isAxiosError(e)) { const n = Number(e.response?.headers['retry-after']), configuration = ['Google Sheets is not configured','Google Sheets credentials not configured','Institutional source is not authorized for credential issuance.'].includes(e.response?.data?.error); throw new AdminError(e.response?.status ?? 0, Number.isFinite(n) ? Math.min(3600, Math.max(0, n)) : 0, configuration) } throw new AdminError() }
async function request<T>(method: 'get' | 'post' | 'patch', path: string, parse: (v: unknown) => T, body?: unknown, signal?: AbortSignal): Promise<T> {
  if (demoMode) throw new AdminError()
  try { const r = method === 'get' ? await api.get(path, { signal }) : await api[method](path, body, { signal }); return parse(r.data) } catch (e) { return failure(e) }
}
function pagePath(path: string, page: number, filters: Record<string, string> = {}) { if (!Number.isSafeInteger(page) || page < 1) throw new AdminError(); return path + '?' + new URLSearchParams({ ...filters, page: String(page) }) }
function cursorPath(path: string, cursor: string | null) { if (cursor !== null && !/^[A-Za-z0-9+/=_:-]{1,1024}$/.test(cursor)) throw new AdminError(); return path + (cursor ? '?' + new URLSearchParams({ cursor }) : '') }
export const getStatistics = (s?: AbortSignal) => request('get', 'admin/statistics/', dto.statistics, undefined, s)
export const getStudents = (page = 1, filters: Record<string, string> = {}, s?: AbortSignal) => request('get', pagePath('admin/students/', page, filters), v => parsePage(v, dto.parseProfile), undefined, s)
export const getStudent = (id: string, s?: AbortSignal) => request('get', `admin/students/${uuid(id)}/`, dto.parseDashboard, undefined, s)
export type StudentInput = { external_student_id: string; first_name: string; last_name: string; email: string; program: string; education_level: string; student_status: string }
export type StudentEdit = Pick<StudentInput, 'program' | 'education_level' | 'student_status'>
export const createStudent = (body: StudentInput, s?: AbortSignal) => request('post', 'admin/students/', dto.parseProfile, body, s)
export const editStudent = (id: string, body: StudentEdit, s?: AbortSignal) => request('patch', `admin/students/${uuid(id)}/`, dto.parseProfile, body, s)
export const getAchievements = (id: string, page: number, s?: AbortSignal) => request('get', pagePath(`admin/students/${uuid(id)}/achievements/`, page), v => parsePage(v, dto.achievement), undefined, s)
export const getCredentials = (page: number, filters: Record<string, string>, s?: AbortSignal) => request('get', pagePath('admin/credentials/', page, filters), v => parsePage(v, dto.credential), undefined, s)
export const getCredential = (id: string, s?: AbortSignal) => request('get', `admin/credentials/${uuid(id)}/`, dto.credential, undefined, s)
export interface IssueInput { achievement_ids: string[]; idempotency_key: string; expires_at?: string | null }
export function issueCredential(body: IssueInput, s?: AbortSignal) { if (!body.achievement_ids.length || body.achievement_ids.length > 256 || new Set(body.achievement_ids).size !== body.achievement_ids.length || !body.idempotency_key || body.idempotency_key.length > 255) throw new AdminError(400); body.achievement_ids.forEach(uuid); return request('post', 'admin/credentials/issue/', dto.credential, body, s) }
export const revokeCredential = (id: string, reason: string, s?: AbortSignal) => request('post', `admin/credentials/${uuid(id)}/revoke/`, dto.credential, { reason }, s)
export const getHistory = (id: string, page: number, s?: AbortSignal) => request('get', pagePath(`admin/credentials/${uuid(id)}/history/`, page), v => parsePage(v, dto.lifecycle), undefined, s)
export const getPassports = (page: number, studentId = '', s?: AbortSignal) => request('get', pagePath('admin/passports/', page, studentId ? { student_id: uuid(studentId) } : {}), v => parsePage(v, parsePassport), undefined, s)
export const getVersions = (id: string, page: number, s?: AbortSignal) => request('get', pagePath(`admin/passports/${uuid(id)}/versions/`, page), v => parsePage(v, parseVersion), undefined, s)
function pdfPath(id: string, operation: string, versionId?: string) { return `admin/passports/${uuid(id)}/pdf/${operation}` + (versionId ? '?' + new URLSearchParams({ version_id: uuid(versionId) }) : '') }
export const pdfStatus = (id: string, versionId?: string, s?: AbortSignal) => request('get', pdfPath(id, 'status/', versionId), parsePDF, undefined, s)
export const generatePDF = (id: string, versionId?: string, s?: AbortSignal) => request('post', pdfPath(id, '', versionId), parsePDF, {}, s)
export async function downloadPDF(id: string, versionId?: string, signal?: AbortSignal) {
  if (demoMode) throw new AdminError()
  try { const r = await api.get(pdfPath(id, 'download/', versionId), { signal, responseType: 'blob' }), blob: Blob = r.data, filename = /(?:^|;)\s*filename="?(btu-passport-[0-9a-f-]{36}\.pdf)"?(?:;|$)/i.exec(String(r.headers['content-disposition']))?.[1]; if (!(blob instanceof Blob) || !String(r.headers['content-type']).startsWith('application/pdf') || await blob.slice(0, 5).text() !== '%PDF-' || !filename) throw new AdminError(); return { blob, filename } } catch (e) { return failure(e) }
}
export const getCatalog = (page: number, s?: AbortSignal) => request('get', pagePath('admin/catalog/', page), v => parsePage(v, parseSkill), undefined, s)
export const getMappings = (s?: AbortSignal) => request('get', 'admin/course-mappings/', dto.mappings, undefined, s)
export const getCompletions = (s?: AbortSignal) => request('get', 'integrations/classroom/completions/', dto.completions, undefined, s)
export const syncClassroom = (dry_run: boolean, s?: AbortSignal) => request('post', 'integrations/classroom/sync/', dto.syncResult, { dry_run }, s)
export const getSyncEvents = (cursor: string | null, s?: AbortSignal) => request('get', cursorPath('integrations/classroom/events/', cursor), v => dto.cursorPage(v, dto.event), undefined, s)
export const retrySync = (id: string, s?: AbortSignal) => request('post', `integrations/classroom/events/${uuid(id)}/retry/`, dto.retryResult, {}, s)
export const getImports = (cursor: string | null, s?: AbortSignal) => request('get', cursorPath('integrations/imports/', cursor), v => dto.cursorPage(v, dto.importRun), undefined, s)
export function getImportEvents(id: number, cursor: string | null, s?: AbortSignal) { if (!Number.isSafeInteger(id) || id < 1) throw new AdminError(); return request('get', cursorPath(`integrations/imports/${id}/events/`, cursor), v => dto.cursorPage(v, dto.event), undefined, s) }
export const retryImport = (id: string, s?: AbortSignal) => request('post', `integrations/imports/events/${uuid(id)}/retry/`, dto.retryResult, {}, s)
export function importExcel(file: File, s?: AbortSignal) { if (!file.name.toLowerCase().endsWith('.xlsx') || file.size < 1 || file.size > 5 * 1024 * 1024) throw new AdminError(400); const body = new FormData(); body.append('file', file, 'completion-evidence.xlsx'); return request('post', 'integrations/import/excel/', dto.imported, body, s) }
export const importSheet = (s?: AbortSignal) => request('post', 'integrations/import/google-sheets/', dto.imported, {}, s)
