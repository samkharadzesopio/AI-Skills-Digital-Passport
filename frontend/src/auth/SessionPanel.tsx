import { useState } from 'react'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { demoMode } from '../demo/mode'
import { Card } from '../components/ui'
import { useAuthText } from './i18n'
import { useSession } from './hooks'
import { logoutAccount } from './service'
import type { AccessDecision } from './contracts'
import './auth.css'
import { StudentShell } from '../layouts/StudentShell'
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
  return <div className="auth-status-page"><Card><h1>{t('signedIn')}</h1><p className="muted">{session.data?.status==='authenticated'?session.data.user.email:''}</p><p className="notice" role="status">{t(key)}</p><p className="muted">{t('switchAccount')}</p><LogoutButton role={role}/><Link className="button" to="/verify">{t('publicVerification')}</Link></Card></div>
}
export function LiveAccountLayout() {
  const session = useSession(), client = useQueryClient(), [refreshing, setRefreshing] = useState(false)
  async function refresh() {
    setRefreshing(true)
    try { await client.invalidateQueries({ queryKey: ['session'] }); await client.invalidateQueries({ queryKey: ['student'] }) }
    finally { setRefreshing(false) }
  }
  return <StudentShell identity={session.data?.status === 'authenticated' ? session.data.user.email : undefined} logout={<LogoutButton role="student"/>} refresh={<button className="button" disabled={refreshing} onClick={() => void refresh()}>Refresh records</button>}/>
}
export function LiveStudentWorkspace() {
  return <Outlet/>
}
