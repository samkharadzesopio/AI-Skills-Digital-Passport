import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Card } from '../../components/ui'
import { IssuedPassportPreview } from '../../components/PassportPreview'
import { adaptPassport } from '../../student/adapter'
import type { Passport, Version } from '../../student/contracts'
import * as api from './service'
import { Action, Empty, Pagination, Result, useAdminQuery, useCapabilities } from './common'

function PDF({ passportId, versionId }: { passportId: string; versionId: string }) {
  const query = useAdminQuery(['pdf', passportId, versionId], s => api.pdfStatus(passportId, versionId, s)), grants = useCapabilities(), urls = useRef(new Set<string>())
  const { refetch, dataUpdatedAt } = query, pending = query.data?.status === 'PENDING' || query.data?.status === 'GENERATING'
  useEffect(() => { if (!pending || query.isError) return; const t = setTimeout(() => void refetch(), 2000); return () => clearTimeout(t) }, [pending, query.isError, dataUpdatedAt, refetch])
  useEffect(() => () => { for (const url of urls.current) URL.revokeObjectURL(url); urls.current.clear() }, [])
  async function download(signal: AbortSignal) { const { blob, filename } = await api.downloadPDF(passportId, versionId, signal); if (signal.aborted) return; const url = URL.createObjectURL(blob); urls.current.add(url); const a = document.createElement('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => { URL.revokeObjectURL(url); urls.current.delete(url) }, 1000) }
  return <section aria-label="Admin Passport PDF"><h2>Registered Passport PDF</h2><p>Uses the original BTU template and the selected issued snapshot.</p><Result query={query}>{status => <><p role="status">PDF status: {status.status}</p>{pending && <p>Generation in progress. Checking status automatically.</p>}{status.available_for_download ? <Action label="Download registered PDF" confirm={false} perform={download}/> : grants.includes('manage_credentials') ? <Action label={status.status === 'FAILED' ? 'Retry PDF generation' : 'Generate Passport PDF'} disabled={pending} perform={s => api.generatePDF(passportId, versionId, s)}><p>Generate the PDF for this exact issued version.</p></Action> : <p>Generating a PDF requires manage_credentials. You may download existing issued documents.</p>}</>}</Result></section>
}
function Versions({ passport }: { passport: Passport }) {
  const [page, setPage] = useState(1), [selected, setSelected] = useState<Version | null>(null), q = useAdminQuery(['versions', passport.id, page], s => api.getVersions(passport.id, page, s)), version = selected ?? passport.latest_version
  return <><Card><h2>Issued Passport versions</h2><p>Current issuance state: {passport.status}. Historical snapshots remain immutable; they do not establish current credential validity.</p><button className="button" onClick={() => setSelected(null)}>Current issued version</button><Result query={q}>{data => <>{data.results.length ? <ul className="student-records">{data.results.map(v => <li key={v.id}><button className="button" onClick={() => setSelected(v)}>Inspect version {v.version_number}</button><p>{v.status} · {v.issued_at} · Public reference {v.public_reference}</p></li>)}</ul> : <Empty label="issued versions"/>}<Pagination page={page} data={data} change={setPage}/></>}</Result></Card>{version ? <Card><IssuedPassportPreview passport={adaptPassport(passport, version)}/><PDF key={version.id} passportId={passport.id} versionId={version.id}/></Card> : <Card>No issued snapshot yet.</Card>}</>
}
export function PassportPage() {
  const { id = '' } = useParams(), [params, setParams] = useSearchParams(), [page, setPage] = useState(1), q = useAdminQuery(['passports', id, page], s => api.getPassports(page, id, s)), chosen = params.get('passport')
  return <><h1>Student Passports</h1>{id && <Link to={`/admin/students/${id}`}>Student record</Link>}<Result query={q}>{data => { const rows = data.results.filter((p): p is Passport => p !== null), p = rows.find(p => p.id === chosen) ?? (id ? rows[0] : null); return <>{!rows.length ? <Card><Empty label="Passports"/></Card> : <Card><ul className="student-records">{rows.map(p => <li key={p.id}><button className="button" onClick={() => setParams({ passport: p.id })}>Open Passport {p.public_reference}</button><Link to={`/admin/students/${p.student_id}`}>Student record</Link></li>)}</ul><Pagination page={page} data={data} change={n => { setPage(n); setParams({}) }}/></Card>}{p && <Versions key={p.id} passport={p}/>}</> }}</Result></>
}
