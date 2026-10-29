import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { History, LayoutDashboard, Menu, ShieldCheck, Sparkles, Target, X } from 'lucide-react'
import { OfficialBtuLogo } from '../components/PassportCard'

const navigation = [
  ['/student/dashboard', 'My Passport', LayoutDashboard],
  ['/student/skills', 'My Skills', Sparkles],
  ['/student/passport/versions', 'Passport History', History],
  ['/student/gap-analyzer', 'Skills Gap Analyzer', Target],
] as const

export function StudentShell({ identity, logout, refresh, children }: { identity?: string; logout?: ReactNode; refresh?: ReactNode; children?: ReactNode }) {
  const [open, setOpen] = useState(false), location = useLocation()
  const landing = location.pathname === '/student/dashboard' || location.pathname === '/student/passport'
  return <div className={landing ? 'app student-workspace student-dashboard-layout' : 'app student-workspace'}>
    <a className="skip" href="#main">Skip to content</a>
    {open && <button className="scrim" aria-label="Close navigation" onClick={() => setOpen(false)}/>}
    <aside className={open ? 'sidebar open' : 'sidebar'}>
      <Link className="brand" to="/student/dashboard"><OfficialBtuLogo/><span>AI SKILLS<br/><strong>DIGITAL PASSPORT</strong></span></Link>
      <div className="workspace"><div><b>Student workspace</b><span>Business &amp; Technology University</span></div></div>
      <nav aria-label="Student navigation">{navigation.map(([path, label, Icon]) => <NavLink end={path === '/student/dashboard'} key={path} to={path} onClick={() => setOpen(false)}><Icon size={19}/>{label}{path.endsWith('gap-analyzer') && <small>Coming Soon</small>}</NavLink>)}<NavLink to="/verify" onClick={() => setOpen(false)}><ShieldCheck size={19}/>Public Verification</NavLink></nav>
      <div className="sidebar-bottom">{identity ? <p className="student-identity"><span>Read-only Student identity</span><strong>{identity}</strong></p> : <p>Demo Mode · fictional Student</p>}{logout ?? <button className="button" disabled>Log Out · Demo Mode</button>}</div>
    </aside>
    <div className="main-shell"><header><button className="mobile-menu" aria-label="Toggle navigation" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X/> : <Menu/>}</button><strong>Student workspace</strong><span className="muted">{identity ? 'University-maintained records' : 'Demo Mode'}</span>{refresh}</header><main id="main">{children ?? <Outlet/>}</main></div>
  </div>
}
export function StudentLayout() { return <StudentShell/> }
