import { createContext, useContext } from 'react'
import { Outlet } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Card, EmptyState, Loading } from '../components/ui'
import { getAdminDemoData } from './mock'
import type { AdminData } from './contracts'
import { useAdminText } from './i18n'
const Context = createContext<{ data: AdminData; update: (fn: (current: AdminData) => AdminData) => void } | null>(null)
export function AdminWorkspace() {
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['admin', 'demo'], queryFn: getAdminDemoData, staleTime: Infinity })
  const t = useAdminText()
  if (query.isPending) return <div role="status"><Loading/>{t('loading')}</div>
  if (query.isError) return <Card><EmptyState title={t('loadError')}>{t('reload')}</EmptyState><button className="button" onClick={() => query.refetch()}>{t('reload')}</button></Card>
  return <Context.Provider value={{ data: query.data, update: fn => client.setQueryData<AdminData>(['admin', 'demo'], current => current ? fn(current) : current) }}><Outlet/></Context.Provider>
}
// eslint-disable-next-line react-refresh/only-export-components
export function useAdminData() {
  const value = useContext(Context)
  if (!value) throw new Error('Admin workspace provider is required')
  return value
}
