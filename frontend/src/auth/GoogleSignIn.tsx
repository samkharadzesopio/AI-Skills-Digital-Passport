import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { api, resetCsrfToken } from '../services/api'
import { demoMode } from '../demo/mode'
import { restoreSession } from './hooks'
import { parseAccountSummary } from './contracts'
import { LogoutButton } from './SessionPanel'

type GIS = { initialize(options: { client_id: string; nonce: string; hd: string; ux_mode: 'popup'; auto_select: false; callback(response: { credential?: string }): void }): void
  renderButton(element: HTMLElement, options: { type: string; text: string; theme: string; size: string }): void
  disableAutoSelect(): void }
declare global { interface Window { google?: { accounts: { id: GIS } } } }
const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '').trim()
const googleConfigured = /^[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId)
let loading: Promise<GIS> | undefined
function loadGoogle(): Promise<GIS> {
  if (window.google?.accounts.id) return Promise.resolve(window.google.accounts.id)
  if (loading) return loading
  loading = new Promise<GIS>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'; script.async = true; script.defer = true
    const timer = setTimeout(() => { script.remove(); loading = undefined; reject(new Error('Google unavailable')) }, 15000)
    script.onload = () => { clearTimeout(timer); const gis = window.google?.accounts.id; if (gis) resolve(gis); else { loading = undefined; reject(new Error('Google unavailable')) } }
    script.onerror = () => { clearTimeout(timer); script.remove(); loading = undefined; reject(new Error('Google unavailable')) }
    document.head.append(script)
  })
  return loading
}
const messages: Record<string, string> = {
  GOOGLE_LINK_REQUIRED: 'This Google account is not linked. Sign in with your university email code first, then open Google sign-in settings to link it.',
  GOOGLE_FRESH_OTP_REQUIRED: 'Linking requires a university email-code login within the last five minutes. Sign out, use an email code, then return here.',
  GOOGLE_STUDENT_REQUIRED: 'Access requires an active, institutionally provisioned student account. Contact university support if your record needs correction.',
  GOOGLE_INVALID_TOKEN: 'Google identity could not be verified. Use a verified @btu.edu.ge Workspace account and try again. Accounts without hd=btu.edu.ge are not accepted.',
  GOOGLE_IDENTITY_CONFLICT: 'This Google identity or student account is already linked differently. Contact university support; it cannot be reassigned here.',
  GOOGLE_INVALID_CHALLENGE: 'This sign-in attempt expired or was already used. Start a new attempt.',
  GOOGLE_NOT_CONFIGURED: 'Google sign-in is not configured on the university server. Email-code login remains available.',
  GOOGLE_SIGN_OUT_REQUIRED: 'Sign out of the current account before using Google to sign in.',
  GOOGLE_RATE_LIMITED: 'Too many Google sign-in attempts. Wait fifteen minutes before trying again.',
  GOOGLE_UNAVAILABLE: 'Google verification is temporarily unavailable. Try again or use your university email code.',
}
export function GoogleSignIn({ intent = 'login' }: { intent?: 'login' | 'link' }) {
  const target = useRef<HTMLDivElement>(null), mounted = useRef(true), busyRef = useRef(false)
  const [busy, setBusy] = useState(false), [ready, setReady] = useState(false), [error, setError] = useState(''), [linked, setLinked] = useState(false)
  const client = useQueryClient(), navigate = useNavigate()
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  function failure(cause: unknown) {
    const code: unknown = axios.isAxiosError(cause) ? cause.response?.data?.code : undefined
    setError(typeof code === 'string' && Object.hasOwn(messages, code) ? messages[code] : 'Google sign-in could not be completed. Start a new attempt or use your university email code.')
    target.current?.replaceChildren(); setReady(false)
  }
  async function prepare() {
    if (demoMode || !googleConfigured || busyRef.current) return
    busyRef.current = true; setBusy(true); setError('')
    target.current?.replaceChildren(); setReady(false)
    try {
      const response = await api.post('accounts/google/challenge/', { intent })
      const data = response.data
      if (typeof data?.challenge_id !== 'string' || typeof data?.nonce !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(data.nonce)) throw new Error('Invalid challenge')
      const gis = await loadGoogle()
      if (!mounted.current || !target.current) return
      let used = false
      gis.initialize({ client_id: clientId, nonce: data.nonce, hd: 'btu.edu.ge', ux_mode: 'popup', auto_select: false,
        callback: response => {
          if (used || !mounted.current) return
          used = true; busyRef.current = true; setBusy(true)
          target.current?.replaceChildren()
          void (async () => {
            try {
              if (!response.credential) throw new Error('Missing credential')
              const result = await api.post('accounts/google/authenticate/', { challenge_id: data.challenge_id, credential: response.credential })
              const account = parseAccountSummary(result.data?.account)
              if (account.role !== 'STUDENT' || !account.email_verified || account.student_association !== 'linked' || result.data?.linked !== (intent === 'link')) throw new Error('Invalid account')
              resetCsrfToken()
              if (!mounted.current) return
              if (intent === 'link') { setLinked(true); setReady(false) }
              else { const session = await restoreSession(client); if (session.status !== 'authenticated' || session.user.role !== 'STUDENT') throw new Error('Invalid session'); navigate('/student/dashboard', { replace: true }) }
            } catch (cause) { if (mounted.current) failure(cause) }
            finally { busyRef.current = false; if (mounted.current) setBusy(false) }
          })()
        } })
      gis.renderButton(target.current, { type: 'standard', text: 'continue_with', theme: 'outline', size: 'large' })
      setReady(true)
    } catch (cause) { if (mounted.current) failure(cause) }
    finally { busyRef.current = false; if (mounted.current) setBusy(false) }
  }
  if (demoMode) return null
  return <section aria-label={intent === 'link' ? 'Link Google account' : 'Google sign-in'} className="auth-secondary-actions">
    {linked ? <p role="status">Google account linked. You can use Google for future student sign-ins.</p> : <>
      {!ready && <button type="button" className="button" disabled={busy || !googleConfigured} onClick={() => void prepare()}>{busy ? 'Preparing Google sign-in…' : intent === 'link' ? 'Link Google account' : 'Continue with Google'}</button>}
      <div ref={target} aria-busy={busy}/>
      {ready && <><p>Use the Google button to open secure sign-in.</p><button type="button" className="button" disabled={busy} onClick={() => void prepare()}>Start a new Google attempt</button></>}
    </>}
    {!googleConfigured && <p>Google sign-in awaits local Client ID configuration. Email-code login remains available.</p>}
    {error && <p role="alert" className="error">{error}</p>}
  </section>
}
export function GoogleLinkPage() {
  return <><h1>Google sign-in settings</h1><p>Link Google only after signing in with your university email code within the last five minutes. Use the same provisioned @btu.edu.ge Workspace identity. This does not change your academic record or permissions.</p><GoogleSignIn intent="link"/><Link to="/student/dashboard">Return to Passport</Link><LogoutButton role="student"/></>
}
