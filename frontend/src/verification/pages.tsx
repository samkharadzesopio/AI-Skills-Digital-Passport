import { useEffect, useRef, useState } from 'react'
import type { DragEvent, FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Clock3, FileCheck2, FileText, LoaderCircle, Search, ShieldCheck, ShieldX, UploadCloud, X } from 'lucide-react'
import { verificationConfig, lookupReference, uploadPdf } from './service'
import { parseReferenceLink, validatePdf, validateReference, verificationLink } from './validation'
import { useCooldown, useVerificationRequest, useVerificationState } from './state'
import { useVerificationText } from './i18n'
import type { CredentialStatus, ReferenceKind, VerificationOutcome } from './contracts'

export function ServiceNotice() {
  const t = useVerificationText()
  return !verificationConfig.enabled || !verificationConfig.trustedSources.length ? <p className="verify-service-notice"><Clock3 size={18}/>{t('serviceNotice')}</p> : null
}
export function VerificationLanding() {
  const t = useVerificationText()
  return <><section className="verification-introduction"><span className="eyebrow">BUSINESS AND TECHNOLOGY UNIVERSITY</span><h1>{t('title')}</h1><p>{t('intro')}</p><p className="verify-help">{t('noLogin')}</p><nav className="verification-shortcuts" aria-label="Verification methods"><Link to="/verify/reference">{t('lookup')}</Link><Link to="/verify/upload">{t('upload')}</Link></nav></section><ServiceNotice/><div className="verification-forms"><ReferenceVerification embedded/><PdfVerification embedded/></div></>
}
function CooldownNotice() { const seconds = useCooldown(), t = useVerificationText(); return seconds > 0 ? <p className="verify-cooldown" role="status">{t('rate_limit')} {t('cooldown')} {seconds} {t('seconds')}.</p> : null }
export function ReferenceVerification({ initialReference = '', initialMethod = 'passport', qr = false, embedded = false }: { initialReference?: string; initialMethod?: ReferenceKind; qr?: boolean; embedded?: boolean }) {
  const t = useVerificationText(), [reference, setReference] = useState(initialReference), method = initialMethod, [error, setError] = useState('')
  const request = useVerificationRequest(), seconds = useCooldown(), { setOutcome } = useVerificationState()
  useEffect(() => setOutcome(null), [setOutcome])
  function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    const invalid = validateReference(reference, method)
    if (invalid) { setError(t(invalid === 'passportFormat' ? 'formatHelp' : invalid)); return }
    void request.run(signal => lookupReference(reference.trim(), method, signal), verificationLink(method, reference))
  }
  return <div className={embedded ? "verify-form-page embedded-verification" : "verify-form-page"}>{!embedded && <Link className="verify-back" to="/verify">← {t('back')}</Link>}<div className="verify-page-title"><span className="verify-method-icon"><Search size={26}/></span>{embedded ? <h2>{t('lookup')}</h2> : <h1>{t(qr ? 'qrTitle' : 'lookup')}</h1>}<p>{t(qr ? 'qrHint' : 'intro')}</p></div>{!embedded && <ServiceNotice/>}<div className="verify-white-card"><form onSubmit={submit}><input id="reference-method" type="hidden" value={method}/>{method === 'credential' && <p className="verify-help">{t('credential')}</p>}<label htmlFor="verification-reference">{t('reference')}</label><input id="verification-reference" value={reference} autoComplete="off" spellCheck={false} autoCapitalize="none" maxLength={512} disabled={request.pending} aria-invalid={!!error} aria-describedby="reference-help reference-error" onChange={e => { setReference(e.target.value); setError('') }}/><p id="reference-help" className="verify-help">{t(method === 'credential' ? 'credentialHint' : 'referenceHelp')}</p><p id="reference-error" className={error ? 'error' : ''} role="alert">{error}</p><CooldownNotice/>{request.canceled && <p role="status" className="verify-help">{t('canceled')}</p>}<button className="button primary verify-submit" disabled={request.pending || seconds > 0}>{request.pending ? <><LoaderCircle size={17} className="spin"/>{t('checking')}</> : <>{t('check')}<ArrowRight size={17}/></>}</button>{request.pending && <button type="button" className="button" onClick={request.cancel}>{t('cancel')}</button>}</form></div></div>
}
export function PdfVerification({ embedded = false }: { embedded?: boolean }) {
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
    void request.run((signal, progress) => uploadPdf(file, signal, progress), '/verify/upload')
  }
  return <div className={embedded ? "verify-form-page embedded-verification" : "verify-form-page"}>{!embedded && <Link className="verify-back" to="/verify">← {t('back')}</Link>}<div className="verify-page-title"><span className="verify-method-icon"><FileCheck2 size={26}/></span>{embedded ? <h2>{t('pdfTitle')}</h2> : <h1>{t('pdfTitle')}</h1>}<p>{t('pdfHint')}</p></div>{!embedded && <ServiceNotice/>}<div className="verify-white-card"><form onSubmit={submit}><div className={`verify-dropzone ${dragging ? 'is-dragging' : ''}`} onDragOver={e => { e.preventDefault(); if (!request.pending) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={drop}><UploadCloud size={40}/><h2>{t('drop')}</h2><label className="button" htmlFor="verification-pdf">{t('choose')}</label><input ref={input} id="verification-pdf" type="file" accept=".pdf,application/pdf" disabled={request.pending} aria-describedby="pdf-help pdf-error" onChange={e => select(e.target.files)}/></div>{file && <div className="verify-selected"><FileText size={24}/><div><strong>{file.name}</strong><p>{(file.size / (1024 * 1024)).toFixed(2)} MB · {file.size.toLocaleString()} bytes</p></div><button type="button" className="button" disabled={request.pending} aria-label={t('remove')} onClick={() => { setFile(null); setError(''); if (input.current) input.current.value = '' }}><X size={17}/></button></div>}<p id="pdf-help" className="verify-help">{t('fileDisclaimer')}</p><p id="pdf-error" className={error ? 'error' : ''} role="alert">{error}</p><CooldownNotice/>{request.pending && <div className="verify-progress" role="status"><p>{request.progress === 100 ? t('waiting') : request.progress === null ? t('preparing') : t('uploading')}</p><progress max={100} value={request.progress ?? undefined} aria-label={t('uploading')}/>{request.progress !== null && <span>{request.progress}%</span>}</div>}{request.canceled && <p role="status" className="verify-help">{t('canceled')}</p>}<button className="button primary verify-submit" disabled={request.pending || !file || seconds > 0}>{request.pending ? <><LoaderCircle className="spin" size={17}/>{t('checking')}</> : <>{t('submitPdf')}<ShieldCheck size={17}/></>}</button>{request.pending && <button className="button" type="button" onClick={request.cancel}>{t('cancel')}</button>}</form></div></div>
}
export function VerificationResultView({ outcome, retryPath, retryReady = true }: { outcome: VerificationOutcome | null; retryPath?: string | null; retryReady?: boolean }) {
  const t = useVerificationText()
  if (!outcome) return <div className="verify-white-card verify-empty"><Search size={40}/><h1>{t('noResult')}</h1><p>{t('noResultText')}</p><Link className="button primary" to="/verify">{t('newCheck')}</Link></div>
  if (outcome.kind === 'failure') return <div className="verify-white-card verify-result verify-failure" role="alert"><span className="verify-result-icon"><Clock3 size={44}/></span><span className="verify-kicker">{t('result')}</span><h1>{t('unavailable')}</h1><p>{t('unavailableText')}</p><div className="verify-result-detail">{t(outcome.reason)}</div>{retryPath && <Link className="button" to={retryPath} aria-disabled={!retryReady} onClick={e => { if (!retryReady) e.preventDefault() }}>{t('retry')}</Link>}<Link className="button primary" to="/verify">{t('newCheck')}</Link></div>
  const successful = outcome.status === 'valid', uncertain = outcome.status === 'outdated' || outcome.status === 'unverifiable' || outcome.status === 'pending'
  const descriptions = { valid: 'validText', revoked: 'revokedText', expired: 'expiredText', invalid: 'invalidText', not_found: 'notFoundText', outdated: 'outdatedText', unverifiable: 'unverifiableText', pending: 'pendingText', replaced: 'replacedText', not_issued: 'notIssuedText' } as const
  const info = outcome.publicInfo, Icon = successful ? CheckCircle2 : uncertain ? Clock3 : ShieldX
  const credential = outcome.method === 'credential'
  const revocation = info.passportStatus === 'revoked'
    ? { title: 'passportRevoked', description: 'passportRevokedText' } as const
    : info.credentialStatus === 'revoked'
      ? { title: 'supportRevoked', description: 'supportRevokedText' } as const
      : { title: 'recordRevoked', description: 'recordRevokedText' } as const
  const lifecycleText = { revoked: 'supportRevokedText', expired: 'supportExpiredText', invalid: 'supportInvalidText', unverifiable: 'validityUnavailableText', outdated: 'historicalText', pending: 'pendingText', replaced: 'replacedText', not_issued: 'notIssuedText' } as const
  const description = !credential && outcome.status === 'revoked' ? t(revocation.description) : !credential && info.authentic && outcome.status !== 'valid' && outcome.status !== 'not_found' ? t(lifecycleText[outcome.status]) : t(descriptions[outcome.status])
  const title = credential ? t(outcome.status === 'valid' ? 'validCredential' : outcome.status) : ['pending','replaced','not_issued'].includes(outcome.status) ? t(outcome.status as 'pending'|'replaced'|'not_issued') : outcome.status === 'revoked' ? t(revocation.title) : outcome.status === 'expired' ? t('supportExpired') : outcome.status === 'not_found' ? t('not_found') : t(outcome.method === 'document' ? 'documentResult' : 'passportResult')
  return <div className={`verify-white-card verify-result ${successful ? 'verify-valid' : uncertain ? 'verify-uncertain' : 'verify-invalid'}`} role="status" data-verification-status={outcome.status}>
    <span className="verify-result-icon"><Icon size={44}/></span><span className="verify-kicker">{t('result')}</span><h1>{title}</h1><p>{description}</p>
    <dl aria-label="Verification result facts">
      <dt>{t('authenticity')}</dt><dd data-fact="authenticity">{info.authentic === undefined ? t('notReported') : t(info.authentic ? 'authenticYes' : 'authenticUnknown')}</dd>
      {!credential && <><dt>{t('currency')}</dt><dd data-fact="currency">{info.isLatest === null ? t('unknown') : t(info.isLatest ? 'currencyLatest' : 'currencyHistorical')}</dd></>}
      <dt>{t('credentialValidity')}</dt><dd data-fact="credential-validity">{credential ? t(`state_${outcome.status === 'not_found' ? 'unverifiable' : outcome.status as CredentialStatus}`) : t(`state_${info.credentialStatus!}`)}</dd>
      {info.credentialId !== undefined && <><dt>{t('credentialId')}</dt><dd>{info.credentialId}</dd></>}
      {info.passportVersion != null && <><dt>{t('version')}</dt><dd>{info.passportVersion}</dd></>}
      {info.latestVersion != null && <><dt>{t('latestVersion')}</dt><dd>{info.latestVersion}</dd></>}
      {info.credentialCounts && Object.entries(info.credentialCounts).map(([status, count]) => <div className="verify-count" key={status}><dt>{t('credentialCounts')} · {t(`state_${status as CredentialStatus}`)}</dt><dd>{count}</dd></div>)}
      <dt>{t('source')}</dt><dd>{outcome.source}</dd>
    </dl>
    {info.authentic && outcome.status !== 'valid' && <p className="verify-help">{t('authenticLifecycle')}</p>}
    {outcome.method === 'document' && !info.authentic && <p className="verify-help">{t('documentUnknown')}</p>}
    <p className="verify-help" data-fact="blockchain">{outcome.blockchain === 'verified' && outcome.status === 'valid' ? t('proofVerified') : outcome.blockchain === 'pending' ? t('proofPending') : outcome.blockchain === 'failed' ? t('proofFailed') : outcome.blockchain ? t('proofUnavailable') : t('registryOnly')}</p><p className="verify-help">{t('publicOnly')}</p><Link className="button primary" to="/verify">{t('newCheck')}</Link>
  </div>
}
export function VerificationResults() { const { outcome, retryPath } = useVerificationState(), seconds = useCooldown(); return <div className="verify-form-page"><VerificationResultView outcome={outcome} retryPath={retryPath} retryReady={seconds === 0}/><CooldownNotice/></div> }
function InvalidReferenceLink() { const t = useVerificationText(); return <div className="verify-white-card verify-empty"><h1>{t('qrTitle')}</h1><p role="alert">{t('qrMissing')}</p><Link className="button primary" to="/verify/reference">{t('lookup')}</Link></div> }
export function ReferenceVerificationPage() {
  const [search] = useSearchParams()
  if (!search.has('reference') && !search.has('kind')) return <ReferenceVerification/>
  const input = parseReferenceLink(search)
  return input ? <ReferenceVerification key={`${input.kind}:${input.reference}`} initialReference={input.reference} initialMethod={input.kind}/> : <InvalidReferenceLink/>
}
export function QrVerification() {
  const { reference } = useParams(), [search] = useSearchParams(), input = parseReferenceLink(search, reference)
  return input ? <ReferenceVerification key={`${input.kind}:${input.reference}`} initialReference={input.reference} initialMethod={input.kind} qr/> : <InvalidReferenceLink/>
}
export function VerificationNotFound() { const t = useVerificationText(); return <div className="verify-white-card verify-empty"><h1>{t('notFoundPage')}</h1><Link className="button primary" to="/verify">{t('back')}</Link></div> }
