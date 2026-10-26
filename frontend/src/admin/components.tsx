import { demoMode } from '../demo/mode'
import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode, FormEvent } from 'react'
import { ArrowDown, ArrowUp, Search, X } from 'lucide-react'
import { EmptyState } from '../components/ui'
import { useAdminText } from './i18n'
import type { AdminTextKey } from './i18n'
import { filterSortRows } from './tableLogic'
import { requestAdminAction } from './services'
import type { AdminAction } from './services'

export interface Column<T> { key: string; label: string; value: (row: T) => string | number; render?: (row: T) => ReactNode }
export function DataTable<T extends { id: string }>({ rows, columns, status, statuses = [], label }: {
  rows: T[]; columns: Column<T>[]; status?: (row: T) => string; statuses?: AdminTextKey[]; label: string
}) {
  const t = useAdminText(), id = useId()
  const [search, setSearch] = useState(''), [filter, setFilter] = useState(''), [sort, setSort] = useState(columns[0].key), [descending, setDescending] = useState(false), [page, setPage] = useState(1)
  const column = columns.find(c => c.key === sort) ?? columns[0]
  const filtered = filterSortRows(rows.filter(row => !filter || !status || status(row) === filter), search, row => columns.map(c => c.value(row)).join(' '), column.value, descending)
  const pageCount = Math.max(1, Math.ceil(filtered.length / 8)), current = Math.min(page, pageCount)
  return <div className="admin-table-block">
    <div className="admin-table-tools"><div className="admin-search"><Search size={16}/><label className="sr-only" htmlFor={id}>{t('search')} · {label}</label><input id={id} type="search" placeholder={t('search')} value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}/></div>
      {status && <><label className="sr-only" htmlFor={`${id}-status`}>{t('status')}</label><select id={`${id}-status`} value={filter} onChange={e => { setFilter(e.target.value); setPage(1) }}><option value="">{t('all')}</option>{statuses.map(s => <option value={s} key={s}>{t(s)}</option>)}</select></>}
    </div>
    <div className="admin-table-scroll"><table><caption className="sr-only">{label}</caption><thead><tr>{columns.map(c => <th scope="col" key={c.key} aria-sort={sort === c.key ? descending ? 'descending' : 'ascending' : 'none'}><button onClick={() => { setSort(c.key); setDescending(sort === c.key ? !descending : false); setPage(1) }}>{c.label}{sort === c.key && (descending ? <ArrowDown size={12}/> : <ArrowUp size={12}/>)}</button></th>)}</tr></thead><tbody>{filtered.slice((current - 1) * 8, current * 8).map(row => <tr key={row.id}>{columns.map(c => <td key={c.key}>{c.render ? c.render(row) : c.value(row)}</td>)}</tr>)}</tbody></table></div>
    {!filtered.length && <EmptyState title={t('noRecords')}>{t('noRecordsHint')}</EmptyState>}
    <div className="admin-pagination"><span aria-live="polite">{filtered.length} {t('records')} · {t('page')} {current} {t('of')} {pageCount}</span><div><button className="button" disabled={current <= 1} onClick={() => setPage(current - 1)}>{t('previous')}</button><button className="button" disabled={current >= pageCount} onClick={() => setPage(current + 1)}>{t('next')}</button></div></div>
  </div>
}
export function Status({ value }: { value: AdminTextKey }) { const t = useAdminText(); return <span className={`admin-status status-${value}`}>{t(value)}</span> }
export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null), id = useId(), t = useAdminText()
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => { dialog?.close() } }, [])
  return <dialog ref={ref} className="admin-dialog" aria-labelledby={id} onCancel={onClose} onClose={onClose}><div className="admin-dialog-title"><h2 id={id}>{title}</h2><button type="button" className="button" onClick={onClose} aria-label={t('close')}><X size={18}/></button></div>{children}</dialog>
}
export function PageTitle({ title, description, action }: { title: string; description?: string; action?: ReactNode }) { return <div className="admin-page-title"><div><div className="eyebrow">BTU AI SKILLS DIGITAL PASSPORT</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div> }
export function ActionForm({ title, onClose, action, children, validate }: { title: string; onClose: () => void; action: () => AdminAction; children?: ReactNode; validate?: () => string | null }) {
  const t = useAdminText(), [error, setError] = useState(''), [pending, setPending] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    const invalid = validate?.()
    if (invalid) { setError(invalid); return }
    setPending(true)
    try { await requestAdminAction(action()) } catch { setError(t('backendUnavailable')) } finally { setPending(false) }
  }
  return <Dialog title={title} onClose={onClose}><p className="notice">{t('noAction')}</p><form onSubmit={submit}>{children}{error && <p className="error" role="alert">{error}</p>}<div className="admin-form-actions"><button type="button" className="button" onClick={onClose}>{t('cancel')}</button><button className="button primary" disabled={pending || demoMode}>{pending ? t('submitting') : title}</button></div></form></Dialog>
}
