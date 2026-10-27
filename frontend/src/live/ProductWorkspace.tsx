import { SpreadsheetImports } from './SpreadsheetImports'
import { PassportCard, OfficialBtuLogo } from '../components/PassportCard'
import { backendPassportCard } from '../components/passport-card-data'
import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, NavLink, useLocation, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Card, Loading } from '../components/ui'
import { LogoutButton } from '../auth/SessionPanel'
import { useSession } from '../auth/hooks'
import { api } from '../services/api'
import { downloadPassport, getList, getProduct, parseProduct, object, productError, rows, text } from '../services/product'
import type { RecordData } from '../services/product'
import { blockchainAvailability } from '../verification/blockchain'
import { passportPresentation, uuidPattern } from './passport'
import './product.css'

function Fields({ data, names }: { data: RecordData; names: string[] }) {
  return <dl className="live-fields">{names.filter(key => text(data[key])).map(key => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{text(data[key])}</dd></div>)}</dl>
}
function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return <Card><p role="alert">{productError(error)}</p>{retry && <button className="button" onClick={retry}>Retry</button>}</Card>
}
function Resource({ path, children }: { path: string; children: (data: RecordData) => ReactNode }) {
  const query = useQuery({ queryKey: ['live', path], queryFn: ({ signal }) => getProduct(path, signal), retry: false,
    refetchInterval: path === 'student/passport/' || /^admin\/students\/[^/]+\/$/.test(path) ? 15000 : false })
  if (query.isPending || query.isFetching) return <Loading/>
  if (query.isError) return <ErrorNotice error={query.error} retry={() => void query.refetch()}/>
  return children(query.data)
}
function Collection({ path, title, render }: { path: string; title: string; render?: (row: RecordData) => ReactNode }) {
  const [page, setPage] = useState(1)
  const query = useQuery({ queryKey: ['live', path, page], queryFn: ({ signal }) => getList(`${path}${path.includes('?') ? '&' : '?'}page=${page}`, page, signal), retry: false })
  return <section id={title === 'Passport version history' ? 'passport-history' : undefined}><h2>{title}</h2>{query.isPending ? <Loading/> : query.isError ? <ErrorNotice error={query.error} retry={() => void query.refetch()}/> : <><p>{query.data.count} records</p>{query.data.results.length === 0 ? <Card><p>No records available.</p></Card> : query.data.results.map((row, index) => <Card key={text(row.id) || index}>{render ? render(row) : <Fields data={row} names={['skill_name', 'category', 'subcategory', 'competency_level', 'earned_on', 'verification_status', 'public_reference', 'issuer_name', 'validity_status', 'issued_at', 'expires_at', 'status', 'state', 'source', 'error_code']}/>}{Array.isArray(row.validation_errors) && <ul>{rows(row.validation_errors).map((entry, j) => <li key={j}>Row {text(entry.row)}: {text(entry.code)}</li>)}</ul>}</Card>)}<div className="live-actions"><button className="button" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page}</span><button className="button" disabled={!query.data.hasNext} onClick={() => setPage(page + 1)}>Next</button></div></>}</section>
}
function Achievement({ data }: { data: RecordData }) {
  return <><Fields data={data.skill ? object(data.skill) : data} names={['skill_name', 'category', 'subcategory', 'competency_level']}/><Fields data={data} names={['id', 'earned_on', 'verification_status', 'course_reference']}/></>
}
function Credential({ data }: { data: RecordData }) {
  return <><Fields data={data} names={['public_reference', 'issuer_name', 'validity_status', 'issued_at', 'expires_at', 'revoked_at']}/>{Array.isArray(data.achievements) && rows(data.achievements).map((award, i) => <Achievement key={i} data={award}/>)}</>
}
function Profile({ data }: { data: RecordData }) {
  return <Fields data={data} names={['first_name', 'last_name', 'email', 'external_student_id', 'program', 'education_level', 'student_status']}/>
}
function Dashboard({ data, student = false }: { data: RecordData; student?: boolean }) {
  const noPassport = data.passport === null || (data.passport && object(data.passport).status === 'NOT_ISSUED')
  if (student) {
    const profile = data.profile ? object(data.profile) : {}, passport = data.passport && !noPassport ? object(data.passport) : null
    const state = passport ? passportPresentation(passport, true) : null, proof = blockchainAvailability(passport?.blockchain)
    const passportStatus = state?.retired ? text(passport?.lifecycle_status) || text(passport?.status) : state?.currentValid && proof === 'verified' ? 'Blockchain verified' : proof === 'pending' ? 'Blockchain confirmation pending' : proof === 'failed' ? 'Blockchain proof failed' : proof === 'not_configured' ? 'Blockchain not configured' : `${text(passport?.status) === 'BLOCKCHAIN_VERIFIED' ? 'University record' : text(passport?.status)} / Blockchain proof not confirmed`
    return <div className="student-dashboard"><section className="dashboard-passport" aria-label="Your Digital Passport">{passport ? <PassportCard data={{ ...backendPassportCard(passport, profile), status: passportStatus }} compact/> : <Card><h2>{noPassport ? 'No passport issued yet' : 'Passport summary unavailable'}</h2><p>Your issued passport will appear here after university recognition.</p></Card>}<DashboardActions passport={passport}/></section></div>
  }
  return <>{student && <p className="student-dashboard-greeting">{text(data.profile && object(data.profile).first_name) ? 'Welcome, ' + text(object(data.profile).first_name) : 'Your Digital Passport'}</p>}{student && (data.passport && !noPassport ? <PassportCard data={backendPassportCard(object(data.passport), object(data.profile))}/> : noPassport ? <Card><h2>No passport issued yet</h2><p>Your issued passport will appear here after university recognition.</p></Card> : <Card><p>Passport summary unavailable. Open your passport to refresh its current status.</p></Card>)}<Card>{data.profile ? <Profile data={object(data.profile)}/> : <Fields data={data} names={['students', 'passports']}/>}<Fields data={data} names={['recognized_skills', 'verified_achievements']}/>{!!data.credentials && <Fields data={object(data.credentials)} names={['total', 'valid', 'expired', 'revoked', 'invalid', 'VALID', 'EXPIRED', 'REVOKED', 'INVALID']}/>}</Card>{Array.isArray(data.recent_achievements) && rows(data.recent_achievements).map((award, i) => <Card key={i}><Achievement data={award}/></Card>)}</>
}
function DashboardActions({ passport }: { passport: RecordData | null }) {
  const [message, setMessage] = useState(''), [downloading, setDownloading] = useState(false)
  const state = passport ? passportPresentation(passport, true) : null
  const versionId = text(state?.version?.id), reference = text(passport?.public_reference)
  const prefix = uuidPattern.test(versionId) ? `student/passport/versions/${versionId}/` : 'student/passport/'
  const status = useQuery({ queryKey: ['live', `${prefix}pdf/status/`], queryFn: ({ signal }) => getProduct(`${prefix}pdf/status/`, signal), enabled: !!state?.canPrepare, retry: false })
  const link = state?.currentValid && uuidPattern.test(reference) ? window.location.origin + '/verify/qr?reference=' + encodeURIComponent('passport:' + reference) : ''
  async function download() { if (status.data?.available_for_download !== true || !state?.canPrepare || downloading) return; setDownloading(true); setMessage(''); try { await downloadPassport(prefix) } catch (error) { setMessage(productError(error)) } finally { setDownloading(false) } }
  async function share() { if (!link) return; try { if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable'); await navigator.clipboard.writeText(link); setMessage('Link copied.') } catch { setMessage('Select and copy the verification link below.') } }
  return <><div className="dashboard-passport-actions"><button className="button" disabled={!state?.canPrepare || status.isFetching || status.isError || status.data?.available_for_download !== true || downloading} onClick={() => void download()}>Download PDF</button><button className="button" disabled={!link} onClick={() => void share()}>Share Passport</button><Link className="button" to="/student/passport#passport-history">View History</Link></div>{message && <p role="status">{message}</p>}{message && link && <label className="dashboard-share-link">Public verification link<input readOnly value={link} onFocus={event => event.target.select()}/></label>}</>
}
function PdfActions({ prefix, canGenerate = true }: { prefix: string; canGenerate?: boolean }) {
  const client = useQueryClient(), [pending, setPending] = useState(false), [error, setError] = useState<unknown>(null)
  const status = useQuery({ queryKey: ['live', `${prefix}pdf/status/`], queryFn: ({ signal }) => getProduct(`${prefix}pdf/status/`, signal), retry: false,
    refetchInterval: query => ['PENDING', 'GENERATING'].includes(text(query.state.data?.status)) ? 3000 : false })
  async function run(generate: boolean) {
    if (pending || (generate && !canGenerate)) return
    setPending(true); setError(null)
    try { if (generate) { await api.post(`${prefix}pdf/`, {}); await client.invalidateQueries({ queryKey: ['live', `${prefix}pdf/status/`] }) } else await downloadPassport(prefix) }
    catch (cause) { setError(cause); await status.refetch() } finally { setPending(false) }
  }
  if (status.isPending) return <Loading/>
  if (status.isError) return <ErrorNotice error={status.error} retry={() => void status.refetch()}/>
  return <section><h3>Passport PDF</h3><p role="status">{text(status.data.status)}</p>{error ? <p role="alert">{productError(error)}</p> : null}<div className="live-actions">{canGenerate && <button className="button primary" disabled={!canGenerate || pending || ['PENDING', 'GENERATING'].includes(text(status.data.status))} onClick={() => void run(true)}>{pending ? 'Please wait…' : 'Prepare PDF'}</button>}<button className="button" disabled={pending || status.data.available_for_download !== true} onClick={() => void run(false)}>Download PDF</button><button className="button" disabled={pending} onClick={() => void status.refetch()}>Refresh status</button></div></section>
}
function Passport({ data, prefix, current = true, holder }: { data: RecordData; prefix: string; current?: boolean; holder?: RecordData }) {
  const [message, setMessage] = useState('')
  if (data.passport === null || data.status === 'NOT_ISSUED') return <Card><h2>No passport issued yet</h2><p>Your passport will appear after the university recognizes your achievements and issues a credential.</p></Card>
  const state = passportPresentation(data, current), reference = text(data.public_reference)
  const proof = blockchainAvailability(data.blockchain)
  const pdfPrefix = prefix === 'student/passport/' && uuidPattern.test(text(state.version?.id)) ? 'student/passport/versions/' + text(state.version?.id) + '/' : prefix
  const link = state.currentValid && uuidPattern.test(reference) ? window.location.origin + '/verify/qr?reference=' + encodeURIComponent('passport:' + reference) : ''
  async function copyLink() {
    try { if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable'); await navigator.clipboard.writeText(link); setMessage('Link copied.') }
    catch { setMessage('Select and copy the link above.') }
  }
  return <Card><h2>{state.title}</h2><PassportCard data={backendPassportCard(data, state.retired ? undefined : holder)}/><Fields data={data} names={['public_reference', 'lifecycle_status', 'first_issued_at', 'updated_at']}/>
    {!state.currentValid && <p role="status">{state.retired ? 'This passport is not active. Use the current passport supplied by the university.' : text(data.status) === 'PENDING_BLOCKCHAIN' ? 'Blockchain confirmation pending.' : 'Current validity has not been confirmed. Refresh the record before sharing.'}</p>}
    {state.version && <><Fields data={state.version} names={['version_number', 'status', 'issued_at']}/>{Array.isArray(state.version.skills) && rows(state.version.skills).map((skill, i) => <Fields key={i} data={skill} names={['skill_name', 'category', 'stamp_type']}/>)}</>}
    {link && <><label htmlFor="passport-share">Public verification link</label><input id="passport-share" readOnly value={link}/><div className="live-actions"><Link className="button" to={link.replace(window.location.origin, '')}>Verify Passport</Link><button className="button" onClick={() => void copyLink()}>Copy link</button></div><p role="status">{message}</p></>}
    {state.canPrepare && <PdfActions prefix={pdfPrefix}/>}
    <p role="status">{state.currentValid && proof === 'verified' ? 'Blockchain Verified' : proof === 'not_configured' ? 'Blockchain verification is not configured.' : proof === 'pending' ? 'Blockchain confirmation pending.' : proof === 'failed' ? 'Blockchain proof processing failed.' : proof === 'unverifiable' ? 'Blockchain proof is unverifiable.' : 'Blockchain proof unavailable or awaiting contract confirmation.'}</p><p className="muted">PDF issuance and registry validity alone do not establish blockchain authenticity.</p>
  </Card>
}
function HistoricalVersion({ data }: { data: RecordData }) {
  const id = text(data.id), reference = text(data.public_reference)
  return <><h3>Historical version {text(data.version_number)}</h3><p>This record is not selected as the current passport.</p><Fields data={data} names={['public_reference', 'status', 'issued_at']}/>
    {uuidPattern.test(reference) && <Link className="button" to={'/verify/qr?reference=' + encodeURIComponent('passport-version:' + reference)}>Verify historical version</Link>}
    {uuidPattern.test(id) && data.status === 'ISSUED' && <PdfActions prefix={'student/passport/versions/' + id + '/'} canGenerate={false}/>}
  </>
}
function StudentContent({ section }: { section: string }) {
  if (section === 'dashboard' || section === 'profile') return <Resource path="student/dashboard/">{data => section === 'profile' ? <Card><Profile data={object(data.profile)}/></Card> : <Dashboard data={data} student/>}</Resource>
  if (section === 'passport') return <><Resource path="student/dashboard/">{dashboard => <Resource path="student/passport/">{data => <Passport data={data} prefix="student/passport/" holder={object(dashboard.profile)}/>}</Resource>}</Resource><Collection path="student/passport/versions/" title="Passport version history" render={row => <HistoricalVersion data={row}/>}/></>
  if (section === 'skills') return <><Collection path="student/skills/" title="Recognized AI skills"/><Collection path="student/achievements/" title="Verified achievements" render={row => <Achievement data={row}/>}/></>
  if (section === 'credentials') return <Collection path="student/credentials/" title="Credentials" render={row => <Credential data={row}/>}/>
  return <Card><p>This feature is not available in the live workspace.</p><Link to="/student/passport">View my passport</Link></Card>
}
function Revoke({ id }: { id: string }) {
  const [reason, setReason] = useState(''), [pending, setPending] = useState(false), [error, setError] = useState<unknown>(null), client = useQueryClient()
  async function submit(event: FormEvent) { event.preventDefault(); if (pending || !reason.trim()) return; setPending(true); setError(null)
    try { const response = await api.post(`admin/credentials/${id}/revoke/`, { reason: reason.trim() }); const record = object(response.data); if (record.id !== id || record.validity_status !== 'REVOKED') throw new Error('REVOCATION_CONTRACT_ERROR'); setReason(''); await client.invalidateQueries({ queryKey: ['live'] }) } catch (cause) { setError(cause) } finally { setPending(false) } }
  return <form onSubmit={e => void submit(e)}><label htmlFor={`revoke-reason-${id}`}>Revocation reason</label><textarea id={`revoke-reason-${id}`} required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} disabled={pending}/><button className="button" disabled={pending || !reason.trim()}>Revoke credential</button>{error ? <p role="alert">{productError(error)}</p> : null}</form>
}
function Issue({ studentId }: { studentId: string }) {
  const [selected, setSelected] = useState<string[]>([]), [key, setKey] = useState(() => crypto.randomUUID()), [pending, setPending] = useState(false), [message, setMessage] = useState(''), client = useQueryClient()
  async function issue() { if (pending || !selected.length) return; setPending(true); setMessage('')
    try { const response = await api.post('admin/credentials/issue/', { achievement_ids: selected, idempotency_key: key }); const record = object(response.data); if (!uuidPattern.test(text(record.id)) || !['VALID', 'EXPIRED', 'REVOKED', 'INVALID'].includes(text(record.validity_status))) throw new Error('ISSUANCE_CONTRACT_ERROR'); setMessage('Credential issued. Passport updates are handled by the university service.'); setSelected([]); setKey(crypto.randomUUID()); await client.invalidateQueries({ queryKey: ['live'] }) } catch (cause) { setMessage(productError(cause)) } finally { setPending(false) } }
  return <><Collection path={`admin/students/${studentId}/achievements/`} title="Achievements eligible for credential issuance" render={row => <><Achievement data={row}/><label><input type="checkbox" disabled={pending} checked={selected.includes(text(row.id))} onChange={e => { setSelected(current => e.target.checked ? [...current, text(row.id)] : current.filter(id => id !== text(row.id))); setKey(crypto.randomUUID()) }}/>Include achievement</label></>}/><button className="button primary" disabled={pending || !selected.length} onClick={() => void issue()}>Issue credential for {selected.length} achievements</button><p role="status">{message}</p></>
}
function Imports({ sync, canRun }: { sync: boolean; canRun: boolean }) {
  const [pending, setPending] = useState(false), [result, setResult] = useState<RecordData | null>(null), [error, setError] = useState<unknown>(null)
  async function previewSync() {
    if (pending || !canRun) return
    setPending(true); setError(null); setResult(null)
    try { const data = parseProduct((await api.post('integrations/classroom/sync/', { dry_run: true })).data); if (data.source !== 'SIMULATED_BTU_CLASSROOM' || data.status !== 'preview') throw new Error('SYNC_CONTRACT_ERROR'); setResult(data) }
    catch (cause) { setError(cause) } finally { setPending(false) }
  }
  return <><Card>{sync ? <><h2>Classroom synchronization</h2><p>Simulated BTU Classroom adapter. This preview does not connect to an institutional Classroom API.</p><button className="button" disabled={pending || !canRun} onClick={() => void previewSync()}>Preview Classroom synchronization</button>{error ? <p role="alert">{productError(error)}</p> : null}{result && <Fields data={result} names={['source', 'status', 'eligible_count', 'issued', 'failed', 'skipped']}/>}</> : canRun ? <SpreadsheetImports/> : <p>Import permission required.</p>}</Card><History path={sync ? 'integrations/classroom/events/' : 'integrations/imports/'} title={sync ? 'Synchronization history' : 'Import history'}/></>
}
function History({ path, title }: { path: string; title: string }) {
  const [cursor, setCursor] = useState(''), [previous, setPrevious] = useState<string[]>([])
  const query = useQuery({ queryKey: ['live', path, cursor], queryFn: ({ signal }) => getProduct(`${path}${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`, signal), retry: false })
  let next = ''
  if (typeof query.data?.next === 'string') { try { next = new URL(query.data.next, 'https://pagination.invalid').searchParams.get('cursor') ?? '' } catch { /* Never follow arbitrary URLs. */ } }
  return <section><h2>{title}</h2>{query.isPending ? <Loading/> : query.isError ? <ErrorNotice error={query.error} retry={() => void query.refetch()}/> : <>{rows(query.data.results).length === 0 && <p>No records available.</p>}{rows(query.data.results).map((row, i) => <Card key={i}><Fields data={row} names={['id', 'source', 'state', 'attempts', 'error_code']}/>{row.summary && typeof row.summary === 'object' ? <Fields data={object(row.summary)} names={['issued', 'awarded', 'failed', 'skipped', 'processed', 'imported', 'duplicates']}/> : null}</Card>)}<div className="live-actions"><button className="button" disabled={!previous.length} onClick={() => { setCursor(previous.at(-1) ?? ''); setPrevious(current => current.slice(0, -1)) }}>Previous</button><button className="button" disabled={!next} onClick={() => { setPrevious(current => [...current, cursor]); setCursor(next) }}>Next</button></div></>}</section>
}
export function ProductWorkspace({ role }: { role: 'student' | 'administrator' }) {
  const location = useLocation(), params = useParams(), session = useSession(), client = useQueryClient()
  const capabilities = session.data?.status === 'authenticated' ? session.data.user.capabilities ?? [] : []
  const admin = role === 'administrator', base = admin ? '/admin' : '/student', section = location.pathname.split('/')[2] || 'dashboard'
  const allNavigation = admin ? [['dashboard', 'Overview'], ['students', 'Students'], ['credentials', 'Credentials'], ['classroom-sync', 'Classroom'], ['imports', 'Imports']] : [['dashboard', 'My Passport'], ['profile', 'My profile'], ['skills', 'Skills & achievements'], ['credentials', 'Credentials'], ['passport', 'Passport details']]
  const navigation = allNavigation.filter(([path]) => !admin || capabilities.includes(path === 'classroom-sync' ? 'sync_classroom' : path === 'imports' ? 'import_completions' : 'view_student_records'))
  const required = section === 'classroom-sync' ? 'sync_classroom' : section === 'imports' ? 'import_completions' : 'view_student_records'
  let content: ReactNode
  if (!admin) content = <StudentContent section={section}/>
  else if (!capabilities.includes(required)) content = <Card><p role="alert">Your account does not have permission to open this page.</p></Card>
  else if (params.id && !uuidPattern.test(params.id)) content = <Card><p role="alert">Invalid student reference.</p></Card>
  else if (section === 'dashboard') content = <Resource path="admin/statistics/">{data => <Dashboard data={data}/>}</Resource>
  else if (section === 'students' && params.id) content = <><Resource path={`admin/students/${params.id}/`}>{data => <><Dashboard data={data}/>{data.passport ? <Passport data={object(data.passport)} prefix={`admin/passports/${text(object(data.passport).id)}/`} holder={object(data.profile)}/> : <p>No current passport.</p>}</>}</Resource><Collection path={`admin/passports/?student_id=${params.id}`} title="Student passports" render={row => <Passport data={row} prefix={`admin/passports/${text(row.id)}/`} current={false}/>}/>{capabilities.includes('manage_credentials') && <Issue studentId={params.id}/>}</>
  else if (section === 'students') content = <Collection path="admin/students/" title="Student records" render={row => <><Profile data={row}/><Link className="button" to={`/admin/students/${encodeURIComponent(text(row.id))}`}>View record and passport</Link></>}/>
  else if (section === 'credentials') content = <Collection path="admin/credentials/" title="Credentials" render={row => <><Credential data={row}/>{capabilities.includes('revoke_credentials') && row.validity_status !== 'REVOKED' && <Revoke id={text(row.id)}/>}</>}/>
  else if (section === 'imports' || section === 'classroom-sync') content = <Imports sync={section === 'classroom-sync'} canRun={capabilities.includes(section === 'classroom-sync' ? 'sync_classroom' : 'import_completions')}/>
  else content = <Card><p>This page is unavailable in the live workspace.</p><Link to="/admin/dashboard">Return to overview</Link></Card>
  return <div className={`app live-product${!admin && section === 'dashboard' ? ' student-dashboard-layout' : ''}`}><aside className="sidebar"><Link className="brand" to={`${base}/dashboard`}><OfficialBtuLogo/><span>AI SKILLS<br/><strong>DIGITAL PASSPORT</strong></span></Link><nav aria-label="Workspace">{navigation.map(([path, label]) => <NavLink key={path} to={`${base}/${path}`}>{label}</NavLink>)}<Link to="/verify">Verify Passport</Link></nav></aside><div className="main-shell"><header><strong>{admin ? 'Administrator workspace' : 'Student workspace'}</strong>{!admin && section === 'dashboard' && <button className="button" onClick={() => void client.invalidateQueries({ queryKey: ['live'] })}>Refresh records</button>}<LogoutButton role={role}/></header><main>{(admin || section !== 'dashboard') && <button className="button" onClick={() => void client.invalidateQueries({ queryKey: ['live'] })}>Refresh records</button>}<h1>{navigation.find(([path]) => path === section)?.[1] ?? 'Workspace'}</h1><div key={location.pathname + JSON.stringify(session.data)}>{content}</div></main></div></div>
}
