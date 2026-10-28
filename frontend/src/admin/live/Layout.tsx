import { OfficialBtuLogo } from '../../components/PassportCard'
import { AdminNavigation } from '../Navigation'
import '../ux.css'
import { useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { Menu, ShieldCheck } from 'lucide-react'
import { LogoutButton } from '../../auth/SessionPanel'
import { useCapabilities } from './common'
import { useLocale } from '../../i18n'
import '../admin.css'
import '../../student/student.css'
import './live.css'
export function LiveAdminLayout() {
  const grants = useCapabilities(), [open, setOpen] = useState(false), { locale, toggle } = useLocale()
  return <div className="app admin-app admin-live-app"><a className="skip" href="#admin-main">Admin workspace</a>{open && <button className="scrim" aria-label="Close navigation" onClick={() => setOpen(false)}/>}
    <aside className={`sidebar admin-sidebar ${open ? 'open' : ''}`}><Link className="brand" to="/admin/dashboard"><OfficialBtuLogo/><span>AI SKILLS<br/><strong>DIGITAL PASSPORT</strong></span></Link><div className="admin-workspace-label"><ShieldCheck/><span>University administration<small>LIVE · Django records</small></span></div><AdminNavigation grants={grants} close={() => setOpen(false)}/><div className="sidebar-bottom"><p>Access follows your administrator grants.</p></div></aside>
    <div className="main-shell"><header><button className="mobile-menu" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(!open)}><Menu/></button><div className="admin-breadcrumb">Admin workspace · LIVE</div><div className="header-actions"><button onClick={toggle}>{locale.toUpperCase()}</button><LogoutButton role="administrator"/></div></header><main id="admin-main"><p className="notice">Live university records. Available pages and actions reflect your explicit administrator grants.</p><Outlet/></main></div>
  </div>
}
