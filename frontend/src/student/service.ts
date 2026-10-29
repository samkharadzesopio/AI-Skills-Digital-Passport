import axios from 'axios'
import { api } from '../services/api'
import { demoMode } from '../demo/mode'
import { parseAchievement, parseCredential, parseDashboard, parsePage, parsePassport, parsePDF, parseRecognized, parseVersion, uuid } from './contracts'
import type { PDFStatus } from './contracts'

export class StudentError extends Error {
  status: number
  retryAfter: number
  pdf: PDFStatus | null
  constructor(status: number, retryAfter = 0, pdf: PDFStatus | null = null) {
    super(status === 401 || status === 403 ? 'Your session or access has changed. Sign in again to continue.' : status === 404 ? 'This record is unavailable or does not belong to your account.' : status === 422 ? 'The issued data does not fit the BTU PDF template. Contact the university; retrying unchanged data will not fix it.' : status === 429 ? 'Too many requests. Please wait before retrying.' : status === 409 ? 'The PDF is being prepared. Check its status shortly.' : status === 503 ? 'PDF generation or storage is temporarily unavailable. Please retry later.' : 'Unable to load university records. Please retry. No demonstration data has been substituted.')
    this.status = status; this.retryAfter = retryAfter; this.pdf = pdf
  }
}
function failure(error: unknown): never {
  if (axios.isCancel(error)) throw error
  if (axios.isAxiosError(error)) {
    let pdf: PDFStatus | null = null
    try { pdf = parsePDF(error.response?.data) } catch { /* Not a PDF response. */ }
    const retry = Number(error.response?.headers?.['retry-after'])
    throw new StudentError(error.response?.status ?? 0, Number.isFinite(retry) ? Math.min(300, Math.max(0, retry)) : 0, pdf)
  }
  throw new StudentError(0)
}
async function get<T>(path: string, parse: (value: unknown) => T, signal?: AbortSignal): Promise<T> {
  if (demoMode) throw new StudentError(0)
  try { return parse((await api.get(path, { signal })).data) } catch (error) { return failure(error) }
}
function pagePath(resource: string, page: number) { if (!Number.isSafeInteger(page) || page < 1) throw new StudentError(0); return `student/${resource}/?page=${page}` }
// Never follow server-supplied pagination URLs or accept a student identifier.
export const getDashboard = (signal?: AbortSignal) => get('student/dashboard/', parseDashboard, signal)
export const getSkills = (page = 1, signal?: AbortSignal) => get(pagePath('skills', page), v => parsePage(v, parseRecognized), signal)
export const getAchievements = (page = 1, signal?: AbortSignal) => get(pagePath('achievements', page), v => parsePage(v, parseAchievement), signal)
export const getCredentials = (page = 1, signal?: AbortSignal) => get(pagePath('credentials', page), v => parsePage(v, parseCredential), signal)
export const getCredential = (id: string, signal?: AbortSignal) => get(`student/credentials/${uuid(id)}/`, parseCredential, signal)
export const getPassport = (signal?: AbortSignal) => get('student/passport/', parsePassport, signal)
export const getVersions = (page = 1, signal?: AbortSignal) => get(pagePath('passport/versions', page), v => parsePage(v, parseVersion), signal)
export const getVersion = (id: string, signal?: AbortSignal) => get(`student/passport/versions/${uuid(id)}/`, parseVersion, signal)
function pdfPath(versionId?: string) { return versionId ? `student/passport/versions/${uuid(versionId)}/pdf/` : 'student/passport/pdf/' }
export const getPDFStatus = (versionId?: string, signal?: AbortSignal) => get(pdfPath(versionId) + 'status/', parsePDF, signal)
export async function generatePDF(versionId?: string, signal?: AbortSignal): Promise<PDFStatus> {
  try { return parsePDF((await api.post(pdfPath(versionId), {}, { signal })).data) } catch (error) { return failure(error) }
}
export async function downloadPDF(versionId?: string, signal?: AbortSignal) {
  try {
    const response = await api.get(pdfPath(versionId) + 'download/', { responseType: 'blob', signal })
    const blob: Blob = response.data
    if (!(blob instanceof Blob) || !String(response.headers['content-type']).startsWith('application/pdf') || await blob.slice(0, 5).text() !== '%PDF-') throw new StudentError(0)
    // Accept only the backend's fixed ASCII filename pattern, never arbitrary paths/HTML.
    const name = /(?:^|;)\s*filename="?(btu-passport-[0-9a-f-]{36}\.pdf)"?(?:;|$)/i.exec(String(response.headers['content-disposition']))?.[1]
    if (!name) throw new StudentError(0)
    return { blob, filename: name }
  } catch (error) { return failure(error) }
}
