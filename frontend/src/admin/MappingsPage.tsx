import { useState } from 'react'
import type { FormEvent } from 'react'
import { Card } from '../components/ui'
import { useLocale } from '../i18n'
import { useAdminData } from './store'
import { formatAdminDate, useAdminText } from './i18n'
import { DataTable, Dialog, PageTitle, Status } from './components'
import { saveMapping, skills } from './catalog'
import type { AdminCourse } from './contracts'
export function MappingsPage() {
  const { data, update } = useAdminData(), t = useAdminText(), { locale } = useLocale(), [course, setCourse] = useState<AdminCourse | null>(null), [selected, setSelected] = useState<string[]>([]), [error, setError] = useState(''), [notice, setNotice] = useState('')
  function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    if (!course) return
    try { update(current => saveMapping(current, course.id, selected)); setNotice(t('saved')); setCourse(null) } catch { setError(t('mappingInvalid')) }
  }
  return <><PageTitle title={t('mappings')} description={t('mappingHint')}/>{notice && <p role="status" className="notice">{notice}</p>}<Card><DataTable label={t('mappings')} rows={data.courses} status={c => c.mappingStatus} statuses={['approved','draft','unmapped']} columns={[
    { key: 'title', label: t('course'), value: c => c.title, render: c => <div><strong>{c.title}</strong><small className="admin-cell-id">{c.id}</small></div> },
    { key: 'approved', label: t('approvedCourse'), value: c => c.approved ? t('yes') : t('no') },
    { key: 'skills', label: t('skills'), value: c => c.skillIds.map(id => skills(data).find(s => s.id === id)?.name ?? id).join(', ') },
    { key: 'status', label: t('mappingStatus'), value: c => c.mappingStatus, render: c => <Status value={c.mappingStatus}/> },
    { key: 'approval', label: t('approval'), value: c => c.approvedBy ?? t('notApproved'), render: c => <div>{c.approvedBy ?? t('notApproved')}<small className="admin-cell-id">{formatAdminDate(c.approvedAt, locale)}</small></div> },
    { key: 'actions', label: t('actions'), value: c => c.id, render: c => <button className="button" disabled={!c.approved} onClick={() => { setCourse(c); setSelected([...c.skillIds]); setError('') }}>{t('editMapping')}</button> },
  ]}/></Card>{course && <Dialog title={`${t('editMapping')} · ${course.title}`} onClose={() => setCourse(null)}><form onSubmit={submit}><fieldset className="admin-checkbox-list"><legend>{t('selectSkills')}</legend>{skills(data).filter(s => s.status === 'approved').map(s => <label key={s.id}><input type="checkbox" checked={selected.includes(s.id)} onChange={e => setSelected(e.target.checked ? [...selected,s.id] : selected.filter(id => id !== s.id))}/><span>{s.name}<small>{s.id}</small></span></label>)}</fieldset>{error && <p className="error" role="alert">{error}</p>}<p className="notice">{t('localOnly')}</p><div className="admin-form-actions"><button type="button" className="button" onClick={() => setCourse(null)}>{t('cancel')}</button><button className="button primary">{t('save')}</button></div></form></Dialog>}</>
}
