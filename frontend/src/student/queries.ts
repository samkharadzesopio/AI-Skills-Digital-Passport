import { useQuery } from '@tanstack/react-query'
import { useSession } from '../auth/hooks'
export function useStudentQuery<T>(key: readonly unknown[], fetcher: (signal: AbortSignal) => Promise<T>) {
  const session = useSession()
  const owner = session.data?.status === 'authenticated' ? session.data.user.email : null
  return useQuery({ queryKey: ['student', owner, ...key], queryFn: ({ signal }) => fetcher(signal), enabled: !!owner, retry: false, staleTime: 0, gcTime: 0 })
}
