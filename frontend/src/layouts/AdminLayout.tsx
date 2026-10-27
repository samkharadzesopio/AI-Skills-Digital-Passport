import { OfficialBtuLogo } from '../components/PassportCard'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Award, Fingerprint, BookOpen, FileSpreadsheet, FolderTree, Globe2, LayoutDashboard, ListChecks, Menu, RefreshCw, ShieldCheck, Users, X } from 'lucide-react'
import { useLocale } from '../i18n'
import { useAdminText } from '../admin/i18n'
import { useAdminData } from '../admin/store'
import { adminFixture } from '../admin/mock'
import '../admin/admin.css'
const navigation = [
  ['/admin/dashboard', 'overview', LayoutDashboard], ['/admin/students', 'students', Users], ['/admin/skills', 'catalog', FolderTree],
  ['/admin/course-mappings', 'mappings', BookOpen], ['/admin/credentials', 'credentials', Award], ['/admin/classroom-sync', 'sync', RefreshCw],
  ['/admin/passports/preview', 'passportPreview', Fingerprint], ['/admin/imports', 'imports', FileSpreadsheet], ['/admin/audit-logs', 'audit', ListChecks],
] as const
export function AdminLayout() {
  const [open, setOpen] = useState(false), t = useAdminText(), { locale, toggle } = useLocale(), { update } = useAdminData(), location = useLocation()
  const title = navigation.toReversed().find(([path]) => location.pathname === path || (path !== '/admin/dashboard' && location.pathname.startsWith(`${path}/`)))?.[1] ?? 'overview'
  useEffect(() => {
    if (!open) return
    const close = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [open])
  return <div className="app admin-app"><a className="skip" href="#admin-main">{t('overview')}</a>{open && <button className="scrim" aria-label={t('close')} onClick={() => setOpen(false)}/>}
    <aside id="admin-navigation" className={`sidebar admin-sidebar ${open ? 'open' : ''}`}><Link className="brand" to="/admin/dashboard" onClick={() => setOpen(false)}><OfficialBtuLogo/><span>AI SKILLS<br/><strong>DIGITAL PASSPORT</strong></span></Link><div className="admin-workspace-label"><ShieldCheck size={22}/><span>{t('workspace')}<small>{t('demo')}</small></span></div><nav aria-label={t('workspace')}>{navigation.map(([path, key, Icon]) => <NavLink key={path} to={path} end={path === '/admin/dashboard'} onClick={() => setOpen(false)}><Icon size={18}/>{t(key)}</NavLink>)}</nav><div className="sidebar-bottom"><div className="support"><ShieldCheck size={23}/><h3>{t('demo')}</h3><p>{t('demoNotice')}</p></div><nav><Link to="/verify"><Globe2 size={18}/>{t('publicVerification')}</Link></nav></div></aside>
    <div className="main-shell"><header><button className="mobile-menu" aria-label={t('openNavigation')} aria-expanded={open} aria-controls="admin-navigation" onClick={() => setOpen(!open)}>{open ? <X/> : <Menu/>}</button><div className="admin-breadcrumb">{t('workspace')} <span>/</span> <b>{t(title)}</b></div><div className="header-actions"><span className="admin-demo-chip">{t('demo')}</span><button onClick={toggle} aria-label="English / ქართული"><Globe2 size={16}/>{locale.toUpperCase()}</button></div></header><main id="admin-main"><p className="admin-demo-notice">{t('demoNotice')}</p><Outlet/><footer><span>BTU · {t('workspace')}</span><button onClick={() => update(() => structuredClone(adminFixture))}>{t('reset')}</button></footer></main></div>
  </div>
}
