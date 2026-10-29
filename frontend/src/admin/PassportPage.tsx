import { Link, useParams } from 'react-router-dom'
import { PassportPreview } from '../components/PassportPreview'
import { Card, EmptyState } from '../components/ui'
import { demoPassport } from '../data/passport'
import { useAdminData } from './store'
import { PageTitle } from './components'
import { useAdminText } from './i18n'

export function AdminPassportPage() {
  const { id } = useParams(), { data } = useAdminData(), t = useAdminText()
  const student = id ? data.students.find(s => s.id === id) : null
  if (id && !student) return <EmptyState title={t('missing')}><Link to="/admin/students">{t('back')}</Link></EmptyState>
  // An independent demonstration presentation, never an adapter for official records.
  const passport = student ? { ...demoPassport, holder: { ...demoPassport.holder, externalStudentId: student.id, displayName: `${student.name} (demo)`, firstName: student.name, lastName: '', program: student.program } } : demoPassport
  return <><PageTitle title={t('passportPreview')} description="Demonstration presentation only; real issued snapshots are not loaded."/><Card><PassportPreview passport={passport} showTemplate/></Card></>
}
