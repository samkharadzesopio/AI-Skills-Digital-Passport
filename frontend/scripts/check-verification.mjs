import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createServer as createHTTPServer } from 'node:http'
import { AxiosError } from 'axios'
import { JSDOM } from 'jsdom'
import { uuid, sources, credential, snapshot, document as pdfResult } from './verification-fixtures.mjs'
let mode='VALID', calls=0
const transport=createHTTPServer((req,res)=>{
  calls++
  assert.equal(req.headers.cookie,undefined);assert.equal(req.headers.authorization,undefined);assert.equal(req.headers['x-csrftoken'],undefined)
  assert.ok(req.url.startsWith('/api/verification/'),'Public components must never query private APIs')
  req.resume();req.on('end',()=>{
    const route=req.url.split('/').filter(Boolean)
    let result=route[2]==='document'?pdfResult(mode):['passport','passport-version'].includes(route[2])?snapshot(mode):credential(mode,decodeURIComponent(route[2]))
    if(mode==='MALFORMED')result={status:'VALID',private:'PRIVATE'}
    const status=mode==='ERROR'?500:mode==='RATE'?429:200
    const send=()=>{res.writeHead(status,{'Content-Type':'application/json','Retry-After':'1'});res.end(JSON.stringify(result))}
    if(mode==='DELAY')setTimeout(()=>{mode='VALID';result=credential('VALID',decodeURIComponent(route[2]));send()},500);else send()
  })
})
await new Promise(r=>transport.listen(0,'127.0.0.1',r))
const base=`http://127.0.0.1:${transport.address().port}/api/`
const server=await createServer({define:{'import.meta.env.VITE_ENABLE_DEMO':'false','import.meta.env.VITE_API_BASE_URL':JSON.stringify(base)},server:{middlewareMode:true},appType:'custom'})
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost:5173/',pretendToBeVisual:true})
const saved=new Map(),timers=new Set();let root,client
function expose(key,value){saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{configurable:true,writable:true,value})}
try {
  const validation=await server.ssrLoadModule('/src/verification/validation.ts')
  const {validateReference,normalizeReference,parseReferenceLink,verificationLink,validatePdf,MAX_PDF_BYTES,retryDeadline,isPublicApiBaseSafe}=validation
  const {parseVerification,mapVerificationError,lookupReference,uploadPdf,verificationConfig}=await server.ssrLoadModule('/src/verification/service.ts')
  const trusted=Object.values(sources), reference=uuid(1)
  assert.equal(verificationConfig.enabled,true)
  assert.equal(validateReference(`passport-version:${reference}`,'passport'),null)
  assert.deepEqual(normalizeReference(`  PASSPORT-VERSION:${reference.toUpperCase()}  `,'passport'),{kind:'passport-version',reference})
  assert.equal(validateReference(reference,'passport-version'),null)
  for(const value of ['../secret','/students/1','a\\b','a\u0000b','.', '..',`passport:${reference}`])assert.equal(validateReference(value,'credential'),'credentialFormat')
  assert.equal(validateReference('student-id','passport'),'passportFormat')
  for(const query of [`reference=${reference}&reference=${reference}`,`kind=passport&kind=credential&reference=${reference}`,`kind=student&reference=${reference}`])assert.equal(parseReferenceLink(new URLSearchParams(query)),null)
  assert.equal(parseReferenceLink(new URLSearchParams(`kind=passport&reference=${reference}`),reference),null)
  assert.deepEqual(parseReferenceLink(new URLSearchParams(`reference=passport-version:${reference}`)),{kind:'passport-version',reference})
  assert.equal(verificationLink('credential',reference),`/verify/reference?kind=credential&reference=${reference}`)
  assert.equal(validatePdf({name:'p.PDF',type:'',size:MAX_PDF_BYTES}),null)
  for(const [file,error]of [[{name:'p.pdf',type:'text/html',size:10},'pdfType'],[{name:'p.exe',type:'application/pdf',size:10},'pdfType'],[{name:'p.pdf',type:'application/pdf',size:MAX_PDF_BYTES+1},'pdfSize'],[{name:'p.pdf',type:'application/pdf',size:0},'pdfSize']])assert.equal(validatePdf(file),error)
  for(const state of ['VALID','REVOKED','EXPIRED','INVALID','NOT_FOUND']){
    const result=parseVerification(credential(state),'credential',trusted,reference)
    assert.equal(result.status,state.toLowerCase());assert.deepEqual(Object.keys(result.publicInfo),['credentialId'])
    assert.ok(!JSON.stringify(result).includes('PRIVATE'))
  }
  for(const method of ['passport','passport-version','document'])for(const state of ['VALID','OUTDATED','REVOKED','EXPIRED','INVALID','UNVERIFIABLE',...(method==='document'?[]:['NOT_FOUND'])]){
    const result=parseVerification(method==='document'?pdfResult(state):snapshot(state),method,trusted)
    assert.equal(result.kind,'result',`${method} ${state}`);assert.equal(result.status,state.toLowerCase())
    assert.ok(!JSON.stringify(result).includes('PRIVATE'))
    if(['REVOKED','EXPIRED','INVALID'].includes(state)){assert.equal(result.publicInfo.authentic,true);assert.equal(result.publicInfo.isLatest,true)}
  }
  const historicalRevoked=parseVerification(pdfResult('REVOKED',{is_latest:false,passport_version:1}),'document',trusted)
  assert.equal(historicalRevoked.publicInfo.isLatest,false);assert.equal(historicalRevoked.publicInfo.credentialStatus,'revoked')
  const uncertain=parseVerification(pdfResult('UNVERIFIABLE',{authentic:true,is_latest:true,passport_version:2,latest_version:2}),'document',trusted)
  assert.equal(uncertain.kind,'result');assert.equal(uncertain.publicInfo.authentic,true)
  for(const source of ['SIMULATED_DOCUMENT_REGISTRY','MOCK_REGISTRY','TEST_REGISTRY'])assert.equal(parseVerification({...pdfResult(),source},'document',[source]).reason,'simulated')
  assert.equal(parseVerification(credential(),'credential',[],reference).reason,'untrusted')
  assert.equal(parseVerification({...credential(),source:sources.document},'credential',trusted,reference).reason,'untrusted')
  assert.equal(parseVerification(credential(),'credential',trusted,uuid(2)).reason,'contract')
  assert.equal(parseVerification({...credential(),verified:false},'credential',trusted,reference).reason,'contract')
  for(const input of [null,[],{}, {...pdfResult(),authentic:false}, {...pdfResult(),passport_version:3}, {...pdfResult('OUTDATED'),is_latest:true}, {...pdfResult(),credential_counts:{VALID:-1,REVOKED:0,EXPIRED:0,INVALID:0}}, {...pdfResult(),credential_counts:{VALID:1}}, {...pdfResult(),is_latest:null}, {...pdfResult(),credential_status:'SURPRISE'}, {...pdfResult(),status:'SURPRISE'}])assert.equal(parseVerification(input,'document',trusted).kind,'failure')
  const error=(status,headers={})=>new AxiosError('PRIVATE DIAGNOSTIC','ERR_BAD_RESPONSE',undefined,undefined,{status,headers,data:{private:'PRIVATE'},config:{},statusText:'Error'})
  assert.equal(retryDeadline('2',1000),3000);assert.equal(mapVerificationError(error(429,{'retry-after':'2'}),1000).retryAt,3000)
  for(const status of [500,502,404])assert.equal(mapVerificationError(error(status)).reason,'server')
  for(const status of [400,413,415,422])assert.equal(mapVerificationError(error(status)).reason,'rejected')
  for(const status of [401,403])assert.equal(mapVerificationError(error(status)).reason,'auth')
  assert.equal(mapVerificationError(new AxiosError('PRIVATE','ETIMEDOUT')).reason,'timeout')
  assert.equal(mapVerificationError(new AxiosError('PRIVATE','ERR_NETWORK')).reason,'network')
  assert.equal(isPublicApiBaseSafe('/api/',false),true)
  for(const url of ['//example.invalid/api/','http://example.invalid/api/','https://user:pass@example.invalid/api/'])assert.equal(isPublicApiBaseSafe(url,false),false)
  verificationConfig.enabled=false;const before=calls
  assert.equal((await lookupReference(reference,'passport',new AbortController().signal)).reason,'disconnected')
  assert.equal((await uploadPdf(new File(['pdf'],'p.pdf',{type:'application/pdf'}),new AbortController().signal,()=>{})).reason,'disconnected')
  assert.equal(calls,before);verificationConfig.enabled=true
  for(const key of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage'])expose(key,dom.window[key])
  expose('IS_REACT_ACT_ENVIRONMENT',true)
  const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client')
  const {QueryClient,QueryClientProvider,timeoutManager}=await import('@tanstack/react-query')
  timeoutManager.setTimeoutProvider({setTimeout:(fn,ms)=>{const t=setTimeout(fn,ms);timers.add(t);return t},clearTimeout:t=>{clearTimeout(t);timers.delete(t)},setInterval:(fn,ms)=>{const t=setInterval(fn,ms);timers.add(t);return t},clearInterval:t=>{clearInterval(t);timers.delete(t)}})
  const {MemoryRouter}=await import('react-router-dom'),{renderToString}=await import('react-dom/server')
  const {AppRoutes}=await server.ssrLoadModule('/src/App.tsx'),{VerificationResultView}=await server.ssrLoadModule('/src/verification/pages.tsx')
  const render=outcome=>renderToString(React.createElement(MemoryRouter,null,React.createElement(VerificationResultView,{outcome})))
  const revokedMarkup=render(parseVerification(pdfResult('REVOKED'),'document',trusted))
  assert.match(revokedMarkup,/Recognized issued record or document/);assert.match(revokedMarkup,/Latest issued version/);assert.match(revokedMarkup,/Credential support has been revoked/)
  assert.doesNotMatch(revokedMarkup,/PRIVATE/)
  const passportRevoked = parseVerification(pdfResult('REVOKED', {
    is_latest: false, credential_status: 'VALID', credential_counts: { VALID: 1, REVOKED: 0, EXPIRED: 0, INVALID: 0 },
    blockchain: { status: 'UNAVAILABLE', passport_status: 'REVOKED', private_email: 'PRIVATE' },
  }), 'document', trusted)
  assert.equal(passportRevoked.status, 'revoked');assert.equal(passportRevoked.blockchain, 'unavailable')
  assert.equal(passportRevoked.publicInfo.passportStatus, 'revoked')
  const passportRevokedMarkup = render(passportRevoked)
  assert.match(passportRevokedMarkup, /<h1>Passport revoked<\/h1>/)
  assert.match(passportRevokedMarkup, /supporting credentials have separate validity statuses/)
  assert.match(passportRevokedMarkup, /Historical version/)
  assert.doesNotMatch(passportRevokedMarkup, /Credential support has been revoked|PRIVATE/)
  const unassessedSupport = parseVerification(pdfResult('REVOKED', {
    is_latest: false, credential_status: 'UNVERIFIABLE', credential_counts: {},
    blockchain: { status: 'CONFIRMED', passport_status: 'REVOKED' },
  }), 'document', trusted)
  assert.match(render(unassessedSupport), /<h1>Passport revoked<\/h1>/)
  assert.match(render(unassessedSupport), /Could not be established/)
  assert.doesNotMatch(render(unassessedSupport), /Credential support has been revoked/)
  for (const method of ['passport', 'passport-version', 'document']) {
    const input = (method === 'document' ? pdfResult : snapshot)('REVOKED', {
      blockchain: { status: 'CONFIRMED', passport_status: 'ACTIVE' },
    })
    const support = parseVerification(input, method, trusted)
    assert.equal(support.publicInfo.passportStatus, 'active')
    assert.match(render(support), /<h1>Credential support has been revoked<\/h1>/)
    const both = parseVerification({ ...input, blockchain: { passport_status: 'REVOKED' } }, method, trusted)
    assert.match(render(both), /<h1>Passport revoked<\/h1>/)
  }
  for (const passport_status of [undefined, 'PRIVATE', { private: 'PRIVATE' }]) {
    const unknown = parseVerification(pdfResult('REVOKED', { credential_status: 'VALID',
      credential_counts: { VALID: 1, REVOKED: 0, EXPIRED: 0, INVALID: 0 },
      blockchain: { status: 'UNAVAILABLE', passport_status },
    }), 'document', trusted)
    assert.equal(unknown.publicInfo.passportStatus, undefined)
    assert.match(render(unknown), /<h1>Revocation reported<\/h1>/)
    assert.doesNotMatch(render(unknown), /PRIVATE|Credential support has been revoked|<h1>Passport revoked/)
  }
  const {LocaleProvider}=await server.ssrLoadModule('/src/i18n.tsx')
  localStorage.setItem('btu-locale', 'ka')
  const kaMarkup = renderToString(React.createElement(LocaleProvider, null,
    React.createElement(MemoryRouter, null, React.createElement(VerificationResultView, {outcome:passportRevoked}))))
  assert.match(kaMarkup, /პასპორტი გაუქმებულია/)
  localStorage.removeItem('btu-locale')
  assert.match(render(uncertain),/current credential validity could not be established/)
  assert.doesNotMatch(render(uncertain),/The university service could not establish authenticity/)
  async function mount(path){if(root)await act(async()=>root.unmount());client?.clear();client=new QueryClient();root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(QueryClientProvider,{client},React.createElement(MemoryRouter,{initialEntries:[path]},React.createElement(AppRoutes)))))}
  async function until(check){const end=Date.now()+5000;while(!check()){if(Date.now()>end)throw new Error('Timed out: '+document.body.textContent);await act(async()=>new Promise(r=>setTimeout(r,20)))}}
  async function submit(){await act(async()=>document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true})))}
  await mount(`/verify/reference?kind=passport-version&reference=${reference}`)
  assert.equal(document.getElementById('reference-method').value,'passport-version')
  await submit();await until(()=>!!document.querySelector('[data-verification-status="valid"]'))
  assert.ok(!client.getQueryCache().getAll().some(q=>['session','student'].includes(q.queryKey[0])))
  mode='RATE';await mount(`/verify/qr/${reference}?kind=credential`);await submit();await until(()=>document.body.textContent.includes('Too many requests'))
  const retry=[...document.querySelectorAll('a')].find(a=>a.textContent==='Try again');assert.equal(retry.getAttribute('aria-disabled'),'true')
  await until(()=>retry.getAttribute('aria-disabled')==='false')
  mode='ERROR';await mount(`/verify/reference?kind=credential&reference=${reference}`);await submit();await until(()=>document.body.textContent.includes('Verification service unavailable'))
  assert.doesNotMatch(document.body.textContent,/PRIVATE/)
  mode='MALFORMED';await mount(`/verify/reference?kind=credential&reference=${reference}`);await submit();await until(()=>document.body.textContent.includes('did not match the confirmed'))
  mode='DELAY';await mount(`/verify/reference?kind=credential&reference=${reference}`);await submit();assert.match(document.body.textContent,/Checking with the university/)
  await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Cancel request').click());assert.match(document.body.textContent,/Request canceled/)
  mode='VALID';await mount('/verify/upload')
  const input=document.getElementById('verification-pdf')
  async function select(file){await act(async()=>{Object.defineProperty(input,'files',{configurable:true,value:[file]});input.dispatchEvent(new window.Event('change',{bubbles:true}))})}
  await select(new File(['not pdf'],'bad.txt',{type:'text/plain'}));assert.match(document.body.textContent,/Select a single .pdf/)
  await select(new File([new Uint8Array(MAX_PDF_BYTES+1)],'large.pdf',{type:'application/pdf'}));assert.match(document.body.textContent,/no larger than 5 MB/)
  await select(new File(['%PDF-synthetic'],'private-name.pdf',{type:'application/pdf'}));await submit();await until(()=>!!document.querySelector('[data-verification-status="valid"]'))
  console.log('Verification checks passed: actual DTO projections, independent lifecycle facts, malformed/private-field rejection, reference/QR routing, file limits, loading/cancel, rate-limit cooldown, sanitized errors, public transport without credentials and disabled/demo boundaries. Contract transport uses test fixtures; real Django acceptance is separate.')
} finally {
  if(root)await(await import('react')).act(async()=>root.unmount());client?.clear()
  for(const t of timers){clearTimeout(t);clearInterval(t)}
  dom.window.close();for(const[k,v]of saved){if(v)Object.defineProperty(globalThis,k,v);else delete globalThis[k]}
  await server.close();await new Promise(r=>transport.close(r))
}
