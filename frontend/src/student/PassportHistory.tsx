import { ArrowLeft, ArrowUpRight, CalendarDays, FileClock, History } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card } from '../components/ui'
import type { ReactNode } from 'react'
import type { Version } from './contracts'

export function PassportHistory({ versions, currentVersionId, pagination }: { versions: Version[]; currentVersionId?: string; pagination?: ReactNode }) {
  return <section className="passport-history" aria-labelledby="passport-history-heading">
    <div className="student-page-heading"><div><p className="student-eyebrow">YOUR PASSPORT JOURNEY</p><h1 id="passport-history-heading">Passport Version History</h1></div><Link className="button" to="/student/dashboard"><ArrowLeft size={16} aria-hidden="true"/>My Passport</Link></div>
    <Card className="passport-history-card">
      {versions.length ? <><div className="passport-history-intro"><span className="student-heading-icon"><History size={21} aria-hidden="true"/></span><div><h2>Your published versions</h2><p>Explore the university-issued snapshots of your learning journey.</p></div></div>
        <ol className="passport-version-list">{versions.map(version => {
          const current = version.id === currentVersionId
          const issued = new Date(version.issued_at)
          return <li key={version.id} className={current ? 'passport-version is-current' : 'passport-version'}>
            <span className="passport-version-marker" aria-hidden="true"><FileClock size={20}/></span>
            <div className="passport-version-content"><div className="passport-version-title"><Link to={`/student/passport/versions/${version.id}`}>Version {version.version_number}</Link>{current && <span className="student-status-pill">Current version</span>}</div>
              <p className="passport-version-date"><CalendarDays size={14} aria-hidden="true"/>Issued <time dateTime={version.issued_at}>{Number.isNaN(issued.getTime()) ? version.issued_at : issued.toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'}</time><span className="passport-snapshot-status">Snapshot: {version.status}</span></p>
              <p className="passport-version-reference">Reference <code>{version.public_reference}</code></p>
            </div><Link className="passport-version-open" to={`/student/passport/versions/${version.id}`} aria-label={`View version ${version.version_number}`}><ArrowUpRight size={20}/></Link>
          </li>
        })}</ol></> : <div className="passport-history-empty"><span className="student-empty-icon"><History size={30} aria-hidden="true"/></span><h2>No passport history yet</h2><p>Your published passport versions will appear here once BTU issues your passport.</p><Link className="button" to="/student/dashboard">Back to My Passport<ArrowUpRight size={16} aria-hidden="true"/></Link></div>}
      {pagination}
    </Card>
  </section>
}
