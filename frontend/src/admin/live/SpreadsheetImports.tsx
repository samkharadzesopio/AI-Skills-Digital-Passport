import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSession } from '../../auth/hooks'
import { Card } from '../../components/ui'
import { AdminError } from './service'
import { Facts, Pagination, Result, useAdminQuery } from './common'
import * as api from './spreadsheet-service'
import type { ImportPreview, ImportProfile } from './spreadsheet-contracts'

// Keep private files/previews in memory and remount on an authenticated account change.
export function SpreadsheetImports() {
  const session = useSession(), owner = session.data?.status === 'authenticated' ? session.data.user.email : ''
  return owner ? <ReviewedImports key={owner}/> : null
}
function ReviewedImports() {
  const client = useQueryClient(), [page, setPage] = useState(1), [source, setSource] = useState<ImportProfile['source']>('BTU_EXCEL'), [profileId, setProfileId] = useState(''), [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null), [confirmed, setConfirmed] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [until, setUntil] = useState(0), [now, setNow] = useState(Date.now)
  const controller = useRef<AbortController | null>(null), inFlight = useRef(false), input = useRef<HTMLInputElement>(null)
  const profiles = useAdminQuery(['import-profiles', page], signal => api.getProfiles(page, signal)), selected = profiles.data?.results.find(p => p.id === profileId && p.source === source)
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => { clearInterval(timer); controller.current?.abort() } }, [])
  function reset(clearFile = false) { setPreview(null); setConfirmed(false); setError(''); if (clearFile) { setFile(null); if (input.current) input.current.value = '' } }
  async function run(action: 'preview' | 'confirm' | 'refresh') {
    if (inFlight.current || Date.now() < until || (action === 'preview' && !selected) || (action !== 'preview' && !preview) || (action === 'confirm' && !confirmed)) return
    const saved = preview, c = new AbortController(); controller.current = c; inFlight.current = true; setBusy(true); setError(''); setConfirmed(false)
    if (action === 'preview') setPreview(null)
    try {
      const next = action === 'preview' ? await api.previewImport(selected!, file, c.signal) : action === 'confirm' ? await api.confirmPreview(saved!, c.signal) : await api.refreshPreview(saved!.id, c.signal)
      if (c.signal.aborted) return
      if (action !== 'preview' && (next.id !== saved?.id || next.snapshot_sha256 !== saved.snapshot_sha256) || action === 'preview' && next.report.profile_id !== selected?.id) throw new AdminError()
      setPreview(next)
      if (action !== 'preview') void client.invalidateQueries({ predicate: q => q.queryKey[0] === 'admin-live' || q.queryKey[0] === 'student' })
    } catch (e) { if (c.signal.aborted) return; setError(e instanceof AdminError ? e.message : 'The import response could not be read. Refresh the outcome and inspect history before retrying.'); if (e instanceof AdminError) { setUntil(Date.now() + Math.max(e.retryAfter, e.status === 409 ? 2 : 0) * 1000); if ([401,403].includes(e.status)) void client.invalidateQueries({ queryKey: ['session'] }) } }
    finally { inFlight.current = false; if (!c.signal.aborted) setBusy(false) }
  }
  const canPreview = !!selected && (source === 'BTU_GOOGLE_SHEETS' || !!file && file.name.toLowerCase().endsWith('.xlsx') && file.size > 0 && file.size <= 5 * 1024 * 1024), canConfirm = !!preview && ['READY','FAILED'].includes(preview.state) && Date.parse(preview.expires_at) > now && preview.report.valid_records > 0, waiting = now < until
  return <Card><h2>Import approved learning evidence</h2><p>Select an institutionally approved mapping, preview the source, then confirm its eligible records. Only explicit CONFIRMED source decisions can issue skill awards. Preview does not issue credentials.</p>
    <Result query={profiles}>{data => <><label htmlFor="import-source">Approved source</label><select id="import-source" value={source} disabled={busy} onChange={e => { setSource(e.target.value as ImportProfile['source']); setProfileId(''); reset(true) }}><option value="BTU_EXCEL">Approved Excel workbook</option><option value="BTU_GOOGLE_SHEETS">Server-configured Google Sheets</option></select>
      <label htmlFor="import-profile">Authorized import profile</label><select id="import-profile" value={profileId} disabled={busy} onChange={e => { setProfileId(e.target.value); reset(true) }}><option value="">Select a profile</option>{data.results.filter(p => p.source === source).map(p => <option key={p.id} value={p.id}>{p.key} · version {p.version} · {p.kind}</option>)}</select>
      {!data.results.some(p => p.source === source) && <p role="status">No enabled profiles for this source on this page. Institutional source approval and a configured profile are required.</p>}
      <Pagination page={page} data={data} change={n => { if (!busy) { setPage(n); setProfileId(''); reset(true) } }}/>
      <button className="button" disabled={busy} onClick={() => { setProfileId(''); reset(true); void profiles.refetch() }}>Refresh approved profiles</button>
      {source === 'BTU_EXCEL' ? <><label htmlFor="reviewed-workbook">Approved workbook (.xlsx, up to 5 MiB)</label><input ref={input} id="reviewed-workbook" type="file" accept=".xlsx" disabled={busy} onChange={e => { setFile(e.target.files?.[0] ?? null); reset() }}/>{file && !canPreview && <p role="alert">Select a nonempty .xlsx file up to 5 MiB and an authorized profile.</p>}</> : <p>Only the approved server-configured sheet is read. Google credentials and source configuration are required; no personal account or arbitrary URL is used.</p>}
      <button className="button" disabled={busy || waiting || !canPreview} onClick={() => void run('preview')}>Preview incoming records</button></>}</Result>
    {busy && <p role="status">Processing request…</p>}{error && <p role="alert">{error} No successful import is assumed. Check the preview outcome and persisted history.</p>}{waiting && <p role="status">Retry in {Math.max(0, Math.ceil((until - now) / 1000))} seconds.</p>}
    {preview && <section aria-label="Reviewed spreadsheet snapshot"><h3>Review import preview</h3><p role="status">{preview.state} · expires {preview.expires_at}</p><p>Profile {preview.report.profile_key} · version {preview.report.profile_version} · {preview.report.kind}</p>
      <h4>Detected column mapping</h4><p>Header row {preview.report.header_row}. The server applies the approved aliases; column numbers refer to the original workbook.</p><Facts values={preview.report.columns}/>
      <Facts values={{ total: preview.report.total_rows, eligible: preview.report.valid_records, duplicates: preview.report.duplicate_records, invalid: preview.report.invalid_records, institutional_review: preview.report.review_records }}/>
      <details open><summary>Row validation details</summary><ul>{preview.report.rows.map(row => <li key={row.row}>Row {row.row}: {row.status} · {row.code} · {row.message}</li>)}</ul></details>
      <p>Snapshot SHA-256: <code style={{ overflowWrap: 'anywhere' }}>{preview.snapshot_sha256}</code></p>
      {Date.parse(preview.expires_at) <= now && preview.state !== 'COMPLETED' && <p role="alert">This preview expired. Create and review a new preview.</p>}
      <label><input type="checkbox" checked={confirmed} disabled={busy || !canConfirm} onChange={e => setConfirmed(e.target.checked)}/>I reviewed this snapshot and confirm importing its eligible records.</label>
      <button className="button primary" disabled={busy || waiting || !canConfirm || !confirmed} onClick={() => void run('confirm')}>Confirm reviewed import</button><button className="button" disabled={busy || waiting} onClick={() => void run('refresh')}>Refresh preview outcome</button>
      <p>Confirmation submits this exact snapshot digest. An interrupted request can still persist rows; refresh the outcome before explicitly retrying. Credential issuance and blockchain confirmation are separate steps.</p>
      {preview.result && <section role="status"><h3>Persisted import result</h3><p>Import {preview.result.import_id}</p><Facts values={preview.result.counts}/><ul>{preview.result.errors.map((row, i) => <li key={i}>Row {row.row}: {row.code}</li>)}</ul><p>Inspect persisted import history and Student records below. Excluded invalid and unconfirmed rows were not imported.</p></section>}
    </section>}
  </Card>
}
