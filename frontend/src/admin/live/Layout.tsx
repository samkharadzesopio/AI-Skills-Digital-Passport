import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { BookOpen, FileSpreadsheet, Fingerprint, FolderTree, LayoutDashboard, ListChecks, Menu, RefreshCw, ShieldCheck, Users, Award } from 'lucide-react'
import type { AdminCapability } from '../../auth/contracts'
import { LogoutButton } from '../../auth/SessionPanel'
import { useCapabilities } from './common'
import { useLocale } from '../../i18n'
import '../admin.css'
import '../../student/student.css'
import './live.css'
const navigation = [
  ['/admin/dashboard', 'Dashboard', LayoutDashboard, 'view_student_records'], ['/admin/students', 'Students', Users, 'view_student_records'],
  ['/admin/skills', 'Skill catalog', FolderTree, 'view_student_records'], ['/admin/course-mappings', 'Course mappings', BookOpen, 'view_student_records'],
  ['/admin/credentials', 'Credentials', Award, 'view_student_records'], ['/admin/classroom-sync', 'Classroom · SIMULATED', RefreshCw, 'sync_classroom'],
  ['/admin/passports/preview', 'Passports', Fingerprint, 'view_student_records'], ['/admin/imports', 'Imports', FileSpreadsheet, 'import_completions'],
  ['/admin/audit-logs', 'History', ListChecks, 'view_student_records'],
] as const
export function LiveAdminLayout() {
  const grants = useCapabilities(), [open, setOpen] = useState(false), { locale, toggle } = useLocale()
  return <div className="app admin-app admin-live-app"><a className="skip" href="#admin-main">Admin workspace</a>{open && <button className="scrim" aria-label="Close navigation" onClick={() => setOpen(false)}/>}
    <aside className={`sidebar admin-sidebar ${open ? 'open' : ''}`}><Link className="brand" to="/admin/dashboard"><b>BTU<span>✳</span></b><span>AI SKILLS<br/><strong>DIGITAL PASSPORT</strong></span></Link><div className="admin-workspace-label"><ShieldCheck/><span>University administration<small>LIVE · Django records</small></span></div><nav aria-label="Admin navigation">{navigation.filter(([, , , cap]) => grants.includes(cap as AdminCapability)).map(([path, label, Icon]) => <NavLink key={path} to={path} end onClick={() => setOpen(false)}><Icon size={18}/>{label}</NavLink>)}</nav><div className="sidebar-bottom"><Link to="/verify">Public verification</Link></div></aside>
    <div className="main-shell"><header><button className="mobile-menu" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(!open)}><Menu/></button><div className="admin-breadcrumb">Admin workspace · LIVE</div><div className="header-actions"><button onClick={toggle}>{locale.toUpperCase()}</button><LogoutButton role="administrator"/></div></header><main id="admin-main"><p className="notice">Live university records. Available pages and actions reflect your explicit administrator grants.</p><Outlet/></main></div>
  </div>
}
