import { useEffect, useRef, useState } from 'react'
import type { DragEvent, FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Clock3, FileCheck2, FileText, Fingerprint, LoaderCircle, Search, ShieldCheck, ShieldX, UploadCloud, X } from 'lucide-react'
import { verificationConfig, lookupReference, uploadPdf } from './service'
import { validatePdf, validateReference } from './validation'
import { useCooldown, useVerificationRequest, useVerificationState } from './state'
import { useVerificationText } from './i18n'
import type { VerificationOutcome } from './contracts'

export function ServiceNotice() {
  const t = useVerificationText()
  return !verificationConfig.enabled || !verificationConfig.trustedSources.length ? <p className="verify-service-notice"><Clock3 size={18}/>{t('serviceNotice')}</p> : null
}
export function VerificationLanding() {
  const t = useVerificationText()
  return <><section className="verify-hero"><span className="verify-kicker"><ShieldCheck size={15}/>{t('trust')}</span><h1>{t('title')}</h1><p>{t('intro')}</p><span className="verify-public-tag">{t('noLogin')}</span><div className="verify-hero-orbit" aria-hidden="true"><Fingerprint size={100}/></div></section><ServiceNotice/><div className="verify-methods">{[{ to: '/verify/reference', title: t('lookup'), description: t('referenceHint'), icon: Search },{ to: '/verify/upload', title: t('upload'), description: t('pdfHint'), icon: FileCheck2 }].map(method => <Link className="verify-method-card" to={method.to} key={method.to}><span className="verify-method-icon"><method.icon size={25}/></span><h2>{method.title}</h2><p>{method.description}</p><span className="verify-method-action">{method.title}<ArrowRight size={17}/></span></Link>)}</div><section id="how-it-works" className="verify-how"><span className="eyebrow">{t('process')}</span><h2>{t('how')}</h2><ol>{[{ title: t('stepOne'), text: t('stepOneText') },{ title: t('stepTwo'), text: t('stepTwoText') },{ title: t('stepThree'), text: t('stepThreeText') }].map((step,i) => <li key={step.title}><span>{String(i + 1).padStart(2,'0')}</span><h3>{step.title}</h3><p>{step.text}</p></li>)}</ol></section></>
}
function CooldownNotice() { const seconds = useCooldown(), t = useVerificationText(); return seconds > 0 ? <p className="verify-cooldown" role="status">{t('rate_limit')} {t('cooldown')} {seconds} {t('seconds')}.</p> : null }
export function ReferenceVerification({ initialReference = '', initialMethod = 'passport', qr = false }: { initialReference?: string; initialMethod?: 'passport' | 'credential'; qr?: boolean }) {
  const t = useVerificationText(), [reference, setReference] = useState(initialReference), [method, setMethod] = useState(initialMethod), [error, setError] = useState('')
  const request = useVerificationRequest(), seconds = useCooldown(), { setOutcome } = useVerificationState()
  useEffect(() => setOutcome(null), [setOutcome])
  function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    const invalid = validateReference(reference, method)
    if (invalid) { setError(t(invalid)); return }
    void request.run(signal => lookupReference(reference.trim(), method, signal))
  }
  return <div className="verify-form-page"><Link className="verify-back" to="/verify">← {t('back')}</Link><div className="verify-page-title"><span className="verify-method-icon"><Search size={26}/></span><h1>{t(qr ? 'qrTitle' : 'lookup')}</h1><p>{t(qr ? 'qrHint' : 'intro')}</p></div><ServiceNotice/><div className="verify-white-card"><form onSubmit={submit}><label htmlFor="reference-method">{t('referenceType')}</label><select id="reference-method" value={method} disabled={request.pending} onChange={e => { setMethod(e.target.value as 'passport' | 'credential'); setError('') }}><option value="passport">{t('passport')}</option><option value="credential">{t('credential')}</option></select><label htmlFor="verification-reference">{t('reference')}</label><input id="verification-reference" value={reference} autoComplete="off" spellCheck={false} autoCapitalize="none" maxLength={512} disabled={request.pending} aria-invalid={!!error} aria-describedby="reference-help reference-error" onChange={e => { setReference(e.target.value); setError('') }}/><p id="reference-help" className="verify-help">{t(method === 'passport' ? 'referenceHint' : 'credentialHint')}</p><p id="reference-error" className={error ? 'error' : ''} role="alert">{error}</p><CooldownNotice/>{request.canceled && <p role="status" className="verify-help">{t('canceled')}</p>}<button className="button primary verify-submit" disabled={request.pending || seconds > 0}>{request.pending ? <><LoaderCircle size={17} className="spin"/>{t('checking')}</> : <>{t('check')}<ArrowRight size={17}/></>}</button>{request.pending && <button type="button" className="button" onClick={request.cancel}>{t('cancel')}</button>}</form></div></div>
}
export function PdfVerification() {
  const t = useVerificationText(), [file, setFile] = useState<File | null>(null), [error, setError] = useState(''), [dragging, setDragging] = useState(false), input = useRef<HTMLInputElement>(null)
  const request = useVerificationRequest(), seconds = useCooldown(), { setOutcome } = useVerificationState()
  useEffect(() => setOutcome(null), [setOutcome])
  function select(files: FileList | null) {
    setFile(null); setError('')
    if (!files?.length) return
    if (files.length !== 1) { setError(t('pdfType')); return }
    const invalid = validatePdf(files[0])
    if (invalid) { setError(t(invalid)); return }
    setFile(files[0])
  }
  function drop(e: DragEvent) { e.preventDefault(); setDragging(false); if (!request.pending) { if (input.current) input.current.value = ''; select(e.dataTransfer.files) } }
  function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    if (!file) { setError(t('selectPdf')); return }
    const invalid = validatePdf(file)
    if (invalid) { setError(t(invalid)); return }
    void request.run((signal, progress) => uploadPdf(file, signal, progress))
  }
  return <div className="verify-form-page"><Link className="verify-back" to="/verify">← {t('back')}</Link><div className="verify-page-title"><span className="verify-method-icon"><FileCheck2 size={26}/></span><h1>{t('pdfTitle')}</h1><p>{t('pdfHint')}</p></div><ServiceNotice/><div className="verify-white-card"><form onSubmit={submit}><div className={`verify-dropzone ${dragging ? 'is-dragging' : ''}`} onDragOver={e => { e.preventDefault(); if (!request.pending) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={drop}><UploadCloud size={40}/><h2>{t('drop')}</h2><label className="button" htmlFor="verification-pdf">{t('choose')}</label><input ref={input} id="verification-pdf" type="file" accept=".pdf,application/pdf" disabled={request.pending} aria-describedby="pdf-help pdf-error" onChange={e => select(e.target.files)}/></div>{file && <div className="verify-selected"><FileText size={24}/><div><strong>{file.name}</strong><p>{(file.size / (1024 * 1024)).toFixed(2)} MB · {file.size.toLocaleString()} bytes</p></div><button type="button" className="button" disabled={request.pending} aria-label={t('remove')} onClick={() => { setFile(null); setError(''); if (input.current) input.current.value = '' }}><X size={17}/></button></div>}<p id="pdf-help" className="verify-help">{t('fileDisclaimer')}</p><p id="pdf-error" className={error ? 'error' : ''} role="alert">{error}</p><CooldownNotice/>{request.pending && <div className="verify-progress" role="status"><p>{request.progress === 100 ? t('waiting') : request.progress === null ? t('preparing') : t('uploading')}</p><progress max={100} value={request.progress ?? undefined} aria-label={t('uploading')}/>{request.progress !== null && <span>{request.progress}%</span>}</div>}{request.canceled && <p role="status" className="verify-help">{t('canceled')}</p>}<button className="button primary verify-submit" disabled={request.pending || !file || seconds > 0}>{request.pending ? <><LoaderCircle className="spin" size={17}/>{t('checking')}</> : <>{t('submitPdf')}<ShieldCheck size={17}/></>}</button>{request.pending && <button className="button" type="button" onClick={request.cancel}>{t('cancel')}</button>}</form></div></div>
}
export function VerificationResultView({ outcome }: { outcome: VerificationOutcome | null }) {
  const t = useVerificationText()
  if (!outcome) return <div className="verify-white-card verify-empty"><Search size={40}/><h1>{t('noResult')}</h1><p>{t('noResultText')}</p><Link className="button primary" to="/verify">{t('newCheck')}</Link></div>
  if (outcome.kind === 'failure') return <div className="verify-white-card verify-result verify-failure" role="alert"><span className="verify-result-icon"><Clock3 size={44}/></span><span className="verify-kicker">{t('result')}</span><h1>{t('unavailable')}</h1><p>{t('unavailableText')}</p><div className="verify-result-detail">{t(outcome.reason)}</div><Link className="button primary" to="/verify">{t('newCheck')}</Link></div>
  const successful = outcome.status === 'valid', uncertain = outcome.status === 'outdated' || outcome.status === 'unverifiable'
  const descriptions = { valid: 'validText', revoked: 'revokedText', expired: 'expiredText', invalid: 'invalidText', not_found: 'notFoundText', outdated: 'outdatedText', unverifiable: 'unverifiableText' } as const
  const Icon = successful ? CheckCircle2 : uncertain ? Clock3 : ShieldX
  return <div className={`verify-white-card verify-result ${successful ? 'verify-valid' : uncertain ? 'verify-uncertain' : 'verify-invalid'}`} role="status"><span className="verify-result-icon"><Icon size={44}/></span><span className="verify-kicker">{t('result')}</span><h1>{t(outcome.status === 'valid' && outcome.method === 'credential' ? 'validCredential' : outcome.status)}</h1><p>{t(descriptions[outcome.status])}</p><dl>{outcome.publicInfo.credentialId !== undefined && <><dt>{t('credentialId')}</dt><dd>{outcome.publicInfo.credentialId}</dd></>}{outcome.publicInfo.passportVersion !== undefined && <><dt>{t('version')}</dt><dd>{outcome.publicInfo.passportVersion}</dd></>}{outcome.publicInfo.latestVersion !== undefined && <><dt>{t('latestVersion')}</dt><dd>{outcome.publicInfo.latestVersion}</dd></>}{outcome.publicInfo.isLatest !== undefined && <><dt>{t('isLatest')}</dt><dd>{t(outcome.publicInfo.isLatest ? 'yes' : 'no')}</dd></>}<dt>{t('source')}</dt><dd>{outcome.source}</dd></dl><p className="verify-help">{t('publicOnly')}</p><Link className="button primary" to="/verify">{t('newCheck')}</Link></div>
}
export function VerificationResults() { const { outcome } = useVerificationState(); return <div className="verify-form-page"><VerificationResultView outcome={outcome}/><CooldownNotice/></div> }
export function QrVerification() {
  const { reference: pathReference } = useParams(), [search] = useSearchParams(), t = useVerificationText()
  const references = search.getAll('reference'), kinds = search.getAll('kind')
  const value = pathReference ?? references[0] ?? '', kind = kinds[0] ?? 'passport'
  if (!value || references.length > (pathReference ? 0 : 1) || kinds.length > 1 || (kind !== 'passport' && kind !== 'credential') || validateReference(value, kind)) return <div className="verify-white-card verify-empty"><h1>{t('qrTitle')}</h1><p role="alert">{t('qrMissing')}</p><Link className="button primary" to="/verify/reference">{t('lookup')}</Link></div>
  return <ReferenceVerification key={`${kind}:${value}`} initialReference={value} initialMethod={kind} qr/>
}
export function VerificationNotFound() { const t = useVerificationText(); return <div className="verify-white-card verify-empty"><h1>{t('notFoundPage')}</h1><Link className="button primary" to="/verify">{t('back')}</Link></div> }
