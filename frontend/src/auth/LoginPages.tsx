import { OfficialBtuLogo } from '../components/PassportCard'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Globe2, KeyRound, LoaderCircle, Mail, ShieldCheck } from 'lucide-react'
import { demoMode } from '../demo/mode'
import { useLocale } from '../i18n'
import { useAuthText } from './i18n'
import { useCountdown, useSession, restoreSession } from './hooks'
import { AuthError } from './errors'
import { normalizeUniversityEmail } from './contracts'
import { loginAdministrator, requestStudentOtp, verifyStudentOtp } from './service'
import { LogoutButton } from './SessionPanel'
import './auth.css'
import { GoogleSignIn } from './GoogleSignIn'
function AuthLayout({kind,children}:{kind:'student'|'administrator';children:ReactNode}) {
  const t=useAuthText(),{locale,toggle}=useLocale()
  return <div className="auth-page"><header><Link to="/verify" className="auth-wordmark"><OfficialBtuLogo/> <small>AI SKILLS DIGITAL PASSPORT</small></Link><button className="button" onClick={toggle} aria-label="English / ქართული"><Globe2 size={16}/>{locale.toUpperCase()}</button></header><main><section className="auth-brand-panel"><ShieldCheck size={34}/><span>BTU AI SKILLS DIGITAL PASSPORT</span><h1>{t(kind==='student'?'studentTitle':'adminTitle')}</h1><p>{t(kind==='student'?'studentIntro':'adminIntro')}</p><small>{t('university')}</small></section><section className="auth-form-panel"><nav className="auth-tabs" aria-label="Sign in"><Link className={kind==='student'?'selected':''} to="/student/login">{t('student')}</Link><Link className={kind==='administrator'?'selected':''} to="/admin/login">{t('administrator')}</Link></nav>{children}<p className="auth-privacy">{t('privacy')}</p><Link className="auth-public-link" to="/verify">{t('publicVerification')}<ArrowRight size={15}/></Link></section></main></div>
}
export function LoginPage({kind}:{kind:'student'|'administrator'}) {
  const t=useAuthText()
  if(demoMode)return <AuthLayout kind={kind}><h2>{t('demoTitle')}</h2><p className="notice">{t('demoText')}</p><Link className="button primary" to={kind==='student'?'/student/dashboard':'/admin/dashboard'}>{t('openDemo')}</Link></AuthLayout>
  return <LiveLoginPage kind={kind}/>
}
function LiveLoginPage({kind}:{kind:'student'|'administrator'}) {
  const t=useAuthText(),session=useSession(),client=useQueryClient(),navigate=useNavigate()
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[code,setCode]=useState(''),[step,setStep]=useState<'email'|'code'>('email'),[busy,setBusy]=useState(false),[notice,setNotice]=useState(false),[error,setError]=useState(''),[limitUntil,setLimitUntil]=useState(0),[resendUntil,setResendUntil]=useState(0)
  const remaining=useCountdown(limitUntil),resendRemaining=useCountdown(resendUntil),inFlight=useRef(false),mounted=useRef(true)
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
  useEffect(()=>{
    if(session.data?.status==='authenticated' && session.data.user.role===(kind==='student'?'STUDENT':'ADMIN'))navigate(kind==='student'?'/student/dashboard':'/admin/dashboard',{replace:true})
  },[session.data,kind,navigate])
  async function submit(e:FormEvent,resend=false) {
    e.preventDefault()
    if(inFlight.current||Date.now()<limitUntil)return
    setError('')
    const normalized=normalizeUniversityEmail(email)
    if(!normalized){setError(t('emailInvalid'));return}
    const requestCode=kind==='student'&&(step==='email'||resend)
    if(requestCode&&Date.now()<resendUntil)return
    if(kind==='administrator'&&(!password||password.length>256)){setError(t('passwordInvalid'));return}
    if(kind==='student'&&!requestCode&&!/^[0-9]{6}$/.test(code)){setError(t('codeInvalid'));return}
    inFlight.current=true;setBusy(true)
    try {
      if(requestCode){
        await requestStudentOtp(normalized)
        if(mounted.current){setEmail(normalized);setStep('code');setNotice(true);setResendUntil(Date.now()+60000)}
      } else {
        if(kind==='student')await verifyStudentOtp(normalized,code)
        else await loginAdministrator(normalized,password)
        const restored=await restoreSession(client)
        if(!mounted.current)return
        if(restored.status!=='authenticated'){setError(t('unavailable'));return}
        navigate(kind==='student'?'/student/dashboard':'/admin/dashboard',{replace:true})
      }
    } catch(cause) {
      if(!mounted.current)return
      const failure=cause instanceof AuthError?cause:new AuthError('unavailable')
      setError(t(failure.code))
      if(failure.retryAt)setLimitUntil(failure.retryAt)
    } finally {
      inFlight.current=false
      if(mounted.current){setPassword('');setCode('');setBusy(false)}
    }
  }
  return <AuthLayout kind={kind}><h2>{t(kind==='student'?'student':'administrator')}</h2>
    {session.isPending&&<p role="status" className="auth-hint">{t('restoring')}</p>}
    {session.isError&&<div className="error" role="alert">{t('unavailable')} <button className="button" onClick={()=>session.refetch()}>{t('retry')}</button></div>}
    {session.data?.status==='authenticated'?<><p className="notice">{t('wrongRole')} {t('switchAccount')}</p><LogoutButton role={kind}/></>:<form onSubmit={e=>void submit(e)}>
      <label htmlFor={`auth-email-${kind}`}><Mail size={15}/>{t('email')}</label><input id={`auth-email-${kind}`} type="email" autoComplete="username" maxLength={254} required value={email} disabled={busy||(kind==='student'&&step==='code')} onChange={e=>setEmail(e.target.value)}/>
      {kind==='administrator'?<><p className="auth-hint">{t('emailOnly')}</p><label htmlFor="admin-password"><KeyRound size={15}/>{t('password')}</label><input id="admin-password" type="password" autoComplete="current-password" required maxLength={256} disabled={busy} value={password} onChange={e=>setPassword(e.target.value)}/></>:step==='code'&&<><label htmlFor="student-otp">{t('code')}</label><input id="student-otp" className="auth-otp" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required disabled={busy} value={code} onChange={e=>setCode(e.target.value.replace(/[^0-9]/g,''))}/></>}
      {notice&&<p role="status" className="notice">{t('genericSent')}</p>}
      {error&&<p className="error" role="alert">{error}</p>}
      {remaining>0&&<p role="status" className="auth-hint">{t('retryIn')} {remaining} {t('seconds')}</p>}
      <button className="button primary auth-submit" disabled={busy||session.isPending||remaining>0||(kind==='student'&&step==='email'&&resendRemaining>0)}>{busy?<><LoaderCircle className="spin" size={17}/>{t('loading')}</>:<>{t(kind==='administrator'?'signIn':step==='email'?'request':'verify')}<ArrowRight size={16}/></>}</button>
      {kind==='student'&&step==='code'&&<div className="auth-secondary-actions"><button type="button" className="button" disabled={busy||resendRemaining>0||remaining>0} onClick={e=>void submit(e,true)}>{t('resend')}{resendRemaining>0?` (${resendRemaining}s)`:''}</button><button type="button" className="button" disabled={busy} onClick={()=>{setStep('email');setCode('');setNotice(false);setError('')}}>{t('changeEmail')}</button></div>}
    </form>}{kind==='student'&&session.data?.status==='anonymous'&&<GoogleSignIn/>}</AuthLayout>
}
