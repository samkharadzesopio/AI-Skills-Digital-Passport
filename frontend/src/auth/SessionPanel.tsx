import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { demoMode } from '../demo/mode'
import { Card, EmptyState } from '../components/ui'
import { useAuthText } from './i18n'
import { useSession } from './hooks'
import { logoutAccount } from './service'
import type { AccessDecision } from './contracts'
import './auth.css'
import { StudentShell } from '../layouts/StudentShell'
import { BlankPassport } from '../student/BlankPassport'
import { PassportHistory } from '../student/PassportHistory'
import { Gap } from '../pages'
export function LogoutButton({role}:{role:'student'|'administrator'}) {
  const [pending,setPending]=useState(false),[error,setError]=useState(false),client=useQueryClient(),navigate=useNavigate(),t=useAuthText()
  async function logout(){
    if(demoMode||pending)return
    setPending(true);setError(false)
    await client.cancelQueries()
    client.removeQueries({predicate:q=>q.queryKey[0]!=='session'})
    try {
      await logoutAccount()
      await client.cancelQueries();client.clear();client.setQueryData(['session'],{status:'anonymous'})
      navigate(role==='student'?'/student/login':'/admin/login',{replace:true})
    } catch {setError(true)} finally{setPending(false)}
  }
  return <div className="auth-logout"><button className="button" disabled={demoMode||pending} onClick={()=>void logout()}><LogOut size={15}/>{pending?t('loading'):t('logout')}</button>{error&&<p className="error" role="alert">{t('logoutFailed')}</p>}</div>
}
export function AccessBlocked({decision,role}:{decision:Exclude<AccessDecision,'allow'|'login'>;role:'student'|'administrator'}) {
  const t=useAuthText(),session=useSession()
  const key=decision==='permissions-missing'?'permissionsMissing':decision==='wrong-role'?'wrongRole':decision
  if (decision === 'unlinked' && role === 'student') return <UnlinkedStudentPreview/>
  return <div className="auth-status-page"><Card><h1>{t('signedIn')}</h1><p className="muted">{session.data?.status==='authenticated'?session.data.user.email:''}</p><p className="notice" role="status">{t(key)}</p><p className="muted">{t('switchAccount')}</p><LogoutButton role={role}/><Link className="button" to="/verify">{t('publicVerification')}</Link></Card></div>
}
/** The access guard still blocks private records. Only the account summary is read. */
function UnlinkedStudentPreview() {
  const session = useSession(), client = useQueryClient(), location = useLocation()
  const email = session.data?.status === 'authenticated' ? session.data.user.email : undefined
  const path = location.pathname
  return <StudentShell identity={email} logout={<LogoutButton role="student"/>} refresh={<button className="button" disabled={session.isFetching} onClick={() => void client.invalidateQueries({ queryKey: ['session'] })}>Refresh records</button>}>
    {path.startsWith('/student/passport/versions') || path === '/student/history' ? <PassportHistory versions={[]}/> : path === '/student/gap-analyzer' ? <Gap/> : path === '/student/skills' ? <Card><h1>My Skills</h1><EmptyState title="Your learning journey starts here">Approved skills will appear once your academic records are linked by BTU.</EmptyState></Card> : <BlankPassport/>}
  </StudentShell>
}
export function LiveAccountLayout() {
  const session = useSession(), client = useQueryClient(), [refreshing, setRefreshing] = useState(false)
  async function refresh() {
    setRefreshing(true)
    try { await client.invalidateQueries({ queryKey: ['session'] }); await client.invalidateQueries({ queryKey: ['student'] }) }
    finally { setRefreshing(false) }
  }
  return <StudentShell identity={session.data?.status === 'authenticated' ? session.data.user.email : undefined} logout={<LogoutButton role="student"/>} refresh={<>{session.data?.status==="authenticated"&&!session.data.user.portal_access&&<Link to="/student/google-link">Google sign-in settings</Link>}<button className="button" disabled={refreshing} onClick={() => void refresh()}>Refresh records</button></>}/>
}
export function LiveStudentWorkspace() {
  const session = useSession()
  if (session.data?.status === 'authenticated' && session.data.user.portal_access && session.data.user.student_association === 'unlinked') return <EmptyPortal/>
  return <Outlet/>
}

function EmptyPortal() {
  const session = useSession()
  return <Card><h1>My Passport</h1><p>Welcome to your personal BTU portal.</p><p>{session.data?.status === 'authenticated' ? session.data.user.email : ''}</p>
    <h2>No Passport records are linked yet</h2><p>Your portal is ready. There are no linked skills, awards or Passport documents to display.</p>
    <p>Historical records remain private until the university confirms your institutional identity mapping. Future approved awards will appear after that mapping is available.</p>
    <p role="status">Passport association pending. No credential or blockchain proof has been issued for this empty portal.</p><Link to="/verify">Public verification</Link></Card>
}
