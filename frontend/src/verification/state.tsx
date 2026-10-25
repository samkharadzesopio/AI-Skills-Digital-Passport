import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'
import { useNavigate } from 'react-router-dom'
import type { VerificationOutcome } from './contracts'
import { failure } from './service'
interface State { outcome: VerificationOutcome | null; setOutcome: Dispatch<SetStateAction<VerificationOutcome | null>>; limitUntil: number; setLimitUntil: Dispatch<SetStateAction<number>> }
const Context = createContext<State | null>(null)
export function VerificationProvider({ children }: { children: ReactNode }) {
  const [outcome, setOutcome] = useState<VerificationOutcome | null>(null), [limitUntil, setLimitUntil] = useState(0)
  return <Context.Provider value={{ outcome, setOutcome, limitUntil, setLimitUntil }}>{children}</Context.Provider>
}
// eslint-disable-next-line react-refresh/only-export-components
export function useVerificationState() { const state = useContext(Context); if (!state) throw new Error('Verification provider required'); return state }
// eslint-disable-next-line react-refresh/only-export-components
export function useCooldown() {
  const { limitUntil } = useVerificationState(), [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const tick = () => setSeconds(Math.max(0, Math.ceil((limitUntil - Date.now()) / 1000)))
    const initial = setTimeout(tick, 0), timer = setInterval(tick, 1000)
    return () => { clearTimeout(initial); clearInterval(timer) }
  }, [limitUntil])
  return seconds
}
// eslint-disable-next-line react-refresh/only-export-components
export function useVerificationRequest() {
  const controller = useRef<AbortController | null>(null), { setOutcome, setLimitUntil, limitUntil } = useVerificationState(), navigate = useNavigate()
  const [pending, setPending] = useState(false), [progress, setProgress] = useState<number | null>(null), [canceled, setCanceled] = useState(false)
  useEffect(() => () => { controller.current?.abort(); controller.current = null }, [])
  async function run(request: (signal: AbortSignal, report: (n: number | null) => void) => Promise<VerificationOutcome>) {
    if (controller.current || limitUntil > Date.now()) return
    const current = new AbortController(); controller.current = current
    setOutcome(null); setCanceled(false); setPending(true); setProgress(null)
    try {
      const result = await request(current.signal, n => { if (!current.signal.aborted) setProgress(n) })
      if (current.signal.aborted) return
      if (result.kind === 'failure' && result.reason === 'rate_limit' && result.retryAt) setLimitUntil(previous => Math.max(previous, result.retryAt!))
      setOutcome(result); navigate('/verify/result')
    } catch {
      if (!current.signal.aborted) { setOutcome(failure('contract')); navigate('/verify/result') }
    } finally { if (controller.current === current) { controller.current = null; setPending(false) } }
  }
  function cancel() { controller.current?.abort(); controller.current = null; setPending(false); setProgress(null); setCanceled(true) }
  return { pending, progress, canceled, run, cancel }
}
