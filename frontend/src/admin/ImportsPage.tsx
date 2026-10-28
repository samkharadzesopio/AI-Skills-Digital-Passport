import { demoMode } from '../demo/mode'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { FileSpreadsheet, Upload } from 'lucide-react'
import { Card, EmptyState } from '../components/ui'
import { useLocale } from '../i18n'
import { useAdminData } from './store'
import { formatAdminDate, useAdminText } from './i18n'
import type { AdminTextKey } from './i18n'
import { ActionForm, DataTable, PageTitle, Status } from './components'
import type { ImportPreview } from './contracts'
import { isGoogleSheetUrl, validateImportRows } from './importValidation'
import { requestAdminAction } from './services'
export function ImportsPage() {
  const { data } = useAdminData(), t = useAdminText(), { locale } = useLocale()
  const [source, setSource] = useState<'excel' | 'sheets'>('excel'), [file, setFile] = useState<File | null>(null), [url, setUrl] = useState(''), [preview, setPreview] = useState<ImportPreview | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [confirm, setConfirm] = useState(false)
  async function validate(e: FormEvent) {
    e.preventDefault(); setError(''); setPreview(null)
    if (!file || !file.name.toLowerCase().endsWith('.xlsx') || !file.size || file.size > 5 * 1024 * 1024) { setError(t('validFile')); return }
    setBusy(true)
    try { const { readSheet } = await import('read-excel-file/browser'); const rows = await readSheet(file, 1); setPreview(validateImportRows(rows, data)) } catch { setError(t('readFailed')) } finally { setBusy(false) }
  }
  async function sheet(e: FormEvent) {
    e.preventDefault(); setError('')
    if (!isGoogleSheetUrl(url)) { setError(t('sheetInvalid')); return }
    setBusy(true)
    try { await requestAdminAction({ type: 'preview-sheet', sheetUrl: url.trim() }) } catch { setError(t('backendUnavailable')) } finally { setBusy(false) }
  }
  const valid = preview && preview.rows.length > 0 && !preview.errors.length && !preview.rows.some(r => r.errors.length)
  return <><PageTitle title={t('imports')} description={t('importHint')}/><p className="notice">Demo workbook preview uses illustrative student_id/course_id/skill_id rows only. It cannot import or issue official records. Live Mode uses the existing completion-evidence schema and server-approved sources.</p><Card><div className="admin-source-switch" role="group" aria-label={t('source')}><button className={`button ${source === 'excel' ? 'primary' : ''}`} disabled={busy} onClick={() => { setSource('excel'); setError('') }}><FileSpreadsheet size={16}/>{t('excel')}</button><button className={`button ${source === 'sheets' ? 'primary' : ''}`} disabled={busy} onClick={() => { setSource('sheets'); setError('') }}>{t('sheets')}</button></div>{source === 'excel' ? <form onSubmit={validate}><label className="admin-upload" htmlFor="import-file"><Upload size={28}/><strong>{t('chooseFile')}</strong><span>{t('fileHint')}</span><input disabled={busy} id="import-file" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); setError('') }}/></label><button className="button primary" disabled={!file || busy}>{busy ? t('validating') : t('validate')}</button></form> : <form onSubmit={sheet}><label htmlFor="sheet-url">{t('sheetUrl')}</label><input disabled={busy} id="sheet-url" type="url" required placeholder="https://docs.google.com/spreadsheets/d/…" value={url} onChange={e => { setUrl(e.target.value); setError('') }}/><p className="notice">{t('sheetNotice')}</p><button className="button primary" disabled={demoMode || busy || !url.trim()}>{busy ? t('submitting') : t('requestPreview')}</button></form>}{error && <p className="error" role="alert">{error}</p>}</Card>{source === 'excel' && <Card className="admin-spaced"><h2>{t('localPreview')}</h2>{preview ? <>{preview.errors.map(code => <p className="error" role="alert" key={code}>{t(code as AdminTextKey)}</p>)}<DataTable label={t('localPreview')} rows={preview.rows} columns={[
    { key: 'row', label: t('row'), value: r => r.row }, { key: 'student', label: 'student_id', value: r => r.studentId }, { key: 'course', label: 'course_id', value: r => r.courseId }, { key: 'skill', label: 'skill_id', value: r => r.skillId }, { key: 'validation', label: t('validation'), value: r => r.errors.map(code => t(code as AdminTextKey)).join(' ') || t('valid'), render: r => r.errors.length ? <ul className="admin-validation-errors">{r.errors.map(code => <li key={code}>{t(code as AdminTextKey)}</li>)}</ul> : <span className="admin-valid">{t('valid')}</span> },
  ]}/><button className="button primary" disabled={demoMode || !valid} onClick={() => setConfirm(true)}>{t('confirmImport')}</button></> : <EmptyState title={t('noPreview')}>{t('fileHint')}</EmptyState>}</Card>}<Card className="admin-spaced"><h2>{t('history')}</h2><DataTable label={t('history')} rows={data.imports} status={r => r.status} statuses={['failed','pending']} columns={[
    { key: 'source', label: t('source'), value: r => r.source }, { key: 'timestamp', label: t('timestamp'), value: r => r.timestamp, render: r => formatAdminDate(r.timestamp, locale) }, { key: 'status', label: t('status'), value: r => r.status, render: r => <Status value={r.status}/> }, { key: 'errors', label: t('errors'), value: r => r.errors },
  ]}/></Card>{confirm && <ActionForm title={t('confirmImport')} onClose={() => setConfirm(false)} action={() => ({ type: 'commit-import', source: file?.name ?? '' })}><p>{file?.name} · {preview?.rows.length} {t('records')}</p></ActionForm>}</>
}
