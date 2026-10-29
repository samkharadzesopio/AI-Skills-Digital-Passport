import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { api, resetCsrfToken } from '../services/api'
import { restoreSession } from './hooks'
import { parseAccountSummary } from './contracts'
import { loadGoogle } from './googleIdentity'

type Challenge = { challenge_id: string; nonce: string }
const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '').trim()
const configured = /^[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId)

export function WorkspaceSignIn() {
  const [ready, setReady] = useState(false), [busy, setBusy] = useState(false), [preparing, setPreparing] = useState(true), [error, setError] = useState(''), [generation, setGeneration] = useState(0)
  const target = useRef<HTMLDivElement>(null)
  const mounted = useRef(true), inFlight = useRef(false), client = useQueryClient(), navigate = useNavigate()
  const preparation = useRef<{ generation: number; request: Promise<Challenge> } | null>(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const signIn = useCallback(async (credential: unknown, challenge: Challenge) => {
    if (inFlight.current) return
    inFlight.current = true; setBusy(true); setError('')
    try {
      // GIS documents response.credential as the JWT; native FedCM token is opaque.
      // This is only a transport shape check. Django performs all token validation.
      if (typeof credential !== 'string' || credential.length > 16384 || !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(credential)) throw new Error('Invalid Google credential format')
      const response = await api.post('accounts/google/authenticate/', { challenge_id: challenge.challenge_id, credential })
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
      setPreparing(true); setReady(false); setGeneration(n => n + 1)
    } finally { inFlight.current = false; if (mounted.current) setBusy(false) }
  }, [client, navigate])
  useEffect(() => {
    if (!configured) return
    let active = true
    const container = target.current
    if (!preparation.current || preparation.current.generation !== generation) {
      preparation.current = { generation, request: api.post('accounts/google/challenge/', { intent: 'login' }).then(response => {
        const value = response.data
        if (typeof value?.challenge_id !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(value?.nonce ?? '')) throw new Error('Invalid challenge')
        return { challenge_id: value.challenge_id, nonce: value.nonce }
      }) }
    }
    void Promise.all([preparation.current.request, loadGoogle()]).then(([value, gis]) => {
      if (!active || !container) return
      let used = false
      gis.initialize({ client_id: clientId, nonce: value.nonce, hd: 'btu.edu.ge', ux_mode: 'popup', auto_select: false, use_fedcm_for_button: true,
        callback: response => {
          if (!active || used || inFlight.current) return
          used = true
          container.replaceChildren(); setReady(false)
          void signIn(response.credential, value)
        } })
      gis.renderButton(container, { type: 'standard', text: 'signin_with', theme: 'outline', size: 'large' })
      setReady(true); setPreparing(false)
    }).catch(() => { if (active) { setPreparing(false); setError('Sign-in preparation is unavailable. Try again shortly.') } })
    const timer = setTimeout(() => { if (active && !inFlight.current) { setPreparing(true); setReady(false); setGeneration(n => n + 1) } }, 240000)
    return () => { active = false; clearTimeout(timer); container?.replaceChildren() }
  }, [generation, signIn])
  return <><div ref={target} hidden={!ready} aria-label="Google student sign-in" aria-busy={busy || preparing}/>
    {!ready && !busy && <button type="button" className="button primary auth-submit" style={{ width: '100%' }} disabled={!configured || preparing} aria-busy={configured && preparing} onClick={() => { setPreparing(true); setError(''); setGeneration(n => n + 1) }}>Sign in</button>}
    {busy && <p role="status" className="auth-hint">Completing Google sign-in…</p>}
    {!configured && <p role="status" className="auth-hint">Google sign-in is awaiting university configuration.</p>}
    {error && <p className="error" role="alert">{error}</p>}</>
}
