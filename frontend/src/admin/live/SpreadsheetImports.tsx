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
  return owner ? <><ReviewedImports key={owner}/><AutomaticSources key={`${owner}:automatic`}/></> : null
}

function AutomaticHistory({id}:{id:string}) {
  const [page,setPage]=useState(1), q=useAdminQuery(['automatic-source-history',id,page],signal=>api.getAutomaticHistory(id,page,signal))
  return <section aria-label="Automatic source history"><h3>Automatic source history</h3><button className="button" onClick={()=>void q.refetch()}>Refresh automatic history</button><Result query={q}>{data=><>{data.results.length?<ul className="student-records">{data.results.map(row=><li key={row.id}><h4>{row.state} · {row.started_at}</h4>{row.error_code&&<p>Error classification: {row.error_code}</p>}<Facts values={row.counts}/></li>)}</ul>:<p>No automatic polling attempts recorded.</p>}<Pagination page={page} data={data} change={setPage}/></>}</Result></section>
}

function AutomaticSources() {
  const client=useQueryClient(), [page,setPage]=useState(1), [id,setId]=useState(''), [seconds,setSeconds]=useState('300'), [reference,setReference]=useState(''), [confirmed,setConfirmed]=useState(false), [busy,setBusy]=useState(false), [message,setMessage]=useState(''), [showHistory,setShowHistory]=useState(false)
  const [until,setUntil]=useState(0), [now,setNow]=useState(Date.now), inFlight=useRef(false), controller=useRef<AbortController|null>(null)
  const q=useAdminQuery(['automatic-sources',page],signal=>api.getAutomaticSources(page,signal)), selected=q.data?.results.find(row=>row.profile_id===id), interval=Number(seconds), waiting=now<until
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>{clearInterval(timer);controller.current?.abort()}},[])
  function reset(){setId('');setReference('');setConfirmed(false);setMessage('');setShowHistory(false)}
  async function configure(enabled:boolean){
    if(!selected||inFlight.current||waiting||enabled&&(!confirmed||!selected.profile_enabled||!Number.isSafeInteger(interval)||interval<60||interval>86400||!reference.trim()||reference.length>255))return
    const c=new AbortController();controller.current=c;inFlight.current=true;setBusy(true);setMessage('')
    try{const value=await api.configureAutomaticSource(id,enabled,interval,reference,c.signal);if(c.signal.aborted)return;if(value.profile_id!==id||value.enabled!==enabled)throw new AdminError();setConfirmed(false);setReference('');setMessage(enabled?'Automatic polling enabled for this approved source.':'Automatic polling disabled for this source.');void client.invalidateQueries({queryKey:['admin-live']})}
    catch(e){if(c.signal.aborted)return;setMessage(e instanceof AdminError?e.message:'The setting could not be read. Refresh source status before retrying.');if(e instanceof AdminError){setUntil(Date.now()+Math.max(e.retryAfter,e.status===409?2:0)*1000);if([401,403].includes(e.status))void client.invalidateQueries({queryKey:['session']})}}
    finally{inFlight.current=false;if(!c.signal.aborted)setBusy(false)}
  }
  return <Card><h2>Automatic confirmed-skill synchronization</h2><p>Automatic processing is off until an authorized administrator enables an independently approved Google awarded-skill source. Only CONFIRMED records that pass the existing validation can issue awards. Manual reviewed imports remain available.</p><p>Polling requires the university synchronization service to be running. University source approval and processing authority remain separate prerequisites.</p>
    <Result query={q}>{data=><><label htmlFor="automatic-source">Automatic source profile</label><select id="automatic-source" value={id} disabled={busy} onChange={e=>{reset();setId(e.target.value);const row=data.results.find(p=>p.profile_id===e.target.value);setSeconds(String(row?.interval_seconds??300))}}><option value="">Select an approved source</option>{data.results.map(row=><option key={row.profile_id} value={row.profile_id}>{row.profile_key} · version {row.profile_version}{row.profile_enabled?'':' · profile disabled'}</option>)}</select>{!data.results.length&&<p>No approved Google awarded-skill profiles are available.</p>}<Pagination page={page} data={data} change={n=>{if(!busy){reset();setPage(n)}}}/><button className="button" disabled={busy} onClick={()=>{reset();void q.refetch()}}>Refresh automatic sources</button>
    {selected&&<section aria-label="Selected automatic source"><h3>{selected.profile_key} · {selected.enabled?'Enabled':'Disabled'}</h3><p role="status">{selected.state}{selected.error_code?` · ${selected.error_code}`:''}</p>{selected.last_checked_at&&<p>Last checked: {selected.last_checked_at}</p>}{selected.next_poll_at&&<p>Next eligible poll: {selected.next_poll_at}</p>}<label htmlFor="automatic-interval">Polling interval (seconds, 60–86400)</label><input id="automatic-interval" type="number" min="60" max="86400" step="1" value={seconds} disabled={busy} onChange={e=>{setSeconds(e.target.value);setConfirmed(false)}}/><label htmlFor="automatic-authorization">Continuing source authorization reference</label><input id="automatic-authorization" maxLength={255} value={reference} disabled={busy} onChange={e=>{setReference(e.target.value);setConfirmed(false)}}/><label><input type="checkbox" checked={confirmed} disabled={busy||!selected.profile_enabled} onChange={e=>setConfirmed(e.target.checked)}/>I authorize periodic processing of this approved source under its existing institutional policy.</label><button className="button primary" disabled={busy||waiting||!selected.profile_enabled||!confirmed||!reference.trim()||!Number.isSafeInteger(interval)||interval<60||interval>86400} onClick={()=>void configure(true)}>Enable automatic source</button><button className="button" disabled={busy||waiting||!selected.enabled} onClick={()=>void configure(false)}>Disable automatic source</button><button className="button" disabled={busy} onClick={()=>setShowHistory(!showHistory)}>{showHistory?'Hide automatic history':'Inspect automatic history'}</button>{showHistory&&<AutomaticHistory key={id} id={id}/>}</section>}</>}</Result>{busy&&<p role="status">Saving source authorization…</p>}{message&&<p role="status">{message}</p>}{waiting&&<p role="status">Retry in {Math.max(0,Math.ceil((until-now)/1000))} seconds.</p>}</Card>
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
