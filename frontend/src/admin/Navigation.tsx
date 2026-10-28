import { NavLink } from 'react-router-dom'
import type { AdminCapability } from '../auth/contracts'

const groups = [
  ['Overview', [['/admin/dashboard', 'Dashboard', 'view_student_records'], ['/admin/students', 'Students', 'view_student_records']]],
  ['Learning Data', [['/admin/skills', 'Skills Catalog', 'view_student_records'], ['/admin/course-mappings', 'Activity-to-Skill Mapping', 'view_student_records']]],
  ['Operations', [['/admin/imports', 'Data Imports', 'import_completions'], ['/admin/credentials', 'Credentials', 'view_student_records']]],
  ['Trust & System', [['/verify', 'Verification', null], ['/admin/passports/preview', 'Passport Records', 'view_student_records'], ['/admin/audit-logs', 'Audit Logs', 'view_student_records']]],
  ['Secondary Features', [['/admin/classroom-sync', 'BTU Classroom Sync · Simulated', 'sync_classroom']]],
] as const

export function AdminNavigation({ grants, close }: { grants?: AdminCapability[]; close: () => void }) {
  return <nav aria-label="Admin navigation" className="admin-grouped-navigation">{groups.map(([label, entries]) => {
    const visible = entries.filter(([, , capability]) => !grants || !capability || grants.includes(capability))
    return visible.length ? <section key={label} aria-label={label}><h2>{label}</h2>{visible.map(([path, title]) => <NavLink key={path} to={path} end={path === '/admin/dashboard' || path === '/verify'} onClick={close}>{title}</NavLink>)}</section> : null
  })}</nav>
}

export function AdminWorkflow() {
  return <p className="admin-workflow">Import records <span aria-hidden="true">→</span> Validate evidence <span aria-hidden="true">→</span> Recognize approved skills <span aria-hidden="true">→</span> Issue credentials <span aria-hidden="true">→</span> Update Passport <span aria-hidden="true">→</span> Verify</p>
}
