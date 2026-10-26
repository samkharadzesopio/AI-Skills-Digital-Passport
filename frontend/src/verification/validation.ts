import type { ReferenceKind } from './contracts'
export const MAX_PDF_BYTES = 5 * 1024 * 1024 // apps/verification/document_service.py
export function isPublicApiBaseSafe(value: string, development: boolean): boolean {
  if (value.startsWith('/') && !value.startsWith('//')) return !value.includes('\\') && !value.includes('?') && !value.includes('#')
  try {
    const url = new URL(value)
    return !url.username && !url.password && !url.search && !url.hash && (url.protocol === 'https:' || (development && url.protocol === 'http:' && ['localhost','127.0.0.1','[::1]'].includes(url.hostname)))
  } catch { return false }
}
export function validatePdf(file: Pick<File, 'name' | 'size' | 'type'>): 'pdfType' | 'pdfSize' | null {
  if (!file.name.toLowerCase().endsWith('.pdf') || (file.type && file.type !== 'application/pdf')) return 'pdfType'
  if (file.size <= 0 || file.size > MAX_PDF_BYTES) return 'pdfSize'
  return null
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export function normalizeReference(value: string, kind: ReferenceKind): { reference: string; kind: ReferenceKind } | null {
  let reference = value.trim(), actualKind = kind
  const prefix = /^(passport-version|passport|credential):(.*)$/i.exec(reference)
  if (prefix) {
    const suppliedKind = prefix[1].toLowerCase() as ReferenceKind
    if (suppliedKind !== kind && !(kind === 'passport' && suppliedKind === 'passport-version')) return null
    actualKind = suppliedKind; reference = prefix[2]
  }
  const unsafe = Array.from(reference).some(c => c.charCodeAt(0) <= 32 || c.charCodeAt(0) === 127 || c === '/' || c === '\\')
  if (!reference || reference.length > 512 || unsafe || reference === '.' || reference === '..') return null
  if (actualKind !== 'credential' && !uuid.test(reference)) return null
  // Canonicalize UUID spelling only; never interpret a student/internal ID as public.
  return { kind: actualKind, reference: uuid.test(reference) ? reference.toLowerCase() : reference }
}
export function validateReference(value: string, kind: ReferenceKind): 'referenceRequired' | 'passportFormat' | 'credentialFormat' | null {
  if (!value.trim()) return 'referenceRequired'
  return normalizeReference(value, kind) ? null : kind === 'credential' ? 'credentialFormat' : 'passportFormat'
}
export function parseReferenceLink(search: URLSearchParams, pathReference?: string) {
  const references = search.getAll('reference'), kinds = search.getAll('kind')
  if (references.length > (pathReference ? 0 : 1) || kinds.length > 1) return null
  const reference = pathReference ?? references[0] ?? ''
  const prefix = /^(passport-version|passport|credential):/i.exec(reference.trim())?.[1].toLowerCase()
  const kind = kinds[0] ?? prefix ?? 'passport'
  if (!['credential','passport','passport-version'].includes(kind)) return null
  return normalizeReference(reference, kind as ReferenceKind)
}
export function verificationLink(kind: ReferenceKind, reference: string, qr = false): string {
  const value = normalizeReference(reference, kind)
  if (!value) throw new Error('Invalid public verification reference')
  return `/verify/${qr ? 'qr' : 'reference'}?${new URLSearchParams({ kind: value.kind, reference: value.reference })}`
}
export function retryDeadline(value: unknown, now = Date.now()): number {
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) {
    const seconds = Number(value)
    if (Number.isSafeInteger(seconds) && seconds <= 31536000) return now + seconds * 1000
  }
  if (typeof value === 'string') { const date = Date.parse(value); if (Number.isFinite(date) && date > now) return date }
  return now + 60000
}
