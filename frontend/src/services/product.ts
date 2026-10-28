import axios from 'axios'
import { api } from './api'

export type RecordData = Record<string, unknown>
export function object(value: unknown): RecordData {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('The service returned an unsupported response.')
  return value as RecordData
}
export function text(value: unknown): string { return typeof value === 'string' || typeof value === 'number' ? String(value) : '' }
export function rows(value: unknown): RecordData[] {
  if (!Array.isArray(value)) throw new Error('The service returned an unsupported list.')
  return value.map(object)
}
function validateRecord(data: RecordData, depth = 0): void {
  if (depth > 12) throw new Error('RESPONSE_DEPTH_EXCEEDED')
  for (const key of ['results', 'recent_achievements', 'recent_credentials', 'achievements', 'skills', 'credentials']) {
    if (data[key] === undefined || data[key] === null) continue
    if (key === 'credentials' && !Array.isArray(data[key])) validateRecord(object(data[key]), depth + 1)
    else rows(data[key]).forEach(row => validateRecord(row, depth + 1))
  }
  for (const key of ['profile', 'skill', 'result', 'summary', 'latest_version', 'passport']) {
    if (data[key] !== undefined && data[key] !== null) validateRecord(object(data[key]), depth + 1)
  }
}
export function productError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    if (status === 401 || status === 403) return 'Your session or permissions do not allow this action. Sign in again or contact your administrator.'
    if (status === 404) return 'This resource or service is unavailable on the connected backend.'
    if (status === 429) return 'Too many requests. Wait before trying again.'
    if (status === 409) return 'The operation is pending or conflicts with the current record. Refresh its status before retrying.'
    if (status === 400 || status === 422) return 'The service rejected this request. Check the required fields and institutional records.'
    return 'The university service could not complete the request. Check your connection and try again.'
  }
  return 'The university service returned an unsupported response. No successful action was confirmed.'
}
export async function getProduct(path: string, signal?: AbortSignal): Promise<RecordData> {
  return parseProduct((await api.get(path, { signal })).data, path)
}
export function parseProduct(value: unknown, path = ''): RecordData {
  const data = object(value)
  validateRecord(data)
  if ('results' in data && data.next !== null && typeof data.next !== 'string') throw new Error('PAGINATION_CONTRACT_ERROR')
  if (path === 'student/dashboard/' || /^admin\/students\/[^/]+\/$/.test(path)) object(data.profile)
  if (path.endsWith('pdf/status/')) {
    if (!['NOT_REQUESTED', 'PENDING', 'GENERATING', 'ISSUED', 'FAILED'].includes(text(data.status)) || typeof data.available_for_download !== 'boolean') throw new Error('PDF_CONTRACT_ERROR')
  }
  if (path === 'student/passport/' && data.passport !== null && (typeof data.id !== 'string' || typeof data.public_reference !== 'string')) throw new Error('PASSPORT_CONTRACT_ERROR')
  return data
}
export async function getList(path: string, page: number, signal?: AbortSignal) {
  const data = await getProduct(path, signal)
  // Follow page numbers against the original trusted path, never server-provided URLs.
  const results = rows(data.results)
  if (typeof data.count !== 'number' || !Number.isSafeInteger(data.count) || data.count < 0) throw new Error('LIST_CONTRACT_ERROR')
  return { results, count: data.count, hasNext: data.next !== null, page }
}
export async function downloadPassport(prefix: string): Promise<void> {
  const response = await api.get(`${prefix}pdf/download/`, { responseType: 'blob' })
  if (!(response.data instanceof Blob) || !String(response.headers['content-type']).startsWith('application/pdf') || response.data.size === 0) throw new Error('PDF_CONTRACT_ERROR')
  const url = URL.createObjectURL(response.data), anchor = document.createElement('a')
  anchor.href = url; anchor.download = 'btu-ai-skills-passport.pdf'; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
