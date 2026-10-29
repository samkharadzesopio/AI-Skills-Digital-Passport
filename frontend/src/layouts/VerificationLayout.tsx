import { OfficialBtuLogo } from '../components/PassportCard'
import { Link, Outlet } from 'react-router-dom'
import { Globe2, ShieldCheck } from 'lucide-react'
import { useLocale } from '../i18n'
import { VerificationProvider } from '../verification/state'
import { useVerificationText } from '../verification/i18n'
import { useAuthText } from '../auth/i18n'
import '../verification/verification.css'
export function VerificationLayout() {
  const { locale, toggle } = useLocale(), t = useVerificationText(), auth = useAuthText()
  return <VerificationProvider><div className="verification-layout"><a className="skip" href="#verification-main">{t('skip')}</a><header>
    <Link className="verify-brand" to="/verify"><OfficialBtuLogo/><span>AI SKILLS<br/>DIGITAL PASSPORT</span></Link>
    <span className="verify-header-caption"><ShieldCheck size={16}/>{t('trust')}</span>
    <div className="verify-header-actions">
      <nav className="verify-sign-in-nav" aria-label={auth('signIn')}>
        {/* A full navigation initializes the real API clients, even from a demo build. */}
        <a className="button verify-student-sign-in" href="/student/login?auth=live">{auth('student')}</a>
        <a className="button" href="/admin/login?auth=live">{auth('administrator')}</a>
      </nav>
      <button className="button verify-language" onClick={toggle} aria-label="English / ქართული"><Globe2 size={16}/>{locale.toUpperCase()}</button>
    </div>
  </header><main id="verification-main"><Outlet/></main><footer><span>BTU · {t('officialOnly')}</span><p>{t('privacy')}</p></footer></div></VerificationProvider>
}
