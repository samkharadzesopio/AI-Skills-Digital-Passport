import { History } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PassportCard } from '../components/PassportCard'
import type { Profile } from './contracts'

/** A personal preview only: no issuance, PDF lookup, proof, or sample records. */
export function BlankPassport({ profile, hasRecords = false }: { profile?: Pick<Profile, 'first_name' | 'last_name'>; hasRecords?: boolean }) {
  return <section className="dashboard-passport blank-passport" aria-label="Your Digital Passport preview">
    <div className="passport-page-heading"><div><p className="student-eyebrow">YOUR LEARNING JOURNEY</p><h1>My Passport</h1></div><span className="student-status-pill">Not issued</span></div>
    <PassportCard compact data={{ unissued: true, demonstration: false, firstName: profile?.first_name ?? '', lastName: profile?.last_name ?? '', issuer: null, reference: null, issuedOn: null, status: 'Not issued', skills: [] }}/>
    <div className="blank-passport-message" role="status"><h2>{hasRecords ? 'Your passport has not been issued yet' : 'No academic records linked yet'}</h2><p>{hasRecords ? 'Your approved achievements will appear in your passport once BTU issues it.' : 'Your passport is ready for future achievements. Verified skills and awards will appear here once approved by BTU.'}</p></div>
    <div className="dashboard-passport-actions"><button className="button primary" disabled>Download PDF</button><button className="button" disabled>Share Passport</button><Link className="button" to="/student/passport/versions"><History size={16} aria-hidden="true"/>View History</Link></div>
  </section>
}
