import { OfficialBtuLogo } from '../components/PassportCard'
import { Link, Outlet } from 'react-router-dom'
import { Globe2, ShieldCheck } from 'lucide-react'
import { useLocale } from '../i18n'
import { VerificationProvider } from '../verification/state'
import { useVerificationText } from '../verification/i18n'
import '../verification/verification.css'
import './public-navigation.css'
export function VerificationLayout() {
  const { locale, toggle } = useLocale(), t = useVerificationText()
  return <VerificationProvider><div className="verification-layout"><a className="skip" href="#verification-main">{t('skip')}</a><header><Link className="verify-brand" to="/verify"><OfficialBtuLogo/><span>AI SKILLS<br/>DIGITAL PASSPORT</span></Link><span className="verify-header-caption"><ShieldCheck size={16}/>{t('trust')}</span><button className="button" onClick={toggle} aria-label="English / ქართული"><Globe2 size={16}/>{locale.toUpperCase()}</button></header><nav className="public-workspaces" aria-label="Passport workspaces"><Link className="button" to="/student/dashboard">Student Dashboard</Link><Link className="button" to="/admin/dashboard">Admin Dashboard</Link><Link className="button primary" to="/verify">Verify Passport</Link></nav><main id="verification-main"><Outlet/></main><footer><span>BTU · {t('officialOnly')}</span><p>{t('privacy')}</p></footer></div></VerificationProvider>
}
