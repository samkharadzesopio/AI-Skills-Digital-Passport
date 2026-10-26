import { Navigate, Outlet } from 'react-router-dom'
import { Card, EmptyState, Loading } from '../components/ui'
import { demoMode } from '../demo/mode'
import { useCountdown, useSession } from './hooks'
import { accessDecision } from './contracts'
import { AccessBlocked } from './SessionPanel'
import { useAuthText } from './i18n'
import { AuthError } from './errors'

export function AccessBoundary({ role }: { role: 'student' | 'administrator' }) {
  // Mount no session hook or real authentication code while previewing mock workspaces.
  if (demoMode) return <Outlet/>
  return <AuthenticatedBoundary role={role}/>
}
function AuthenticatedBoundary({ role }: { role: 'student' | 'administrator' }) {
  const session = useSession(), t = useAuthText()
  const failure=session.error instanceof AuthError?session.error:null
  const retryIn=useCountdown(failure?.retryAt??0)
  if (session.isPending) return <Loading/>
  if (session.isError) return <Card><EmptyState title={t('unavailable')}>{t(failure?.code??'network')}</EmptyState><button className="button" disabled={retryIn>0} onClick={() => session.refetch()}>{t('retry')}</button>{retryIn>0&&<p role="status">{t('retryIn')} {retryIn} {t('seconds')}</p>}</Card>
  const decision=accessDecision(session.data,role)
  if(decision==='login')return <Navigate replace to={role==='student'?'/student/login':'/admin/login'}/>
  if(decision==='allow')return <Outlet/>
  return <AccessBlocked decision={decision} role={role}/>
}
