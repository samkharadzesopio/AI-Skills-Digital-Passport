// Actual public React -> Vite -> Django -> PostgreSQL. No API/adapter mocks.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
assert.ok(process.env.BTU_VERIFICATION_FIXTURE,'Run through ops/test_verification_e2e.py')
const fixture=JSON.parse(process.env.BTU_VERIFICATION_FIXTURE)
assert.equal(fixture.testOnly,true)
assert.ok(fixture.admin.email.startsWith('synthetic-pdf-'))
delete process.env.BTU_VERIFICATION_FIXTURE
assert.equal(new URL(process.env.BTU_DEV_API_TARGET).hostname,'127.0.0.1')
assert.ok(process.env.BTU_TEST_VITE_CACHE, 'A disposable Vite cache is required')
const server=await createServer({cacheDir:process.env.BTU_TEST_VITE_CACHE,define:{'import.meta.env.VITE_ENABLE_DEMO':'false'},server:{host:'127.0.0.1',port:0,strictPort:false}})
await server.listen()
const origin=`http://127.0.0.1:${server.httpServer.address().port}`
const dom=new JSDOM('<div id="root"></div>',{url:origin+'/verify',pretendToBeVisual:true})
const saved=new Map(),timers=new Set(),cookies=new Map(),requests=[]
const nativeFetch=globalThis.fetch,NativeRequest=globalThis.Request
let root,client,publicPhase=false
function expose(key,value){saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{configurable:true,writable:true,value})}
try {
  for(const key of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage'])expose(key,dom.window[key])
  expose('IS_REACT_ACT_ENVIRONMENT',true)
  expose('Request',class extends NativeRequest {constructor(input,options){super(typeof input==='string'?new URL(input,origin):input,options)}})
  expose('fetch',async(input,init)=>{
    const req=new NativeRequest(typeof input==='string'?new URL(input,origin):input,init)
    assert.equal(new URL(req.url).origin,origin)
    const path=new URL(req.url).pathname,headers=new Headers(req.headers)
    if(path.startsWith('/api/verification/')){
      assert.equal(req.credentials,'omit');assert.equal(headers.has('Cookie'),false);assert.equal(headers.has('Authorization'),false);assert.equal(headers.has('X-CSRFToken'),false)
    }
    if(req.credentials!=='omit')headers.set('Cookie',[...cookies].map(([k,v])=>`${k}=${v}`).join('; '))
    if(!['GET','HEAD','OPTIONS'].includes(req.method))headers.set('Origin',origin)
    const response=await nativeFetch(new NativeRequest(req,{headers}))
    if(req.credentials!=='omit')for(const cookie of response.headers.getSetCookie()){
      const [pair]=cookie.split(';'),i=pair.indexOf('='),name=pair.slice(0,i),value=pair.slice(i+1)
      if(!value||/max-age=0/i.test(cookie))cookies.delete(name);else cookies.set(name,value)
    }
    requests.push({path,status:response.status,publicPhase})
    if(path.startsWith('/api/verification/'))assert.equal(response.headers.get('cache-control'),'no-store')
    return response
  })
  let csrf
  async function privateJSON(path,data,expected=200){
    const headers={'Accept':'application/json'}
    if(data!==undefined){headers['Content-Type']='application/json';headers['X-CSRFToken']=csrf}
    const response=await fetch(path,{method:data===undefined?'GET':'POST',headers,body:data===undefined?undefined:JSON.stringify(data),credentials:'include'})
    assert.equal(response.status,expected,path)
    return expected===204?null:response.json()
  }
  csrf=(await privateJSON('/api/accounts/csrf/')).csrfToken
  await privateJSON('/api/accounts/login/',fixture.admin)
  csrf=(await privateJSON('/api/accounts/csrf/')).csrfToken
  const pdfs={}
  for(const name of ['valid','historical','revoked','expired']){
    const data=fixture[name],prefix=`/api/admin/passports/${data.passportId}/pdf/`,query=`?version_id=${data.versionId}`
    const status=await privateJSON(prefix+query,{})
    assert.equal(status.status,'ISSUED')
    const response=await fetch(prefix+'download/'+query,{credentials:'include'})
    assert.equal(response.status,200);assert.match(response.headers.get('content-type'),/application\/pdf/)
    const blob=await response.blob();assert.equal(await blob.slice(0,5).text(),'%PDF-');pdfs[name]=blob
  }
  await privateJSON('/api/accounts/logout/',{},204)
  assert.equal(cookies.has('sessionid'),false)
  const denied=await fetch('/api/student/dashboard/',{credentials:'omit'});assert.equal(denied.status,403)
  publicPhase=true
  const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client')
  const {QueryClient,QueryClientProvider,timeoutManager}=await import('@tanstack/react-query')
  timeoutManager.setTimeoutProvider({setTimeout:(fn,ms)=>{const t=setTimeout(fn,ms);timers.add(t);return t},clearTimeout:t=>{clearTimeout(t);timers.delete(t)},setInterval:(fn,ms)=>{const t=setInterval(fn,ms);timers.add(t);return t},clearInterval:t=>{clearInterval(t);timers.delete(t)}})
  const {BrowserRouter}=await import('react-router-dom')
  const {AppRoutes}=await server.ssrLoadModule('/src/App.tsx'),{LocaleProvider}=await server.ssrLoadModule('/src/i18n.tsx')
  const {verificationLink}=await server.ssrLoadModule('/src/verification/validation.ts')
  const text=()=>document.body.textContent
  async function until(check,label){const end=Date.now()+15000;while(!check()){if(Date.now()>end)throw new Error(`Timed out ${label}: ${text()}`);await act(async()=>new Promise(r=>setTimeout(r,25)))}}
  async function mount(path){if(root)await act(async()=>root.unmount());client?.clear();client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});window.history.replaceState({},'',path);root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(QueryClientProvider,{client},React.createElement(LocaleProvider,null,React.createElement(BrowserRouter,null,React.createElement(AppRoutes))))))}
  async function submit(){await act(async()=>document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true})))}
  async function result(status){await until(()=>!!document.querySelector(`[data-verification-status="${status}"]`),status);for(const secret of fixture.privateFields)assert.ok(!text().includes(secret),'Private Student fields must not be displayed');assert.ok(!client.getQueryCache().getAll().some(q=>['session','student','admin'].includes(q.queryKey[0])))}
  async function reference(kind,value,status,qr=false){await mount(verificationLink(kind,value,qr));assert.equal(document.getElementById('reference-method').value,kind);await submit();await result(status)}
  await mount('/verify');assert.match(text(),/No login required/)
  for(const [value,status] of [[fixture.credential,'valid'],[fixture.revokedCredential,'revoked'],[fixture.expiredCredential,'expired'],[fixture.unknown,'not_found']])await reference('credential',value,status)
  await reference('passport',fixture.valid.passportReference,'valid')
  await reference('passport-version',fixture.valid.versionReference,'valid')
  await reference('passport-version',fixture.historical.versionReference,'outdated',true)
  assert.match(document.querySelector('[data-fact="currency"]').textContent,/Historical version/)
  await mount(`/verify/qr/passport-version:${fixture.valid.versionReference}`);await submit();await result('valid')
  await reference('passport',fixture.revoked.passportReference,'revoked')
  await reference('passport-version',fixture.expired.versionReference,'expired')
  const before=requests.length
  await mount(`/verify/qr?reference=${fixture.credential}&reference=${fixture.unknown}&kind=credential`)
  assert.match(text(),/does not contain a single supported reference/);assert.equal(requests.length,before)
  async function upload(blob,name='passport.pdf',type='application/pdf'){
    await mount('/verify/upload');const file=new File([blob],name,{type})
    await act(async()=>{const input=document.getElementById('verification-pdf');Object.defineProperty(input,'files',{configurable:true,value:[file]});input.dispatchEvent(new window.Event('change',{bubbles:true}))})
    return file
  }
  for(const [name,status] of [['valid','valid'],['historical','outdated'],['revoked','revoked'],['expired','expired']]){
    await upload(pdfs[name]);await submit();await result(status)
    assert.match(document.querySelector('[data-fact="authenticity"]').textContent,/Recognized issued record/)
    if(name==='revoked'){
      assert.match(document.querySelector('[data-fact="currency"]').textContent,/Latest issued version/)
      assert.equal(document.querySelector('[data-fact="credential-validity"]').textContent,'Revoked')
      assert.match(text(),/does not by itself mean these PDF bytes were altered/)
    }
  }
  await upload(new Blob([pdfs.valid,'\n% modified after issuance']));await submit();await result('unverifiable')
  assert.match(document.querySelector('[data-fact="authenticity"]').textContent,/Not established/);assert.match(text(),/does not prove tampering/)
  let count=requests.length;await upload(new Blob(['bad']),'bad.txt','text/plain');assert.match(text(),/Select a single .pdf/);assert.equal(requests.length,count)
  count=requests.length;await upload(new Blob([new Uint8Array(5*1024*1024+1)]));assert.match(text(),/no larger than 5 MB/);assert.equal(requests.length,count)
  console.log('PASS real public UI/HTTP: valid/revoked/expired/unknown credentials, Passport/version references, direct/QR links, actual current/historical/revoked-latest/expired PDFs, modified PDF and local upload limits.')
  let limited=false
  for(let i=0;i<12;i++){const body=new FormData();body.append('file',pdfs.valid,'passport.pdf');const response=await fetch('/api/verification/document/',{method:'POST',body,credentials:'omit'});await response.text();if(response.status===429){limited=true;break}}
  assert.ok(limited,'Actual PostgreSQL public upload rate limit must engage')
  await upload(pdfs.valid);await submit();await until(()=>text().includes('Too many requests'),'rate limit UI')
  assert.equal(document.querySelector('[data-verification-status]'),null)
  assert.equal([...document.querySelectorAll('a')].find(a=>a.textContent==='Try again').getAttribute('aria-disabled'),'true')
  assert.ok(requests.filter(r=>r.publicPhase).every(r=>r.path.startsWith('/api/verification/')),'Public routes never bootstrap private account/Student/Admin APIs')
  for(const key of Object.keys(localStorage))assert.equal(key,'btu-locale')
  console.log(`PASS real public privacy/rate limit: anonymous verification, omitted session/CSRF/Authorization, no private API bootstrap, private Student denial and actual 429 UI (${requests.length} real proxied requests). Driver: jsdom, not a graphical browser.`)
} finally {
  if(root)await(await import('react')).act(async()=>root.unmount());client?.clear()
  for(const t of timers){clearTimeout(t);clearInterval(t)}
  dom.window.close();for(const[k,v]of saved){if(v)Object.defineProperty(globalThis,k,v);else delete globalThis[k]}
  await server.close()
}
