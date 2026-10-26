// Real React -> Vite -> Django -> disposable PostgreSQL; no API mocks.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
assert.ok(process.env.BTU_ADMIN_FIXTURE && process.env.BTU_ADMIN_ARTIFACTS, 'Run through ops/test_admin_e2e.py')
const fixture = JSON.parse(process.env.BTU_ADMIN_FIXTURE)
assert.equal(fixture.testOnly, true)
delete process.env.BTU_ADMIN_FIXTURE
assert.equal(new URL(process.env.BTU_DEV_API_TARGET).hostname, '127.0.0.1')
assert.ok(process.env.BTU_TEST_VITE_CACHE, 'A disposable Vite cache is required')
const server = await createServer({cacheDir:process.env.BTU_TEST_VITE_CACHE, define: { 'import.meta.env.VITE_ENABLE_DEMO':'false' }, server: { host:'127.0.0.1', port:0, strictPort:false } })
await server.listen()
const origin = `http://127.0.0.1:${server.httpServer.address().port}`, dom = new JSDOM('<div id="root"></div>', { url:origin+'/admin/login', pretendToBeVisual:true }), saved = new Map(), timers = new Set(), cookies = new Map(), requests = [], downloads = [], objects = new Map()
const nativeFetch = globalThis.fetch, NativeRequest = globalThis.Request, originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL, originalClick = dom.window.HTMLAnchorElement.prototype.click
let root, client
function expose(k, v) { saved.set(k, Object.getOwnPropertyDescriptor(globalThis, k)); Object.defineProperty(globalThis, k, { configurable:true, writable:true, value:v }) }
try {
  for (const k of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage','DOMParser']) expose(k, dom.window[k])
  expose('IS_REACT_ACT_ENVIRONMENT', true)
  expose('Request', class extends NativeRequest { constructor(input, options) { super(typeof input === 'string' ? new URL(input, origin) : input, options) } })
  expose('fetch', async (input, init) => {
    const req = new NativeRequest(typeof input === 'string' ? new URL(input, origin) : input, init), path = new URL(req.url).pathname, headers = new Headers(req.headers)
    assert.equal(new URL(req.url).origin, origin)
    if (path.startsWith('/api/verification/')) { assert.equal(req.credentials, 'omit'); assert.ok(!headers.has('Cookie') && !headers.has('Authorization') && !headers.has('X-CSRFToken')) }
    if (req.credentials !== 'omit') headers.set('Cookie', [...cookies].map(([k,v]) => `${k}=${v}`).join('; '))
    if (!['GET','HEAD','OPTIONS'].includes(req.method)) headers.set('Origin', origin)
    const payload = path === '/api/admin/credentials/issue/' ? await req.clone().json() : undefined
    const response = await nativeFetch(new NativeRequest(req, { headers }))
    if (req.credentials !== 'omit') for (const cookie of response.headers.getSetCookie()) { const [pair] = cookie.split(';'), i = pair.indexOf('='), name = pair.slice(0,i), value = pair.slice(i+1); if (!value || /max-age=0/i.test(cookie)) cookies.delete(name); else cookies.set(name,value) }
    requests.push({ path, method:req.method, status:response.status, payload })
    if (path.startsWith('/api/admin/') || path.startsWith('/api/integrations/')) assert.equal(response.headers.get('cache-control'), 'no-store')
    return response
  })
  URL.createObjectURL = blob => { const url = originalCreate(blob); objects.set(url,blob); return url }
  URL.revokeObjectURL = url => { objects.delete(url); originalRevoke(url) }
  dom.window.HTMLAnchorElement.prototype.click = function() { if (this.download) downloads.push({ filename:this.download, blob:objects.get(this.href) }); else originalClick.call(this) }
  const React = await import('react'), { act } = React, { createRoot } = await import('react-dom/client'), { QueryClient, QueryClientProvider, timeoutManager } = await import('@tanstack/react-query'), { BrowserRouter } = await import('react-router-dom')
  timeoutManager.setTimeoutProvider({ setTimeout:(f,ms) => { const t=setTimeout(f,ms);timers.add(t);return t }, clearTimeout:t => { clearTimeout(t);timers.delete(t) }, setInterval:(f,ms) => { const t=setInterval(f,ms);timers.add(t);return t }, clearInterval:t => { clearInterval(t);timers.delete(t) } })
  const { AppRoutes } = await server.ssrLoadModule('/src/App.tsx'), { LocaleProvider } = await server.ssrLoadModule('/src/i18n.tsx'), { api } = await server.ssrLoadModule('/src/services/api.ts')
  assert.equal(api.defaults.adapter,'fetch')
  const text = () => document.body.textContent
  async function until(check,label) { const end=Date.now()+18000; while(!check()) { if(Date.now()>end) throw new Error(`Timeout ${label}: ${text()}`); await act(async()=>new Promise(r=>setTimeout(r,25))) } }
  async function mount(path) { if(root) await act(async()=>root.unmount());client?.clear();client=new QueryClient({ defaultOptions:{ queries:{ retry:false,gcTime:0 } } });window.history.replaceState({},'',path);root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(QueryClientProvider,{client},React.createElement(LocaleProvider,null,React.createElement(BrowserRouter,null,React.createElement(AppRoutes)))))) }
  async function fill(id,value) { await act(async()=>{ const el=document.getElementById(id);assert.ok(el,id);const proto=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);el.dispatchEvent(new window.Event('input',{bubbles:true})) }) }
  async function submit() { await act(async()=>document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}))) }
  async function click(label) { await until(()=>[...document.querySelectorAll('button')].some(b=>b.textContent===label&&!b.disabled),label);await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===label).click()) }
  async function login(reader=false) { await mount('/admin/login');await until(()=>!!document.getElementById('admin-password'),'Admin password form');await fill('auth-email-administrator',reader?'journey-reader@btu.edu.ge':'journey-admin@btu.edu.ge');await fill('admin-password',reader?fixture.readerPassword:fixture.adminPassword);await submit();await until(()=>text().includes('Administration dashboard')&&text().includes('Verified achievements'),'authenticated Admin dashboard');assert.equal(client.getQueryData(['admin','demo']),undefined) }
  async function logout() { await click('Sign out');await until(()=>!cookies.has('sessionid'),'server logout') }
  async function json(path, data, expected=200, method='POST') { let headers={Accept:'application/json'};if(data!==undefined) { const bootstrap=await fetch('/api/accounts/csrf/',{credentials:'include'});headers={...headers,'Content-Type':'application/json','X-CSRFToken':(await bootstrap.json()).csrfToken} } const r=await fetch(path,{method:data===undefined?'GET':method,credentials:'include',headers,body:data===undefined?undefined:JSON.stringify(data)});assert.equal(r.status,expected,path);return expected===204?null:r.json() }
  async function upload(blob,path,id,name) { await mount(path);await until(()=>!!document.getElementById(id),'upload form');await act(async()=>{ const file=new File([blob],name,{type:name.endsWith('.pdf')?'application/pdf':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});Object.defineProperty(document.getElementById(id),'files',{configurable:true,value:[file]});document.getElementById(id).dispatchEvent(new window.Event('change',{bubbles:true})) }) }
  await login()
  const me=await json('/api/accounts/me/');assert.equal(me.capabilities.length,6)
  await mount('/admin/students');await until(()=>text().includes('BTU-T-0010'),'real Student list');assert.doesNotMatch(text(),/Nino|DEMO-/)
  await click('New Student record')
  for(const [k,v] of Object.entries({external_student_id:'ADMIN-HTTP-CREATED',first_name:'Synthetic',last_name:'Created',email:'created-admin-http@btu.edu.ge',program:'AI',education_level:'Bachelor',student_status:'ACTIVE'}))await fill(`student-${k}`,v)
  await click('Create Student record');await click('Confirm Create Student record');await until(()=>text().includes('ADMIN-HTTP-CREATED')&&text().includes('Edit academic profile'),'Student creation')
  const createdId=window.location.pathname.split('/').at(-1)
  await click('Edit academic profile');assert.equal(document.getElementById('student-email'),null);assert.equal(document.getElementById('student-external_student_id'),null);await fill('student-program','Synthetic updated program');await click('Update Student record');await click('Confirm Update Student record');await until(()=>text().includes('Synthetic updated program')&&!text().includes('Confirm Update'),'protected Student edit')
  await json(`/api/admin/students/${createdId}/`,{email:'identity-replacement@btu.edu.ge'},400,'PATCH')
  await mount('/admin/classroom-sync');await until(()=>text().includes('CLASSROOM')||text().includes('BTU-T-0010'),'simulated completion preview');await click('Preview sync (dry run)');await until(()=>text().includes('Sync preview'),'dry run');await click('Synchronize simulated completions');await click('Confirm Synchronize simulated completions');await until(()=>text().includes('Sync completed')&&text().includes('CREDENTIAL_ISSUED'),'persisted sync issuance')
  const syncAgain=await json('/api/integrations/classroom/sync/',{dry_run:false});assert.equal(syncAgain.issued,0);assert.equal(syncAgain.skipped,1)
  await mount(`/admin/students/${fixture.studentId}`);await until(()=>!!document.querySelector('input[aria-label="Select Ai Literacy"]'),'approved verified achievement');await act(async()=>document.querySelector('input[aria-label="Select Ai Literacy"]').click());await click('Issue credential');await click('Confirm Issue credential');await until(()=>text().includes('Credential issued:'),'evidence issuance')
  const issuedPath=[...document.querySelectorAll('a')].find(a=>a.parentElement.textContent.startsWith('Credential issued:')).getAttribute('href'), credentialId=issuedPath.split('/').at(-1), payload=requests.filter(r=>r.path==='/api/admin/credentials/issue/').at(-1).payload
  assert.deepEqual(Object.keys(payload).sort(),['achievement_ids','expires_at','idempotency_key']);const replay=await json('/api/admin/credentials/issue/',payload);assert.equal(replay.id,credentialId)
  await mount(`/admin/students/${fixture.studentId}/passport`);await until(()=>text().includes('Generate Passport PDF'),'issued Passport');await click('Generate Passport PDF');await click('Confirm Generate Passport PDF');await until(()=>text().includes('Download registered PDF'),'registered PDF generation');await click('Download registered PDF');await until(()=>downloads.length===1,'registered PDF bytes');assert.equal(await downloads[0].blob.slice(0,5).text(),'%PDF-');assert.match(downloads[0].filename,/^btu-passport-[0-9a-f-]+\.pdf$/)
  await upload(downloads[0].blob,'/verify/upload','verification-pdf','passport.pdf');await submit();await until(()=>!!document.querySelector('[data-verification-status="valid"]'),'public frontend PDF validity');assert.match(document.querySelector('[data-fact="authenticity"]').textContent,/Recognized issued record/)
  await mount(issuedPath);await until(()=>!!document.getElementById('revocation-reason'),'Admin revocation');await fill('revocation-reason','Synthetic acceptance revocation');await click('Revoke credential');await click('Confirm Revoke credential');await until(()=>text().includes('REVOKED')&&!document.getElementById('revocation-reason'),'revoked state refresh')
  await logout();await mount('/student/login');await until(()=>!!document.getElementById('auth-email-student'),'Student login');await fill('auth-email-student',fixture.email);await submit();await until(()=>!!document.getElementById('student-otp'),'Student OTP request')
  let code;for(let i=0;i<80;i++){try{code=await readFile(join(process.env.BTU_ADMIN_ARTIFACTS,fixture.email.replace('@','_')+'.otp'),'utf8');break}catch{await new Promise(r=>setTimeout(r,25))}}assert.match(code??'',/^[0-9]{6}$/);await fill('student-otp',code);await submit();await until(()=>text().includes('Welcome, Synthetic'),'real Student sign-in')
  await mount('/student/credentials');await until(()=>text().includes('Current validity: REVOKED'),'Student revoked state');assert.match(text(),/Current validity: VALID/)
  await json('/api/admin/statistics/',undefined,403)
  await upload(downloads[0].blob,'/verify/upload','verification-pdf','passport.pdf');await submit();await until(()=>!!document.querySelector('[data-verification-status="revoked"]'),'revoked downloaded PDF');assert.match(document.querySelector('[data-fact="authenticity"]').textContent,/Recognized issued record/);assert.equal(document.querySelector('[data-fact="credential-validity"]').textContent,'Revoked')
  await mount('/student/dashboard');await until(()=>text().includes('Welcome, Synthetic'),'Student restored session');await logout()
  await login()
  const excel=await readFile(join(process.env.BTU_ADMIN_ARTIFACTS,'completion-evidence.xlsx'));await upload(excel,'/admin/imports','completion-workbook','completion-evidence.xlsx');await until(()=>text().includes('Completion schema found:'),'Excel schema validation');await click('Import Excel evidence');await click('Confirm Import Excel evidence');await until(()=>text().includes('Import result')&&text().includes('Course was not passed'),'real multipart rows and errors')
  const runs=await json('/api/integrations/imports/');const imported=runs.results.find(r=>r.source==='BTU_EXCEL'&&r.id!==fixture.recoveryRun);assert.ok(imported);assert.equal(imported.validation_errors[0].row,3)
  await click(`Inspect import ${fixture.recoveryRun} events`);await until(()=>text().includes('ADMIN-HTTP-RECOVERY'),'recovery event history');await click('Retry event ADMIN-HTTP-RECOVERY');await click('Confirm Retry event ADMIN-HTTP-RECOVERY');await until(()=>text().includes('CREDENTIAL_ISSUED'),'persisted import retry');const duplicate=await json(`/api/integrations/imports/events/${fixture.recoveryEvent}/retry/`,{});assert.equal(duplicate.result,'skipped')
  await click('Import configured Google Sheet');await click('Confirm Import configured Google Sheet');await until(()=>text().includes('configuration or storage is unavailable'),'truthful Google configuration state')
  for(const [path,value]of [['skills','Learning format: APPLIED'],['course-mappings','AI_LITERACY'],['audit-logs','General security-audit reading']]){await mount('/admin/'+path);await until(()=>text().includes(value),path);assert.equal(client.getQueryData(['admin','demo']),undefined);assert.doesNotMatch(text(),/Nino|DEMO-/)}
  const missing=await fetch('/api/integrations/classroom/sync/',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({dry_run:false})});assert.equal(missing.status,403);await missing.text()
  await logout();await login(true)
  await mount(`/admin/students/${fixture.studentId}`);await until(()=>text().includes('Ai Literacy'),'reader sees achievements');assert.ok(!text().includes('Issue credential'));assert.ok(!text().includes('Edit academic profile'))
  await mount(issuedPath);await until(()=>text().includes('REVOKED'),'reader credential');assert.equal(document.getElementById('revocation-reason'),null)
  await json('/api/admin/credentials/issue/',payload,403);await json(`/api/admin/credentials/${credentialId}/revoke/`,{reason:'Forbidden'},403);await json('/api/integrations/classroom/sync/',{dry_run:false},403);await json('/api/integrations/import/google-sheets/',{},403);await json('/api/admin/students/',{},403)
  const before=requests.length;await mount('/admin/imports');await until(()=>text().includes('Permission required'),'reader import route gate');assert.ok(!requests.slice(before).some(r=>r.path.startsWith('/api/integrations/')))
  await mount('/admin/dashboard');await until(()=>text().includes('Administration dashboard'),'reader dashboard');await logout();await mount('/admin/students');await until(()=>window.location.pathname==='/admin/login','expired session redirect');assert.ok(!client.getQueryCache().getAll().some(q=>q.queryKey[0]==='admin-live'&&q.state.data))
  for(const key of Object.keys(localStorage))assert.equal(key,'btu-locale')
  console.log(`PASS real Admin/Student/public UI HTTP: explicit-grant password session, dashboard/Student create+protected edit, simulated dry-run/sync/history and replay, evidence-only issuance and duplicate replay, issued Passport PDF/download, public valid->revoked bytes, real Student OTP/status, multipart Excel row errors/history/retry, configured Sheet unavailability, catalog/mappings, grant/CSRF/session denials (${requests.length} real proxied requests). Driver: jsdom, not a graphical browser.`)
} finally {
  if(root)await(await import('react')).act(async()=>root.unmount());client?.clear();for(const t of timers){clearTimeout(t);clearInterval(t)}for(const url of objects.keys())originalRevoke(url);URL.createObjectURL=originalCreate;URL.revokeObjectURL=originalRevoke;dom.window.HTMLAnchorElement.prototype.click=originalClick;dom.window.close();for(const[k,v]of saved){if(v)Object.defineProperty(globalThis,k,v);else delete globalThis[k]}await server.close()
}
