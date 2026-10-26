import { Link } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { useLocale } from '../i18n'
import { demoMode } from './mode'
import './demo.css'
export function DemoBanner() {
  const { locale } = useLocale()
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!demoMode || !ref.current) return
    const root = document.documentElement, previous = root.style.getPropertyValue('--btu-demo-banner-height')
    const observer = new ResizeObserver(entries => root.style.setProperty('--btu-demo-banner-height', `${entries[0].target.getBoundingClientRect().height}px`))
    observer.observe(ref.current)
    return () => { observer.disconnect(); if (previous) root.style.setProperty('--btu-demo-banner-height', previous); else root.style.removeProperty('--btu-demo-banner-height') }
  }, [])
  if (!demoMode) return null
  return <aside ref={ref} className="demo-mode-banner" aria-label="Demo Mode"><strong>Demo Mode</strong><span>{locale === 'ka' ? 'მხოლოდ სადემონსტრაციო მონაცემები · ავტორიზაციის გარეშე · ოფიციალური მოქმედებები გამორთულია' : 'Sample data only · Not authenticated · Official actions disabled'}</span><nav aria-label="Demo workspaces"><Link to="/student/dashboard">{locale === 'ka' ? 'სტუდენტი' : 'Student'}</Link><Link to="/admin/dashboard">{locale === 'ka' ? 'ადმინისტრაცია' : 'Admin'}</Link><Link to="/verify">{locale === 'ka' ? 'გადამოწმება' : 'Verification'}</Link></nav></aside>
}
