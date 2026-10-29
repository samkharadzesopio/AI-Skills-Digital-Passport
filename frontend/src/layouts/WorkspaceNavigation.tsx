import { NavLink } from 'react-router-dom'
import './workspace-navigation.css'

export function WorkspaceNavigation() {
  return <nav className="workspace-navigation" aria-label="Passport workspaces">
    <NavLink to="/student/dashboard">Student Dashboard</NavLink>
    <NavLink to="/admin/dashboard">Admin Dashboard</NavLink>
    <NavLink to="/verify">Public Verification</NavLink>
  </nav>
}
