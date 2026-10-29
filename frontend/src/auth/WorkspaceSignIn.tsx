import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { api, resetCsrfToken } from '../services/api'
import { restoreSession } from './hooks'
import { parseAccountSummary } from './contracts'

type Challenge = { challenge_id: string; nonce: string }
const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '').trim()
const configured = /^[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId)

export function WorkspaceSignIn() {
  const [challenge, setChallenge] = useState<Challenge | null>(null), [busy, setBusy] = useState(false), [preparing, setPreparing] = useState(true), [error, setError] = useState(''), [generation, setGeneration] = useState(0)
  const mounted = useRef(true), inFlight = useRef(false), client = useQueryClient(), navigate = useNavigate()
  const preparation = useRef<{ generation: number; request: Promise<Challenge> } | null>(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    if (!configured) return
    let active = true
    if (!preparation.current || preparation.current.generation !== generation) {
      preparation.current = { generation, request: api.post('accounts/google/challenge/', { intent: 'login' }).then(response => {
        const value = response.data
        if (typeof value?.challenge_id !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(value?.nonce ?? '')) throw new Error('Invalid challenge')
        return { challenge_id: value.challenge_id, nonce: value.nonce }
      }) }
    }
    void preparation.current.request.then(value => {
      if (active) { setChallenge(value); setPreparing(false) }
    }).catch(() => { if (active) { setPreparing(false); setError('Sign-in preparation is unavailable. Try again shortly.') } })
    // Prepare the nonce before the click so the browser keeps the user gesture.
    const timer = setTimeout(() => { if (active) { setPreparing(true); setChallenge(null); setGeneration(n => n + 1) } }, 240000)
    return () => { active = false; clearTimeout(timer) }
  }, [generation])
  async function signIn() {
    if (inFlight.current || !challenge) { if (!busy) { setPreparing(true); setError(''); setGeneration(n => n + 1) } return }
    if (!('IdentityCredential' in window) || !navigator.credentials?.get) {
      setError('Google account selection requires a current browser with FedCM support, such as Chrome or Edge.'); return
    }
    inFlight.current = true; setBusy(true); setError('')
    try {
      const credential = await navigator.credentials.get({
        identity: { mode: 'active', context: 'signin', providers: [{
          configURL: 'https://accounts.google.com/gsi/fedcm.json', clientId,
          domainHint: 'btu.edu.ge', nonce: challenge.nonce,
          // Google requires the ID-token parameters supplied by its GIS SDK, even with native FedCM.
          params: { nonce: challenge.nonce, response_type: 'id_token', scope: 'email profile openid', ss_domain: window.location.origin },
        }] }, mediation: 'required',
      } as CredentialRequestOptions) as (Credential & { token?: string }) | null
      if (!credential?.token) throw new Error('Google sign-in cancelled')
      const response = await api.post('accounts/google/authenticate/', { challenge_id: challenge.challenge_id, credential: credential.token })
      const account = parseAccountSummary(response.data?.account)
      if (account.role !== 'STUDENT' || !account.email_verified || !account.portal_access) throw new Error('Invalid portal session')
      resetCsrfToken()
      const restored = await restoreSession(client)
      if (restored.status !== 'authenticated' || restored.user.role !== 'STUDENT' || !restored.user.portal_access) throw new Error('Invalid portal session')
      if (mounted.current) navigate('/student/dashboard', { replace: true })
    } catch (cause) {
      if (!mounted.current) return
      const code: unknown = axios.isAxiosError(cause) ? cause.response?.data?.code : undefined
      setError(code === 'GOOGLE_INVALID_TOKEN' ? 'Use a verified @btu.edu.ge Google Workspace account.'
        : code === 'GOOGLE_IDENTITY_CONFLICT' ? 'This identity needs university support before access can be restored.'
          : code === 'GOOGLE_RATE_LIMITED' ? 'Too many attempts. Please wait before trying again.'
            : 'Google sign-in was cancelled or could not be completed. Please try again.')
      setPreparing(true); setChallenge(null); setGeneration(n => n + 1)
    } finally { inFlight.current = false; if (mounted.current) setBusy(false) }
  }
  return <><button type="button" className="button primary auth-submit" style={{ width: '100%' }} disabled={busy || !configured || preparing} aria-busy={busy || (configured && preparing)} onClick={() => void signIn()}>Sign in</button>
    {!configured && <p role="status" className="auth-hint">Google sign-in is awaiting university configuration.</p>}
    {error && <p className="error" role="alert">{error}</p>}</>
}
