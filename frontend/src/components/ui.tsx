import type { ReactNode } from 'react'
import { AlertCircle, LoaderCircle } from 'lucide-react'
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) { return <section className={`card ${className}`}>{children}</section> }
export function EmptyState({ title, children }: { title: string; children: ReactNode }) { return <div className="empty"><AlertCircle size={30}/><h2>{title}</h2><p>{children}</p></div> }
export function Loading() { return <div className="empty" role="status"><LoaderCircle className="spin"/>Loading your passport…</div> }
