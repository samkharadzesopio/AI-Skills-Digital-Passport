import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { getSession } from '../services/session'
import type { Session } from './contracts'
export function useSession() {
  return useQuery({ queryKey:['session'], queryFn:({signal})=>getSession(signal), retry:false, staleTime:0, gcTime:0, refetchOnWindowFocus:true, refetchOnReconnect:true })
}
export async function restoreSession(client:QueryClient):Promise<Session> {
  await client.cancelQueries()
  client.clear()
  const session=await getSession()
  client.setQueryData(['session'],session)
  return session
}
export function useCountdown(until:number) {
  const [seconds,setSeconds]=useState(0)
  useEffect(()=>{
    const tick=()=>setSeconds(Math.max(0,Math.ceil((until-Date.now())/1000)))
    const initial=setTimeout(tick,0),timer=setInterval(tick,1000)
    return ()=>{clearTimeout(initial);clearInterval(timer)}
  },[until])
  return seconds
}
