import { useQuery } from '@tanstack/react-query'
import { Outlet } from 'react-router-dom'
import { getSession } from '../services/session'
import { Card, EmptyState, Loading } from '../components/ui'
import { demoMode } from '../demo/mode'

export function AccessBoundary({ role }: { role: 'student' | 'administrator' }) {
  // Mount no session hook or real authentication code while previewing mock workspaces.
  if (demoMode) return <Outlet/>
  return <AuthenticatedBoundary role={role}/>
}
function AuthenticatedBoundary({ role }: { role: 'student' | 'administrator' }) {
  const session = useQuery({ queryKey: ['session'], queryFn: getSession, retry: false })
  if (session.isPending) return <Loading/>
  if (session.isError) return <Card><EmptyState title="Unable to check access">Try again when the university authentication service is available.</EmptyState><button className="button" onClick={() => session.refetch()}>Retry</button></Card>
  if (session.data?.status === 'authenticated' && session.data.roles.includes(role)) return <Outlet/>
  return <Card><EmptyState title={session.data?.status === 'unavailable' ? 'Authentication integration pending' : 'Access required'}>
    {role === 'administrator' ? 'Explicit administrator permission from Django is required.' : 'Authenticated student access from Django is required.'} No protected data has been loaded.
  </EmptyState></Card>
}
