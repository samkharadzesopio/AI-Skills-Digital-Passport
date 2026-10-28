// Full HTTP acceptance using React DOM in jsdom and real fetch. No Axios adapters,
// query fixtures, forced login or mocked API responses. Django owns all records.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
assert.ok(process.env.BTU_E2E_FIXTURE && process.env.BTU_E2E_MAILBOX,'Run through ops/test_student_e2e.py')
const fixture=JSON.parse(process.env.BTU_E2E_FIXTURE)
delete process.env.BTU_E2E_FIXTURE
assert.ok(process.env.BTU_TEST_VITE_CACHE,'A disposable Vite cache is required')
const target=new URL(process.env.BTU_DEV_API_TARGET)
assert.equal(target.hostname,'127.0.0.1')
const server=await createServer({cacheDir:process.env.BTU_TEST_VITE_CACHE,define:{'import.meta.env.VITE_ENABLE_DEMO':'false'},server:{host:'127.0.0.1',port:0,strictPort:false}})
await server.listen()
const address=server.httpServer.address(), origin=`http://127.0.0.1:${address.port}`
const dom=new JSDOM('<div id="root"></div>',{url:origin+'/student/dashboard',pretendToBeVisual:true})
const saved=new Map(), timers=new Set(), requests=[], cookies=new Map(), downloads=[]
const nativeFetch=globalThis.fetch, NativeRequest=globalThis.Request
function expose(key,value){saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{configurable:true,writable:true,value})}
let root, client
const originalAnchor=dom.window.HTMLAnchorElement.prototype.click, originalCreate=URL.createObjectURL, originalRevoke=URL.revokeObjectURL
const objects=new Map(),revoked=new Set()
try {
  for(const key of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage'])expose(key,dom.window[key])
  expose('IS_REACT_ACT_ENVIRONMENT',true)
  expose('Request',class extends NativeRequest {constructor(input,options){super(typeof input==='string'?new URL(input,origin):input,options)}})
  // Emulate the browser's same-origin cookie jar while keeping real HTTP I/O.
  expose('fetch',async(input,init)=>{
    const request=new NativeRequest(typeof input==='string'?new URL(input,origin):input,init)
    assert.equal(new URL(request.url).origin,origin,'No private traffic may leave the frontend origin')
    const headers=new Headers(request.headers)
    if(request.credentials!=='omit')headers.set('Cookie',[...cookies].map(([k,v])=>`${k}=${v}`).join('; '))
    if(!['GET','HEAD','OPTIONS'].includes(request.method))headers.set('Origin',origin)
    const response=await nativeFetch(new NativeRequest(request,{headers}))
    if(request.credentials!=='omit')for(const setCookie of response.headers.getSetCookie()){
      const [pair]=setCookie.split(';'),i=pair.indexOf('='),name=pair.slice(0,i),value=pair.slice(i+1)
      if(!value||/max-age=0/i.test(setCookie))cookies.delete(name);else cookies.set(name,value)
      if(name==='sessionid'&&value&&!/max-age=0/i.test(setCookie))assert.match(setCookie,/httponly/i)
    }
    requests.push({path:new URL(request.url).pathname,method:request.method,status:response.status})
    if(response.status>=400)console.log('HTTP rejection',new URL(request.url).pathname,response.status,(await response.clone().text()).slice(0,180))
    return response
  })
  URL.createObjectURL=blob=>{const key=`blob:acceptance-${objects.size}`;objects.set(key,blob);return key}
  URL.revokeObjectURL=key=>revoked.add(key)
  dom.window.HTMLAnchorElement.prototype.click=function(){downloads.push({blob:objects.get(this.href),filename:this.download})}
  const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client')
  const {QueryClient,QueryClientProvider,timeoutManager}=await import('@tanstack/react-query')
  timeoutManager.setTimeoutProvider({setTimeout:(fn,ms)=>{const t=setTimeout(fn,ms);timers.add(t);return t},clearTimeout:t=>{clearTimeout(t);timers.delete(t)},setInterval:(fn,ms)=>{const t=setInterval(fn,ms);timers.add(t);return t},clearInterval:t=>{clearInterval(t);timers.delete(t)}})
  const {BrowserRouter}=await import('react-router-dom')
  const {LocaleProvider}=await server.ssrLoadModule('/src/i18n.tsx')
  const {AppRoutes}=await server.ssrLoadModule('/src/App.tsx')
  const {api}=await server.ssrLoadModule('/src/services/api.ts')
  assert.equal(api.defaults.adapter,'fetch','Use the real fetch adapter throughout')
  const body=()=>document.body.textContent
  async function until(check,label){const end=Date.now()+12000;while(!check()){if(Date.now()>end)throw new Error(`Timed out ${label}: ${body()}`);await act(async()=>new Promise(r=>setTimeout(r,25)))}}
  async function mount(path,refresh=false){
    if(root)await act(async()=>root.unmount())
    if(refresh||!client){client?.clear();client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}})}
    window.history.replaceState({},'',path)
    root=createRoot(document.getElementById('root'))
    await act(async()=>root.render(React.createElement(QueryClientProvider,{client},React.createElement(LocaleProvider,null,React.createElement(BrowserRouter,null,React.createElement(AppRoutes))))))
  }
  async function fill(id,value){await act(async()=>{const input=document.getElementById(id);assert.ok(input,id);Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(input,value);input.dispatchEvent(new window.Event('input',{bubbles:true}))})}
  async function submit(){await act(async()=>document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true})))}
  async function click(text){await until(()=>[...document.querySelectorAll('button')].some(b=>b.textContent===text&&!b.disabled),text);await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===text).click())}
  async function login(email){
    await until(()=>!!document.getElementById('auth-email-student'),'login form')
    await fill('auth-email-student',email);await submit();await until(()=>!!document.getElementById('student-otp'),'OTP form')
    let code

    for(let n=0;n<80;n++){try{code=await readFile(join(process.env.BTU_E2E_MAILBOX,email.replace('@','_')+'.otp'),'utf8');break}catch{await new Promise(r=>setTimeout(r,25))}}
    assert.match(code??'',/^[0-9]{6}$/)
    await fill('student-otp',code);await submit();await until(()=>!!document.querySelector('.dashboard-passport')||body().includes('No issued Passport yet'),'authenticated dashboard')
  }
  await mount('/student/dashboard',true)
  await until(()=>window.location.pathname==='/student/login','anonymous redirect')
  await login(fixture.email)
  assert.ok(document.querySelector('.passport-carousel'));assert.match(body(),/My Passport/);assert.equal(document.querySelector('.stats'),null)
  assert.ok(cookies.has('sessionid'))
  assert.doesNotMatch(body(),/Nino|78%|Demo credential/)
  console.log('PASS real UI/HTTP: anonymous redirect, OTP sign-in, CSRF/session cookies and persisted dashboard')
  for(const [path,text]of [['/student/profile','PDF-owner'],['/student/skills','Learning format: APPLIED'],['/student/achievements','Verified achievements'],['/student/credentials','Current validity: REVOKED']]){
    await mount(path);await until(()=>body().includes(text),path)
    assert.doesNotMatch(body(),/Nino|Demo credential/)
  }
  assert.match(body(),/EXPIRED/);assert.match(body(),/VALID/)
  await mount(`/student/credentials/${fixture.credentialId}`);await until(()=>body().includes(fixture.credentialReference),'credential detail')
  await mount('/student/passport');await until(()=>body().includes(fixture.passportReference)&&body().includes('Generate Passport PDF'),'current Passport')
  await click('Generate Passport PDF');await until(()=>body().includes('Download registered PDF'),'generation')
  await click('Download registered PDF');await until(()=>downloads.length===1,'download')
  assert.match(downloads[0].filename,new RegExp(fixture.latestVersionReference))
  assert.equal(await downloads[0].blob.slice(0,5).text(),'%PDF-')
  await click('Download registered PDF');await until(()=>downloads.length===2,'repeated download')
  await mount('/student/passport/versions');await until(()=>body().includes('Version 1'),'version history')
  await mount(`/student/passport/versions/${fixture.historicalVersionId}`);await until(()=>body().includes('Historical version')&&body().includes('Generate Passport PDF'),'historical version')
  await click('Generate Passport PDF');await until(()=>body().includes('Download registered PDF'),'historical generation')
  await click('Download registered PDF');await until(()=>downloads.length===3,'historical download')
  assert.match(downloads[2].filename,new RegExp(fixture.historicalVersionReference))
  assert.equal(await downloads[2].blob.slice(0,5).text(),'%PDF-')
  // Verify the actual downloaded bytes and references over the same real proxy.
  const form=new FormData();form.append('file',downloads[0].blob,'passport.pdf')
  const verification=await fetch('/api/verification/document/',{method:'POST',body:form,credentials:'omit'})
  const verdict=await verification.json();assert.equal(verdict.authentic,true);assert.equal(verdict.is_latest,true)
  assert.equal(verdict.status,'VALID')
  const publicReference=await(await fetch(`/api/verification/${fixture.credentialReference}/`,{credentials:'omit'})).json();assert.equal(publicReference.status,'VALID')
  console.log('PASS real UI/HTTP: records, credential states/details, Passport/history, registered current/historical PDFs and public byte verification')
  await mount('/student/dashboard',true);await until(()=>body().includes('My Passport'),'session restoration after refresh')
  await click('Sign out');await until(()=>window.location.pathname==='/student/login','logout')
  assert.ok(!cookies.has('sessionid'))
  assert.ok(!client.getQueryCache().getAll().some(q=>q.queryKey[0]==='student'),'Private query data cleared')
  await mount('/student/passport');await until(()=>window.location.pathname==='/student/login','private route after logout')
  await login(fixture.otherEmail)
  assert.ok(!body().includes(fixture.credentialReference),'A restored second-student session cannot reuse the first student cache')
  await mount(`/student/credentials/${fixture.credentialId}`);await until(()=>body().includes('does not belong to your account'),'foreign credential denial')
  assert.ok(requests.some(r=>r.path===`/api/student/credentials/${fixture.credentialId}/`&&r.status===404))
  await mount(`/student/passport/versions/${fixture.latestVersionId}`);await until(()=>body().includes('does not belong to your account'),'foreign Passport denial')
  const otherDownload=await fetch(`/api/student/passport/versions/${fixture.latestVersionId}/pdf/download/`,{credentials:'include'});assert.equal(otherDownload.status,404)
  const denied=await fetch('/api/student/passport/pdf/',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',credentials:'include'});assert.equal(denied.status,403,'Missing CSRF must remain denied')
  await click('Sign out');await until(()=>window.location.pathname==='/student/login','second logout')
  assert.ok(requests.some(r=>r.path==='/api/student/dashboard/'&&r.status===200))
  assert.ok(requests.some(r=>r.path==='/api/accounts/otp/verify/'&&r.status===200))
  assert.ok([...revoked].length,'Private download URLs revoked on leaving the page')
  for(const key of Object.keys(localStorage))assert.equal(key,'btu-locale')
  console.log(`PASS real UI/HTTP: refresh restoration, logout/cache cleanup, second-student ownership denials and missing-CSRF denial (${requests.length} real proxy requests). DOM driver is jsdom, not a graphical browser; no HTTP/API responses were mocked.`)
} finally {
  if(root)await(await import('react')).act(async()=>root.unmount())
  client?.clear();for(const t of timers){clearTimeout(t);clearInterval(t)}
  dom.window.HTMLAnchorElement.prototype.click=originalAnchor;URL.createObjectURL=originalCreate;URL.revokeObjectURL=originalRevoke
  dom.window.close();for(const[k,v]of saved){if(v)Object.defineProperty(globalThis,k,v);else delete globalThis[k]}
  await server.close()
}
