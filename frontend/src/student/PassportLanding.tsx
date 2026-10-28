import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PassportCard } from '../components/PassportCard'
import { backendPassportCard } from '../components/passport-card-data'
import type { Dashboard } from './contracts'
import { PdfActions } from './PdfActions'
import { passportState } from './proof'
import { verificationLink } from '../verification/validation'
import { Card, EmptyState } from '../components/ui'

export function PassportLanding({ data }: { data: Dashboard }) {
  const [sharing, setSharing] = useState(false), [message, setMessage] = useState('')
  const passport = data.passport
  if (!passport?.latest_version) return <Card><EmptyState title="No issued Passport yet">Your Passport will appear after eligible credentials are issued.</EmptyState><Link className="button" to="/student/passport/versions">View History</Link></Card>
  const state = passportState(passport)
  const share = new URL(verificationLink('passport', passport.public_reference), window.location.origin).href
  async function showShare() {
    if (!state.currentValid) return
    setSharing(true)
    try { await navigator.clipboard.writeText(share); setMessage('Passport verification link copied.') }
    catch { setMessage('Copy the public verification link below.') }
  }
  return <section className="dashboard-passport" aria-label="Your Digital Passport">
    <h1 className="sr-only">My Passport</h1>
    <PassportCard data={{ ...backendPassportCard(passport, data.profile), status: state.label }} compact/>
    <div className="dashboard-passport-actions">
      <PdfActions compact key={passport.latest_version.id}/>
      <button className="button" disabled={!state.currentValid} onClick={() => void showShare()}>Share Passport</button>
      <Link className="button" to="/student/passport/versions">View History</Link>
    </div>
    {!state.currentValid && <p className="muted" role="status">{state.label}. Sharing requires a confirmed current Passport.</p>}
    {sharing && state.currentValid && <div className="dashboard-share-link"><label htmlFor="passport-share">Public verification link</label><input id="passport-share" value={share} readOnly/><p role="status">{message}</p><Link to={verificationLink('passport', passport.public_reference)}>Verify Passport</Link></div>}
    <details className="passport-record-details"><summary>Read-only Student identity and record details</summary><p>{data.profile.first_name} {data.profile.last_name} · {data.profile.email}</p><p>{data.profile.program} · {data.profile.external_student_id}</p><p role="status">{state.label}</p><p>PDF issuance alone does not establish blockchain authenticity.</p><Link to="/student/profile">View university-maintained identity</Link></details>
  </section>
}
