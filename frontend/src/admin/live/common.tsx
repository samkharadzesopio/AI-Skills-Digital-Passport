import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSession } from '../../auth/hooks'
import type { AdminCapability } from '../../auth/contracts'
import { Card, EmptyState, Loading } from '../../components/ui'
import { AdminError } from './service'
import type { Page } from '../../student/contracts'
import type { CursorPage } from './contracts'

// Every page is gated; every endpoint independently checks the actual grant.
// eslint-disable-next-line react-refresh/only-export-components
export function useCapabilities() { const q = useSession(); return q.data?.status === 'authenticated' && q.data.user.role === 'ADMIN' ? q.data.user.capabilities ?? [] : [] }
export function Gate({ capability, children }: { capability: AdminCapability; children: ReactNode }) { const grants = useCapabilities(); return grants.includes(capability) ? <>{children}</> : <Card><h1>Permission required</h1><p role="alert">This page requires {capability}. Contact an authorized university administrator.</p></Card> }
// eslint-disable-next-line react-refresh/only-export-components
export function useAdminQuery<T>(key: readonly unknown[], fetcher: (s: AbortSignal) => Promise<T>) {
  const session = useSession(), client = useQueryClient(), owner = session.data?.status === 'authenticated' ? session.data.user.email : null
  const query = useQuery({ queryKey: ['admin-live', owner, ...key], queryFn: ({ signal }) => fetcher(signal), enabled: !!owner, retry: false, staleTime: 0, gcTime: 0 })
  useEffect(() => { if (query.error instanceof AdminError && [401, 403].includes(query.error.status)) void client.invalidateQueries({ queryKey: ['session'] }) }, [query.error, client])
  return query
}
export function Result<T>({ query, children }: { query: { isPending: boolean; isError: boolean; error: Error | null; data: T | undefined; refetch: () => unknown }; children: (data: T) => ReactNode }) {
  if (query.isPending) return <Loading/>
  if (query.isError || query.data === undefined) return <QueryFailure error={query.error} refetch={query.refetch}/>
  return <>{children(query.data)}</>
}
function QueryFailure({ error, refetch }: { error: Error | null; refetch: () => unknown }) {
  const [now, setNow] = useState(Date.now), until = error instanceof AdminError ? error.retryAt : 0
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer) }, [])
  return <Card><h2>Records unavailable</h2><p role="alert">{error?.message ?? 'The response could not be read.'}</p><button className="button" disabled={now < until} onClick={() => { if (Date.now() >= until) void refetch() }}>Retry records</button></Card>
}
export function Pagination({ page, data, change }: { page: number; data: Page<unknown>; change: (n: number) => void }) { return <nav className="admin-pagination" aria-label="Record pages"><span>{data.count} records · Page {page}</span><button className="button" disabled={!data.hasPrevious} onClick={() => change(page - 1)}>Previous</button><button className="button" disabled={!data.hasNext} onClick={() => change(page + 1)}>Next</button></nav> }
export function CursorNavigation({ data, change }: { data: CursorPage<unknown>; change: (v: string | null) => void }) { return <nav className="admin-pagination" aria-label="History pages"><button className="button" disabled={!data.previous} onClick={() => change(data.previous)}>Previous history</button><button className="button" disabled={!data.next} onClick={() => change(data.next)}>Next history</button></nav> }
export function Empty({ label }: { label: string }) { return <EmptyState title={`No ${label}`}>Persisted university records will appear here.</EmptyState> }
export function Facts({ values }: { values: Record<string, string | number> }) { return <dl className="student-details">{Object.entries(values).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl> }
export function Action({ label, perform, children, onSuccess, disabled = false, confirm = true }: { label: string; perform: (signal: AbortSignal) => Promise<unknown>; children?: ReactNode; onSuccess?: (value: unknown) => void; disabled?: boolean; confirm?: boolean }) {
  const client = useQueryClient(), [review, setReview] = useState(false), [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [until, setUntil] = useState(0), [now, setNow] = useState(Date.now), controller = useRef<AbortController | null>(null), inFlight = useRef(false)
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => { clearInterval(timer); controller.current?.abort() } }, [])
  async function run() {
    if (inFlight.current || disabled || Date.now() < until) return
    inFlight.current = true; setBusy(true); setMessage(''); const c = new AbortController(); controller.current = c
    try { const value = await perform(c.signal); if (c.signal.aborted) return; onSuccess?.(value); setReview(false); setMessage(`${label} completed.`); void client.invalidateQueries({ predicate: q => q.queryKey[0] === 'admin-live' || q.queryKey[0] === 'student' }) }
    catch (e) { if (c.signal.aborted) return; setMessage(e instanceof AdminError ? e.message : 'Operation failed. Check current records before retrying.'); if (e instanceof AdminError) { setUntil(Date.now() + Math.max(e.retryAfter, e.status === 409 ? 2 : 0) * 1000); if ([401,403].includes(e.status)) void client.invalidateQueries({ queryKey: ['session'] }) } }
    finally { inFlight.current = false; if (!c.signal.aborted) setBusy(false) }
  }
  const waiting = now < until
  return <section className="admin-action"><button className="button primary" disabled={disabled || busy || waiting} onClick={() => confirm ? setReview(true) : void run()}>{busy ? 'Processing…' : label}</button>{review && <div role="group" aria-label={`Confirm ${label}`}><h3>Confirm {label}</h3>{children}<p>This changes persisted university records. Review the selected evidence and action.</p><button className="button" disabled={busy} onClick={() => setReview(false)}>Cancel</button><button className="button primary" disabled={disabled || busy || waiting} onClick={() => void run()}>Confirm {label}</button></div>}{message && <p role="status">{message}</p>}{waiting && <p role="status">Retry in {Math.max(0, Math.ceil((until - now) / 1000))} seconds.</p>}</section>
}
