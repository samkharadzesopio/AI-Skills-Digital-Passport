import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { Gamepad2 } from 'lucide-react'
import { LocaleProvider } from './i18n'
import { AccessBoundary } from './auth/AccessBoundary'
import { StudentLayout } from './layouts/StudentLayout'
import { AdminLayout } from './layouts/AdminLayout'
import { VerificationLayout } from './layouts/VerificationLayout'
import { Dashboard, Detail, Profile, Gap } from './pages'
import { VerificationLanding, ReferenceVerification, PdfVerification, VerificationResults, QrVerification, VerificationNotFound } from './verification/pages'
import { AdminWorkspace } from './admin/store'
import { AdminDashboard, StudentsPage, StudentDetail, CredentialsPage, CredentialDetail, SynchronizationPage, AuditPage } from './admin/pages'
import { CatalogPage } from './admin/CatalogPage'
import { MappingsPage } from './admin/MappingsPage'
import { ImportsPage } from './admin/ImportsPage'
import { AdminPassportPage } from './admin/PassportPage'
import { Card, EmptyState, Loading } from './components/ui'
import { getDemoStudent } from './data/mock'
import './App.css'
import './artwork-theme.css'
import { DemoBanner } from './demo/DemoBanner'
import { demoMode } from './demo/mode'
import { LoginPage } from './auth/LoginPages'
import { ProductWorkspace } from './live/ProductWorkspace'
const client = new QueryClient()
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
      {!demoMode ? <Route path="*" element={<ProductWorkspace role="student"/>}/> : <Route element={<StudentLayout/>}>
        <Route element={<DemoStudentDataBoundary/>}>
          <Route path="dashboard" element={<Dashboard/>}/>
          <Route path="skills" element={<Detail page="AI skills & competencies"/>}/>
          <Route path="credentials" element={<Detail page="Verified credentials"/>}/>
          <Route path="passport" element={<Detail page="Digital passport preview"/>}/>
          <Route path="profile" element={<Profile/>}/>
          <Route path="gap-analyzer" element={<Gap/>}/>
          <Route path="game" element={<Card><EmptyState title="AI playground coming soon">A future Dino-style game is planned for online and offline play.</EmptyState><Gamepad2 className="game-icon" size={64}/></Card>}/>
          <Route path="*" element={<NotFound/>}/>
        </Route>
      </Route>}
      </Route>
    </Route>
    <Route path="admin">
      <Route path="login" element={<LoginPage kind="administrator"/>}/>
      <Route element={<AccessBoundary role="administrator"/>}>
      <Route index element={<LegacyRedirect to="/admin/dashboard"/>}/>
      {!demoMode ? <><Route path="students/:id/*" element={<ProductWorkspace role="administrator"/>}/><Route path="*" element={<ProductWorkspace role="administrator"/>}/></> : <Route element={<AdminWorkspace/>}>
        <Route element={<AdminLayout/>}>
          <Route path="dashboard" element={<AdminDashboard/>}/>
          <Route path="students" element={<StudentsPage/>}/>
          <Route path="students/:id" element={<StudentDetail/>}/>
          <Route path="students/:id/passport" element={<AdminPassportPage/>}/>
          <Route path="passports/preview" element={<AdminPassportPage/>}/>
          <Route path="skills" element={<CatalogPage/>}/>
          <Route path="course-mappings" element={<MappingsPage/>}/>
          <Route path="courses" element={<LegacyRedirect to="/admin/course-mappings"/>}/>
          <Route path="credentials" element={<CredentialsPage/>}/>
          <Route path="credentials/:id" element={<CredentialDetail/>}/>
          <Route path="classroom-sync" element={<SynchronizationPage/>}/>
          <Route path="sync" element={<LegacyRedirect to="/admin/classroom-sync"/>}/>
          <Route path="imports" element={<ImportsPage/>}/>
          <Route path="audit-logs" element={<AuditPage/>}/>
          <Route path="audit" element={<LegacyRedirect to="/admin/audit-logs"/>}/>
          <Route path="*" element={<NotFound/>}/>
        </Route>
      </Route>}
      </Route>
    </Route>
    <Route path="verify" element={<VerificationLayout/>}>
      <Route index element={<VerificationLanding/>}/>
      <Route path="reference" element={<ReferenceVerification/>}/>
      <Route path="upload" element={<PdfVerification/>}/>
      <Route path="result" element={<VerificationResults/>}/>
      <Route path="qr" element={<QrVerification/>}/>
      <Route path="qr/:reference" element={<QrVerification/>}/>
      <Route path="*" element={<VerificationNotFound/>}/>
    </Route>
    <Route path="/" element={<LegacyRedirect to="/verify"/>}/>
    {['skills', 'credentials', 'passport', 'profile', 'gap-analyzer', 'game'].map(path => <Route key={path} path={path} element={<LegacyRedirect to={`/student/${path}`}/>}/>)}
    <Route path="*" element={<NotFound/>}/>
  </Routes>
}
export default function App() {
  return <QueryClientProvider client={client}><LocaleProvider><BrowserRouter><DemoBanner/><div className={demoMode ? 'demo-preview-content' : undefined}><AppRoutes/></div></BrowserRouter></LocaleProvider></QueryClientProvider>
}
