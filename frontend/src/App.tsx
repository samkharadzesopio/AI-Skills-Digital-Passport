import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { Gamepad2 } from 'lucide-react'
import { LocaleProvider } from './i18n'
import { AccessBoundary } from './auth/AccessBoundary'
import { StudentLayout } from './layouts/StudentLayout'
import { AdminLayout } from './layouts/AdminLayout'
import { VerificationLayout } from './layouts/VerificationLayout'
import { Dashboard, Detail, Profile, Gap } from './pages'
import { VerificationLanding, ReferenceVerificationPage, PdfVerification, VerificationResults, QrVerification, VerificationNotFound } from './verification/pages'
import { AdminWorkspace } from './admin/store'
import { AdminDashboard, StudentsPage, StudentDetail, CredentialsPage, CredentialDetail, SynchronizationPage, AuditPage } from './admin/pages'
import { CatalogPage } from './admin/CatalogPage'
import { MappingsPage } from './admin/MappingsPage'
import { ImportsPage } from './admin/ImportsPage'
import { AdminPassportPage } from './admin/PassportPage'
import { Card, EmptyState, Loading } from './components/ui'
import { getDemoStudent } from './data/mock'
import './App.css'
import { DemoBanner } from './demo/DemoBanner'
import { demoMode } from './demo/mode'
import { LoginPage } from './auth/LoginPages'
import { LiveAccountLayout, LiveStudentWorkspace } from './auth/SessionPanel'
import { LiveDashboard, LiveProfile, LiveSkills, LiveAchievements, LiveCredentials, LiveCredential, LivePassport, LiveVersions, LiveVersion } from './student/pages'
import { LiveAdminLayout } from './admin/live/Layout'
import { Gate as AdminGate } from './admin/live/common'
import * as AdminLive from './admin/live/pages'
import { PassportPage as LiveAdminPassport } from './admin/live/PassportPage'
import { SyncPage as LiveAdminSync, ImportsPage as LiveAdminImports } from './admin/live/integrations'
const client = new QueryClient()
function StudentDataBoundary() {
  if (!demoMode) return <LiveStudentWorkspace/>
  return <DemoStudentDataBoundary/>
}
function DemoStudentDataBoundary() {
  const student = useQuery({ queryKey: ['demo-student'], queryFn: getDemoStudent })
  if (student.isPending) return <Loading/>
  if (student.isError) return <Card><EmptyState title="Unable to load student preview">Please try again.</EmptyState><button className="button" onClick={() => student.refetch()}>Retry</button></Card>
  return <Outlet/>
}
function LegacyRedirect({ to }: { to: string }) {
  const location = useLocation()
  return <Navigate replace to={{ pathname: to, search: location.search, hash: location.hash }}/>
}
function NotFound() { return <EmptyState title="Page not found"><Link to="/verify">Go to public verification</Link></EmptyState> }
export function AppRoutes() {
  return <Routes>
    <Route path="student">
      <Route path="login" element={<LoginPage kind="student"/>}/>
      <Route element={<AccessBoundary role="student"/>}>
      <Route index element={<LegacyRedirect to="/student/dashboard"/>}/>
      <Route element={demoMode ? <StudentLayout/> : <LiveAccountLayout/>}>
        <Route element={<StudentDataBoundary/>}>
          <Route path="dashboard" element={demoMode ? <Dashboard/> : <LiveDashboard/>}/>
          <Route path="skills" element={demoMode ? <Detail page="AI skills & competencies"/> : <LiveSkills/>}/>
          <Route path="achievements" element={demoMode ? <Card>Achievement records are available in the live student workspace.</Card> : <LiveAchievements/>}/>
          <Route path="credentials" element={demoMode ? <Detail page="Verified credentials"/> : <LiveCredentials/>}/>
          <Route path="credentials/:id" element={demoMode ? <NotFound/> : <LiveCredential/>}/>
          <Route path="passport" element={demoMode ? <Detail page="Digital passport preview"/> : <LivePassport/>}/>
          <Route path="passport/versions" element={demoMode ? <NotFound/> : <LiveVersions/>}/>
          <Route path="passport/versions/:id" element={demoMode ? <NotFound/> : <LiveVersion/>}/>
          <Route path="profile" element={demoMode ? <Profile/> : <LiveProfile/>}/>
          <Route path="gap-analyzer" element={<Gap/>}/>
          <Route path="game" element={<Card><EmptyState title="AI playground coming soon">A future Dino-style game is planned for online and offline play.</EmptyState><Gamepad2 className="game-icon" size={64}/></Card>}/>
          <Route path="*" element={<NotFound/>}/>
        </Route>
      </Route>
      </Route>
    </Route>
    <Route path="admin">
      <Route path="login" element={<LoginPage kind="administrator"/>}/>
      <Route element={<AccessBoundary role="administrator"/>}>
      <Route index element={<LegacyRedirect to="/admin/dashboard"/>}/>
      <Route element={demoMode ? <AdminWorkspace/> : <Outlet/>}>
        <Route element={demoMode ? <AdminLayout/> : <LiveAdminLayout/>}>
          <Route path="dashboard" element={demoMode ? <AdminDashboard/> : <AdminGate capability="view_student_records"><AdminLive.DashboardPage/></AdminGate>}/>
          <Route path="students" element={demoMode ? <StudentsPage/> : <AdminGate capability="view_student_records"><AdminLive.StudentsPage/></AdminGate>}/>
          <Route path="students/:id" element={demoMode ? <StudentDetail/> : <AdminGate capability="view_student_records"><AdminLive.StudentDetail/></AdminGate>}/>
          <Route path="students/:id/passport" element={demoMode ? <AdminPassportPage/> : <AdminGate capability="view_student_records"><LiveAdminPassport/></AdminGate>}/>
          <Route path="passports/preview" element={demoMode ? <AdminPassportPage/> : <AdminGate capability="view_student_records"><LiveAdminPassport/></AdminGate>}/>
          <Route path="skills" element={demoMode ? <CatalogPage/> : <AdminGate capability="view_student_records"><AdminLive.CatalogPage/></AdminGate>}/>
          <Route path="course-mappings" element={demoMode ? <MappingsPage/> : <AdminGate capability="view_student_records"><AdminLive.MappingsPage/></AdminGate>}/>
          <Route path="courses" element={<LegacyRedirect to="/admin/course-mappings"/>}/>
          <Route path="credentials" element={demoMode ? <CredentialsPage/> : <AdminGate capability="view_student_records"><AdminLive.CredentialsPage/></AdminGate>}/>
          <Route path="credentials/:id" element={demoMode ? <CredentialDetail/> : <AdminGate capability="view_student_records"><AdminLive.CredentialDetail/></AdminGate>}/>
          <Route path="classroom-sync" element={demoMode ? <SynchronizationPage/> : <AdminGate capability="sync_classroom"><LiveAdminSync/></AdminGate>}/>
          <Route path="sync" element={<LegacyRedirect to="/admin/classroom-sync"/>}/>
          <Route path="imports" element={demoMode ? <ImportsPage/> : <AdminGate capability="import_completions"><LiveAdminImports/></AdminGate>}/>
          <Route path="audit-logs" element={demoMode ? <AuditPage/> : <AdminGate capability="view_student_records"><AdminLive.AuditPage/></AdminGate>}/>
          <Route path="audit" element={<LegacyRedirect to="/admin/audit-logs"/>}/>
          <Route path="*" element={<NotFound/>}/>
        </Route>
      </Route>
      </Route>
    </Route>
    <Route path="verify" element={<VerificationLayout/>}>
      <Route index element={<VerificationLanding/>}/>
      <Route path="reference" element={<ReferenceVerificationPage/>}/>
      <Route path="upload" element={<PdfVerification/>}/>
      <Route path="result" element={<VerificationResults/>}/>
      <Route path="qr" element={<QrVerification/>}/>
      <Route path="qr/:reference" element={<QrVerification/>}/>
      <Route path="*" element={<VerificationNotFound/>}/>
    </Route>
    <Route path="/" element={<LegacyRedirect to="/student/dashboard"/>}/>
    {['skills', 'credentials', 'passport', 'profile', 'gap-analyzer', 'game'].map(path => <Route key={path} path={path} element={<LegacyRedirect to={`/student/${path}`}/>}/>)}
    <Route path="*" element={<NotFound/>}/>
  </Routes>
}
export default function App() {
  return <QueryClientProvider client={client}><LocaleProvider><BrowserRouter><DemoBanner/><div className={demoMode ? 'demo-preview-content' : undefined}><AppRoutes/></div></BrowserRouter></LocaleProvider></QueryClientProvider>
}
