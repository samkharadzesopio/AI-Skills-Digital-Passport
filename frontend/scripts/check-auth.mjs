import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import { AxiosError, AxiosHeaders } from 'axios'
import { dashboard } from './student-fixtures.mjs'
const server=await createServer({define:{'import.meta.env.VITE_ENABLE_DEMO':'false','import.meta.env.VITE_GOOGLE_CLIENT_ID':'""'},server:{middlewareMode:true},appType:'custom'})
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'http://localhost:5173/',pretendToBeVisual:true})
const descriptors=new Map(),timers=new Set()
function expose(key,value){descriptors.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{configurable:true,writable:true,value})}
let root
try {
 for(const key of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage'])expose(key,dom.window[key])
 expose('IS_REACT_ACT_ENVIRONMENT',true)
 expose('ResizeObserver',class{observe(){}disconnect(){}})
 const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client')
 const {timeoutManager}=await import('@tanstack/react-query')
 timeoutManager.setTimeoutProvider({setTimeout:(fn,ms)=>{const id=setTimeout(fn,ms);timers.add(id);return id},clearTimeout:id=>{timers.delete(id);clearTimeout(id)},setInterval:(fn,ms)=>{const id=setInterval(fn,ms);timers.add(id);return id},clearInterval:id=>{timers.delete(id);clearInterval(id)}})
 const {api,resetCsrfToken}=await server.ssrLoadModule('/src/services/api.ts')
 const {getSession}=await server.ssrLoadModule('/src/services/session.ts')
 const {requestStudentOtp,verifyStudentOtp,loginAdministrator,logoutAccount}=await server.ssrLoadModule('/src/auth/service.ts')
 const {parseAccountSummary,accessDecision}=await server.ssrLoadModule('/src/auth/contracts.ts')
 const student={email:'unit.student@btu.edu.ge',role:'STUDENT',email_verified:true,student_association:'linked',capabilities:[]}
 const admin={email:'unit.admin@btu.edu.ge',role:'ADMIN',email_verified:true,student_association:'unlinked',capabilities:[]}
 let current=null,csrf=null,generation=0,logoutFailure=false,rateLimit=false,sessionNetwork=false,csrfFailure=false
 const calls=[]
 api.defaults.adapter=async config=>{
  const path=config.url,method=config.method,body=config.data?JSON.parse(config.data):null
  calls.push({path,method,body,csrf:config.headers.get('X-CSRFToken')})
  assert.equal(config.baseURL,'/api/');assert.equal(config.withCredentials,true)
  const response=(status,data,headers={})=>{
   const r={status,data,statusText:'Test response',headers:new AxiosHeaders(headers),config}
   if(status>=400)throw new AxiosError('Synthetic error with request data; must be sanitized','ERR_BAD_RESPONSE',config,undefined,r)
   return r
  }
  if(path==='accounts/csrf/'){csrf='A'.repeat(63)+String(++generation%10);return response(200,{csrfToken:csrf})}
  if(path==='accounts/me/'){
   if(sessionNetwork)throw new AxiosError('Synthetic network error','ERR_NETWORK',config)
   return current?response(200,current):response(403,{detail:'Authentication credentials were not provided.'})
  }
  if(path==='student/passport/pdf/status/')return response(200,{status:'NOT_REQUESTED',available_for_download:false,document_reference:null,passport_reference:dashboard.passport.public_reference,passport_version_reference:dashboard.passport.latest_version.public_reference,generated_at:null,download_document_reference:null,error:null});
  if(path==='student/dashboard/')return current?response(200,dashboard):response(403,{})
  assert.equal(config.headers.get('X-CSRFToken'),csrf,'Mutation must send the latest server CSRF token')
  assert.ok(csrf,'Mutation must bootstrap CSRF first')
  if(csrfFailure){csrfFailure=false;return response(403,'Synthetic HTML CSRF failure')}
  if(path==='accounts/otp/request/')return rateLimit?response(429,{detail:'Too many requests'},{'retry-after':'1'}):response(202,{detail:'If eligible, a login code will be sent to your registered email.'})
  if(path==='accounts/otp/verify/'){
   if(body.code!=='123456')return response(400,{detail:'Invalid or expired login code.'})
   current={...student};csrf=null;return response(200,{detail:'Authenticated.'})
  }
  if(path==='accounts/login/'){
   if(body.password!==' unit-test password ')return response(401,{detail:'Invalid email or password.'})
   current={...admin};csrf=null;return response(200,current)
  }
  if(path==='accounts/logout/'){
   if(logoutFailure)throw new AxiosError('Synthetic logout failure','ERR_NETWORK',config)
   current=null;csrf=null;return response(204,'')
  }
  throw new Error('Unexpected endpoint')
 }
 assert.deepEqual(await getSession(),{status:'anonymous'})
 await requestStudentOtp(' UNIT.STUDENT@BTU.EDU.GE ')
 assert.deepEqual(calls.at(-1).body,{email:student.email})
 await assert.rejects(verifyStudentOtp(student.email,'000000'),e=>e.code==='invalidCode'&&!('config'in e)&&!e.message.includes('000000'))
 await verifyStudentOtp(student.email,'123456')
 assert.deepEqual(await getSession(),{status:'authenticated',user:student})
 await logoutAccount()
 assert.equal(calls.at(-2).path,'accounts/csrf/','Login CSRF rotation requires a new bootstrap before logout')
 await assert.rejects(loginAdministrator(admin.email,'incorrect'),e=>e.code==='invalidCredentials'&&!('config'in e))
 await loginAdministrator(admin.email,' unit-test password ')
 assert.deepEqual(calls.at(-1).body,{email:admin.email,password:' unit-test password '})
 assert.equal(accessDecision(await getSession(),'administrator'),'permissions-missing')
 csrfFailure=true
 await assert.rejects(logoutAccount(),e=>e.code==='csrf')
 await logoutAccount()
 assert.equal(calls.at(-2).path,'accounts/csrf/','A rejected CSRF token is discarded; only manual retry sends the mutation again')
 rateLimit=true
 await assert.rejects(requestStudentOtp(student.email),e=>e.code==='rateLimit'&&e.retryAt>Date.now())
 rateLimit=false
 for(const [user,role,decision] of [[student,'student','allow'],[{...student,student_association:'unlinked'},'student','unlinked'],[{...student,email_verified:false},'student','unverified'],[student,'administrator','wrong-role'],[admin,'administrator','permissions-missing']])assert.equal(accessDecision({status:'authenticated',user},role),decision)
 assert.equal(accessDecision({status:'anonymous'},'student'),'login')
 assert.equal(accessDecision({status:'authenticated',user:{...student,student_association:'unlinked',portal_access:true}},'student'),'allow')
 assert.throws(()=>parseAccountSummary({...admin,portal_access:true}))
 assert.deepEqual(Object.keys(parseAccountSummary({...admin,permissions:['fake'],userId:'fake-id'})).sort(),Object.keys(admin).sort())
 assert.throws(()=>parseAccountSummary({...student,role:'administrator'}))
 assert.deepEqual(parseAccountSummary({...student,capabilities:['manage_credentials']}).capabilities,[])
 assert.deepEqual(parseAccountSummary({...admin,capabilities:['manage_credentials','unknown_grant']}).capabilities,['manage_credentials'])
 assert.equal(accessDecision({status:'authenticated',user:parseAccountSummary({...admin,capabilities:['sync_classroom']})},'administrator'),'allow')
 current=null;resetCsrfToken();calls.length=0
 const {default:App}=await server.ssrLoadModule('/src/App.tsx')
 async function until(check){const end=Date.now()+5000;while(!check()){if(Date.now()>end)throw new Error('Timed out waiting for auth UI');await act(async()=>{await new Promise(r=>setTimeout(r,20))})}}
 async function mount(path){if(root){await act(async()=>root.unmount());root=null}window.history.replaceState({},'',path);root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(App)))}
 async function fill(id,value){await act(async()=>{const input=document.getElementById(id);assert.ok(input,id);Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(input,value);input.dispatchEvent(new window.Event('input',{bubbles:true}))})}
 async function submit(){await act(async()=>document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true})))}
 async function clickLogout(){const button=[...document.querySelectorAll('button')].find(b=>b.textContent==='Sign out');assert.ok(button);await act(async()=>button.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true})))}
 await mount('/student/dashboard')
 await until(()=>window.location.pathname==='/student/login'&&!!document.querySelector('.auth-submit'))
 assert.equal(document.querySelectorAll('.auth-form-panel input').length,0)
 assert.equal(document.querySelectorAll('.auth-form-panel button').length,1)
 assert.equal(document.querySelector('.auth-submit').textContent,'Sign in')
 assert.doesNotMatch(document.querySelector('.auth-form-panel').textContent,/Request a code|Continue with Google|one-time/)
 current={...student}
 await mount('/student/dashboard');await until(()=>document.body.textContent.includes('Authenticated Student'))
 assert.match(document.body.textContent,/unit.student@btu.edu.ge/);assert.doesNotMatch(document.body.textContent,/Nino|DEMO-PASSPORT/)
 const beforeRefresh=calls.filter(c=>c.path==='accounts/me/').length
 await mount('/student/dashboard')
 await until(()=>calls.filter(c=>c.path==='accounts/me/').length>beforeRefresh&&document.body.textContent.includes('Authenticated Student'))
 logoutFailure=true;await clickLogout()
 await until(()=>document.body.textContent.includes('Could not confirm server logout'))
 assert.ok(current,'Failed logout must not claim the server session ended')
 logoutFailure=false;await clickLogout()
 await until(()=>window.location.pathname==='/student/login')
 assert.equal(current,null)
 await mount('/admin/login')
 await until(()=>!!document.getElementById('admin-password')&&!document.querySelector('button[type="submit"]')?.disabled)
 await fill('auth-email-administrator',admin.email);await fill('admin-password','wrong');await submit()
 await until(()=>document.body.textContent.includes('Invalid email or password'))
 assert.equal(document.getElementById('admin-password').value,'')
 await fill('admin-password',' unit-test password ');await submit()
 await until(()=>window.location.pathname==='/admin/dashboard'&&document.body.textContent.includes('Administrator permissions are not available'))
 assert.doesNotMatch(document.body.textContent,/Total students|Demo student|Nino/)
 await clickLogout();await until(()=>window.location.pathname==='/admin/login')
 current={...student,student_association:'unlinked',portal_access:true}
 await mount('/student/dashboard');await until(()=>document.body.textContent.includes('No Passport records are linked yet'))
 assert.doesNotMatch(document.body.textContent,/Authenticated Student|Recent credentials/)
 await clickLogout();await until(()=>window.location.pathname==='/student/login')
 await act(async()=>root.unmount());root=null
 await new Promise(resolve=>setTimeout(resolve,10))
 sessionNetwork=true
 await mount('/student/dashboard')
 await until(()=>document.body.textContent.includes('Authentication service is unavailable'))
 assert.doesNotMatch(document.body.textContent,/Nino|Recent credentials/)
 sessionNetwork=false
 current={...student}
 await mount('/student/dashboard');await until(()=>document.body.textContent.includes('Authenticated Student'))
 current=null
 await mount('/student/dashboard');await until(()=>window.location.pathname==='/student/login')
 assert.doesNotMatch(document.body.textContent,/unit.student@btu.edu.ge|Nino/)
 for(const key of Object.keys(localStorage))assert.equal(key,'btu-locale','No credentials/tokens/identity persisted')
 assert.ok(calls.every(c=>c.path.startsWith('accounts/')||['student/dashboard/','student/passport/pdf/status/'].includes(c.path)),'Only the authenticated dashboard data route is expected here')
 assert.equal(calls.filter(c=>c.path==='accounts/login/').at(-1).body.password,' unit-test password ')
 console.log('Mocked auth integration passed: retained OTP API, administrator passwords, CSRF, one-button Student screen, empty portal, guards, restoration, logout and no persisted secrets. No real Django account was used.')
} finally {
 if(root)await (await import('react')).act(async()=>root.unmount())
 for(const timer of timers){clearTimeout(timer);clearInterval(timer)}
 dom.window.close()
 for(const[key,value]of descriptors){if(value)Object.defineProperty(globalThis,key,value);else delete globalThis[key]}
 await server.close()
}
