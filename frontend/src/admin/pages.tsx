import { demoMode } from '../demo/mode'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Award, Fingerprint, RefreshCw, Users } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, EmptyState } from '../components/ui'
import { useLocale } from '../i18n'
import { useAdminData } from './store'
import { useAdminText, formatAdminDate } from './i18n'
import { ActionForm, DataTable, Dialog, PageTitle, Status } from './components'
import { skills } from './catalog'
import type { SyncEvent } from './contracts'

export function AdminDashboard() {
  const { data } = useAdminData(), t = useAdminText(), { locale } = useLocale()
  const stats = [
    { label: t('totalStudents'), value: data.students.length, icon: Users, color: 'pink' },
    { label: t('verifiedCredentials'), value: data.credentials.filter(c => c.status === 'verified').length, icon: Award, color: 'purple' },
    { label: t('activePassports'), value: data.students.filter(s => s.passportStatus === 'active').length, icon: Fingerprint, color: 'teal' },
    { label: t('pendingSync'), value: data.syncEvents.filter(e => e.status === 'pending').length, icon: RefreshCw, color: 'orange' },
  ]
  return <><PageTitle title={t('overview')} description={t('overviewHint')}/><div className="stats">{stats.map(s => <Card className="stat" key={s.label}><div className="stat-top"><span>{s.label}</span><div className={`icon-box ${s.color}`}><s.icon size={20}/></div></div><strong>{s.value}</strong><p>{t('sampleTotals')}</p></Card>)}</div><div className="admin-overview-grid"><Card><div className="section-title"><h2>{t('issuanceTrend')}</h2><span className="admin-demo-chip">{t('demo')}</span></div><div className="admin-chart" role="img" aria-label={data.issuanceTrend.map(d => `${d.month}: ${d.count}`).join(', ')}><ResponsiveContainer width="100%" height="100%"><BarChart data={data.issuanceTrend} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}><CartesianGrid vertical={false} strokeDasharray="3 5" stroke="#eeeaf4"/><XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 12 }}/><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 12 }}/><Tooltip/><Bar dataKey="count" name={t('credentials')} fill="#e5007d" radius={[5,5,0,0]} maxBarSize={35}/></BarChart></ResponsiveContainer></div></Card><Card><div className="section-title"><h2>{t('recentActivity')}</h2><Link to="/admin/audit-logs">{t('details')}</Link></div><ul className="admin-activity">{data.audit.toSorted((a,b) => b.timestamp.localeCompare(a.timestamp)).slice(0,5).map(entry => <li key={entry.id}><span className="admin-activity-dot"/><div><strong>{entry.action}</strong><p>{entry.actor} · {entry.record}</p><small>{formatAdminDate(entry.timestamp, locale)}</small></div></li>)}</ul></Card></div></>
}
export function StudentsPage() {
  const { data } = useAdminData(), t = useAdminText(), [program, setProgram] = useState('')
  return <><PageTitle title={t('students')}/><Card><div className="admin-inline-filter"><label htmlFor="student-program">{t('program')}</label><select id="student-program" value={program} onChange={e => setProgram(e.target.value)}><option value="">{t('all')}</option>{[...new Set(data.students.map(s => s.program))].map(p => <option key={p}>{p}</option>)}</select></div><DataTable label={t('students')} rows={data.students.filter(s => !program || s.program === program)} status={s => s.passportStatus} statuses={['active','pending','revoked','not-issued']} columns={[
    { key: 'name', label: t('student'), value: s => s.name, render: s => <Link className="admin-record-link" to={`/admin/students/${s.id}`}><strong>{s.name}</strong><small>{s.id}</small></Link> },
    { key: 'email', label: t('email'), value: s => s.email }, { key: 'program', label: t('program'), value: s => s.program },
    { key: 'skills', label: t('skills'), value: s => s.skillIds.map(id => skills(data).find(skill => skill.id === id)?.name ?? id).join(', ') },
    { key: 'credentials', label: t('credentials'), value: s => s.credentialIds.length },
    { key: 'status', label: t('passport'), value: s => s.passportStatus, render: s => <Status value={s.passportStatus}/> },
  ]}/></Card></>
}
export function StudentDetail() {
  const { id } = useParams(), { data } = useAdminData(), t = useAdminText(), student = data.students.find(s => s.id === id)
  if (!student) return <EmptyState title={t('missing')}><Link to="/admin/students">{t('back')}</Link></EmptyState>
  return <><Link className="admin-back" to="/admin/students">← {t('back')}</Link><PageTitle title={student.name} description={student.id} action={<Link className="button" to={`/admin/students/${student.id}/passport`}>{t('passportPreview')}</Link>}/><Card><dl className="admin-detail-list"><dt>{t('email')}</dt><dd>{student.email}</dd><dt>{t('program')}</dt><dd>{student.program}</dd><dt>{t('passport')}</dt><dd><Status value={student.passportStatus}/></dd></dl><h2>{t('skills')}</h2><ul className="admin-detail-items">{student.skillIds.map(skillId => <li key={skillId}>{skills(data).find(s => s.id === skillId)?.name ?? skillId}<small>{skillId}</small></li>)}</ul>{!student.skillIds.length && <p>{t('noSkills')}</p>}<h2>{t('supportingCredentials')}</h2><ul className="admin-detail-items">{student.credentialIds.map(credentialId => <li key={credentialId}><Link to={`/admin/credentials/${credentialId}`}>{data.credentials.find(c => c.id === credentialId)?.title ?? credentialId}</Link></li>)}</ul>{!student.credentialIds.length && <p>{t('noCredentials')}</p>}</Card></>
}
export function CredentialsPage() {
  const { data } = useAdminData(), t = useAdminText(), [issue, setIssue] = useState(false), [studentId, setStudentId] = useState(''), [title, setTitle] = useState('')
  return <><PageTitle title={t('credentials')} action={<button className="button primary" disabled={demoMode} onClick={() => setIssue(true)}>{t('issue')}</button>}/><Card><DataTable label={t('credentials')} rows={data.credentials} status={c => c.status} statuses={['verified','pending','revoked']} columns={[
    { key: 'title', label: t('title'), value: c => c.title, render: c => <Link className="admin-record-link" to={`/admin/credentials/${c.id}`}><strong>{c.title}</strong><small>{c.id}</small></Link> },
    { key: 'student', label: t('student'), value: c => data.students.find(s => s.id === c.studentId)?.name ?? c.studentId },
    { key: 'issuer', label: t('issuer'), value: c => c.issuer },
    { key: 'status', label: t('status'), value: c => c.status, render: c => <Status value={c.status}/> },
  ]}/></Card>{issue && <ActionForm title={t('issue')} onClose={() => setIssue(false)} action={() => ({ type: 'issue', studentId, title: title.trim() })} validate={() => !data.students.some(s => s.id === studentId) || title.trim().length < 2 || title.trim().length > 100 ? t('fieldRequired') : null}><label htmlFor="issue-student">{t('student')}</label><select required id="issue-student" value={studentId} onChange={e => setStudentId(e.target.value)}><option value="">—</option>{data.students.map(s => <option key={s.id} value={s.id}>{s.name} · {s.id}</option>)}</select><label htmlFor="issue-title">{t('credentialTitle')}</label><input id="issue-title" required minLength={2} maxLength={100} value={title} onChange={e => setTitle(e.target.value)}/></ActionForm>}</>
}
export function CredentialDetail() {
  const { id } = useParams(), { data } = useAdminData(), t = useAdminText(), { locale } = useLocale(), [revoke, setRevoke] = useState(false), [reason, setReason] = useState('')
  const credential = data.credentials.find(c => c.id === id)
  if (!credential) return <EmptyState title={t('missing')}><Link to="/admin/credentials">{t('back')}</Link></EmptyState>
  return <><Link className="admin-back" to="/admin/credentials">← {t('back')}</Link><PageTitle title={credential.title} description={credential.id} action={<button className="button admin-danger" disabled={demoMode || credential.status !== 'verified'} onClick={() => setRevoke(true)}>{t('revoke')}</button>}/><Card><dl className="admin-detail-list"><dt>{t('student')}</dt><dd><Link to={`/admin/students/${credential.studentId}`}>{data.students.find(s => s.id === credential.studentId)?.name ?? credential.studentId}</Link></dd><dt>{t('issuer')}</dt><dd>{credential.issuer}</dd><dt>{t('issuedAt')}</dt><dd>{formatAdminDate(credential.issuedAt, locale)}</dd><dt>{t('status')}</dt><dd><Status value={credential.status}/></dd></dl><h2>{t('evidence')}</h2><ul className="admin-detail-items">{credential.evidence.map(e => <li key={e}>{e}</li>)}</ul></Card>{revoke && <ActionForm title={t('revoke')} onClose={() => setRevoke(false)} action={() => ({ type: 'revoke', credentialId: credential.id, reason: reason.trim() })} validate={() => reason.trim().length < 10 || reason.trim().length > 500 ? t('reasonInvalid') : null}><label htmlFor="revoke-reason">{t('reason')}</label><textarea id="revoke-reason" required minLength={10} maxLength={500} value={reason} onChange={e => setReason(e.target.value)}/></ActionForm>}</>
}
export function SynchronizationPage() {
  const { data } = useAdminData(), t = useAdminText(), { locale } = useLocale(), [preview, setPreview] = useState<SyncEvent | null>(null), [retry, setRetry] = useState<SyncEvent | null>(null)
  return <><PageTitle title={t('sync')} description={t('syncHint')}/><Card><DataTable label={t('sync')} rows={data.syncEvents} status={e => e.status} statuses={['failed','pending']} columns={[
    { key: 'id', label: t('event'), value: e => e.id }, { key: 'course', label: t('course'), value: e => data.courses.find(c => c.id === e.courseId)?.title ?? e.courseId },
    { key: 'timestamp', label: t('timestamp'), value: e => e.timestamp, render: e => formatAdminDate(e.timestamp, locale) },
    { key: 'status', label: t('status'), value: e => e.status, render: e => <Status value={e.status}/> }, { key: 'attempts', label: t('attempts'), value: e => e.attempts },
    { key: 'failure', label: t('failure'), value: e => e.error ?? t('noFailure') },
    { key: 'actions', label: t('actions'), value: e => e.id, render: e => <div className="admin-row-actions"><button className="button" onClick={() => setPreview(e)}>{t('preview')}</button><button className="button" disabled={demoMode || e.status !== 'failed'} onClick={() => setRetry(e)}>{t('retry')}</button></div> },
  ]}/></Card>{preview && <Dialog title={`${t('preview')} · ${preview.id}`} onClose={() => setPreview(null)}><p className="notice">{t('previewNotice')}</p><ul className="admin-detail-items">{preview.preview.map((p,i) => <li key={i}><strong>{t('externalStudent')}: {p.externalStudentId}</strong><p>{t('proposedSkills')}: {p.proposedSkillIds.map(id => skills(data).find(s => s.id === id)?.name ?? id).join(', ')}</p></li>)}</ul></Dialog>}{retry && <ActionForm title={t('retry')} onClose={() => setRetry(null)} action={() => ({ type: 'retry-sync', eventId: retry.id })}><p>{retry.id} · {t('attempts')}: {retry.attempts}</p></ActionForm>}</>
}
export function AuditPage() {
  const { data } = useAdminData(), t = useAdminText(), { locale } = useLocale()
  return <><PageTitle title={t('audit')} description={t('auditHint')}/><Card><DataTable label={t('audit')} rows={data.audit} columns={[
    { key: 'timestamp', label: t('timestamp'), value: e => e.timestamp, render: e => formatAdminDate(e.timestamp, locale) }, { key: 'actor', label: t('actor'), value: e => e.actor }, { key: 'action', label: t('action'), value: e => e.action }, { key: 'record', label: t('affectedRecord'), value: e => e.record },
  ]}/></Card></>
}
