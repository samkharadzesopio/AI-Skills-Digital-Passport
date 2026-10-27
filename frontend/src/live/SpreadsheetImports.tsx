import { parsePreview } from './spreadsheet-contracts'
import { useCountdown } from '../auth/hooks'
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { api } from '../services/api'
import { getList, object, rows, text, productError } from '../services/product'
import type { RecordData } from '../services/product'
import { uuidPattern } from './passport'

/** Inspected profile workflow; missing backend support never falls back to immediate issuance. */
export function SpreadsheetImports() {
  const client = useQueryClient(), [page, setPage] = useState(1), [source, setSource] = useState('BTU_EXCEL')
  const [profileId, setProfileId] = useState(''), [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<RecordData | null>(null), [confirmed, setConfirmed] = useState(false)
  const [pending, setPending] = useState(false), [error, setError] = useState<unknown>(null)
  const profiles = useQuery({ queryKey: ['live', 'import-profiles', page], queryFn: ({ signal }) => getList(`integrations/import/profiles/?page=${page}`, page, signal), retry: false })
  const selected = profiles.data?.results.find(p => p.id === profileId && p.source === source)
  const reset = () => { setPreview(null); setConfirmed(false); setError(null) }
  async function run(action: 'preview' | 'confirm' | 'refresh') {
    if (pending) return
    setPending(true); setError(null)
    try {
      let response
      if (action === 'preview') {
        if (!selected || !uuidPattern.test(profileId)) return
        setPreview(null); setConfirmed(false)
        if (source === 'BTU_EXCEL') {
          if (!file || !file.name.toLowerCase().endsWith('.xlsx') || !file.size || file.size > 5 * 1024 * 1024) return
          const body = new FormData(); body.append('profile_id', profileId); body.append('file', file)
          response = await api.post('integrations/import/excel/preview/', body)
        } else response = await api.post('integrations/import/google-sheets/preview/', { profile_id: profileId })
      } else {
        if (!preview || !uuidPattern.test(text(preview.id))) return
        const path = `integrations/import/previews/${text(preview.id)}/`
        if (action === 'confirm') {
          if (!confirmed || Date.parse(text(preview.expires_at)) <= Date.now() || !['READY', 'FAILED'].includes(text(preview.state)) || Number(object(preview.report).valid_records) < 1) return
          // Exact reviewed snapshot, actor-bound backend idempotency, no automatic retry.
          response = await api.post(`${path}confirm/`, { snapshot_sha256: preview.snapshot_sha256, confirm: true })
        } else response = await api.get(path)
      }
      const next = parsePreview(response.data)
      if (action !== 'preview' && (next.id !== preview?.id || next.snapshot_sha256 !== preview?.snapshot_sha256)) throw new Error('PREVIEW_CHANGED')
      setPreview(next); setConfirmed(false)
      await client.invalidateQueries({ queryKey: ['live'] })
    } catch (cause) { setError(cause); setConfirmed(false) } finally { setPending(false) }
  }
  const secondsRemaining = useCountdown(preview ? Date.parse(text(preview.expires_at)) : 0)
  if (profiles.isPending) return <p role="status">Loading authorized import profiles…</p>
  if (profiles.isError) return <section><h2>Reviewed spreadsheet imports unavailable</h2><p role="alert">{axios.isAxiosError(profiles.error) && profiles.error.response?.status === 404 ? 'This backend does not provide approved profile, preview and confirmation APIs. Import is disabled until that backend workflow is integrated.' : productError(profiles.error)}</p><button className="button" onClick={() => void profiles.refetch()}>Retry profiles</button></section>
  const report = preview ? object(preview.report) : null
  const canConfirm = preview && ['READY', 'FAILED'].includes(text(preview.state)) && secondsRemaining > 0 && Number(report?.valid_records) > 0
  return <section><h2>Import approved learning evidence</h2><p>Preview uses server-authorized sources and profiles. Only eligible, institutionally confirmed records may issue credentials. No arbitrary Google Sheets URL is accepted.</p>
    <label htmlFor="import-source">Approved source</label><select id="import-source" value={source} disabled={pending} onChange={e => { setSource(e.target.value); setProfileId(''); reset() }}><option value="BTU_EXCEL">Approved Excel workbook</option><option value="BTU_GOOGLE_SHEETS">Server-configured Google Sheets</option></select>
    <label htmlFor="import-profile">Authorized import profile</label><select id="import-profile" value={profileId} disabled={pending} onChange={e => { setProfileId(e.target.value); reset() }}><option value="">Select a profile</option>{profiles.data.results.filter(p => p.source === source && uuidPattern.test(text(p.id))).map(p => <option key={text(p.id)} value={text(p.id)}>{text(p.key)} · version {text(p.version)} · {text(p.kind)}</option>)}</select>
    <div className="live-actions"><button className="button" disabled={pending || page === 1} onClick={() => { setPage(page - 1); setProfileId(''); reset() }}>Previous profiles</button><button className="button" disabled={pending || !profiles.data.hasNext} onClick={() => { setPage(page + 1); setProfileId(''); reset() }}>Next profiles</button></div>
    {source === 'BTU_EXCEL' && <><label htmlFor="completion-file">Completion workbook (.xlsx, up to 5 MB)</label><input id="completion-file" type="file" accept=".xlsx" disabled={pending} onChange={e => { setFile(e.target.files?.[0] ?? null); reset() }}/></>}
    <button className="button" disabled={pending || !selected || (source === 'BTU_EXCEL' && (!file || !file.name.toLowerCase().endsWith('.xlsx') || !file.size || file.size > 5 * 1024 * 1024))} onClick={() => void run('preview')}>Preview incoming records</button>
    {error ? <p role="alert">{productError(error)} Review or refresh the preview before retrying. No successful import is assumed.</p> : null}
    {preview && report && <><h3>Review import preview</h3><p role="status">{text(preview.state)} · expires {text(preview.expires_at)}</p><p>Eligible: {text(report.valid_records)} · Duplicates skipped: {text(report.duplicate_records)} · Invalid: {text(report.invalid_records)} · Requires institutional review: {text(report.review_records)}</p>
      <ul>{rows(report.rows).map((row, i) => <li key={i}>Row {text(row.row)}: {text(row.status)} · {text(row.code)} · {text(row.message)}</li>)}</ul>
      <label><input type="checkbox" checked={confirmed} disabled={pending || !canConfirm} onChange={e => setConfirmed(e.target.checked)}/>I reviewed this snapshot and confirm importing its eligible records.</label>
      <button className="button primary" disabled={pending || !canConfirm || !confirmed} onClick={() => void run('confirm')}>Confirm reviewed import</button><button className="button" disabled={pending} onClick={() => void run('refresh')}>Refresh preview outcome</button>
      {preview.result != null && <div role="status"><h3>Persisted import result</h3>{Object.entries(object(preview.result)).filter(([key]) => ['processed', 'awarded', 'issued', 'skipped', 'failed', 'import_id'].includes(key)).map(([key, value]) => <p key={key}>{key}: {text(value)}</p>)}<ul>{Array.isArray(object(preview.result).errors) && rows(object(preview.result).errors).map((row, i) => <li key={i}>Row {text(row.row)}: {text(row.code)}</li>)}</ul></div>}
    </>}
  </section>
}
