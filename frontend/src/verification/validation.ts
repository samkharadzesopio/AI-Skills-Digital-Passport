import type { VerificationMethod } from './contracts'
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
// UUID-based printed passport references come from backend/apps/passports/document_services.py.
const passportReference = /^passport(?:-version)?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export function normalizePassportReference(value: string): string | null {
  let reference = value.trim()
  if (/^https?:/i.test(reference)) {
    try {
      const url = new URL(reference)
      if (typeof window === 'undefined' || url.origin !== window.location.origin || url.username || url.password || url.hash) return null
      if (url.pathname === '/verify/qr') {
        if (url.searchParams.getAll('reference').length !== 1 || [...url.searchParams.keys()].some(key => key !== 'reference')) return null
        reference = url.searchParams.get('reference') ?? ''
      } else return null
    } catch { return null }
  }
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(reference)) reference = `passport:${reference}`
  return passportReference.test(reference) ? reference.toLowerCase() : null
}
export function validateReference(value: string, method: Exclude<VerificationMethod, 'document'>): 'referenceRequired' | 'passportFormat' | 'credentialFormat' | null {
  const reference = value.trim()
  if (!reference) return 'referenceRequired'
  if (method === 'passport') return normalizePassportReference(reference) ? null : 'passportFormat'
  // Django's <str:credential_id> defines a nonempty path segment, not a published ID regex.
  // The length bound is a UI transport limit, not an official identifier format.
  const unsafeCharacter = Array.from(reference).some(c => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127 || c === '/' || c === '\\')
  return reference.length > 512 || unsafeCharacter || reference === '.' || reference === '..' || /^passport(?:-version)?:/i.test(reference) ? 'credentialFormat' : null
}
export function retryDeadline(value: unknown, now = Date.now()): number {
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) {
    const seconds = Number(value)
    if (Number.isSafeInteger(seconds) && seconds <= 31536000) return now + seconds * 1000
  }
  if (typeof value === 'string') { const date = Date.parse(value); if (Number.isFinite(date) && date > now) return date }
  return now + 60000
}
