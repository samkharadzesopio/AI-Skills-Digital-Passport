import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
import { AxiosError, AxiosHeaders } from 'axios'
import { dashboard, skill, achievement, credential, passport, version, pdf, id } from './student-fixtures.mjs'
const server = await createServer({ define:{'import.meta.env.VITE_ENABLE_DEMO':'false'}, server:{middlewareMode:true}, appType:'custom' })
const dom = new JSDOM('<div id="root"></div>', { url:'http://localhost:5173/', pretendToBeVisual:true })
const saved = new Map(), timers = new Set()
function expose(key,value) { saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{configurable:true,writable:true,value}) }
let root
try {
  for (const key of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage']) expose(key,dom.window[key])
  expose('IS_REACT_ACT_ENVIRONMENT',true)
  const React = await import('react'), { act } = React, {createRoot}=await import('react-dom/client')
  const { QueryClient, QueryClientProvider, timeoutManager } = await import('@tanstack/react-query')
  const { MemoryRouter, Routes, Route } = await import('react-router-dom')
  timeoutManager.setTimeoutProvider({setTimeout:(fn,ms)=>{const t=setTimeout(fn,ms);timers.add(t);return t},clearTimeout:t=>{clearTimeout(t);timers.delete(t)},setInterval:(fn,ms)=>{const t=setInterval(fn,ms);timers.add(t);return t},clearInterval:t=>{clearInterval(t);timers.delete(t)}})
  const contracts = await server.ssrLoadModule('/src/student/contracts.ts')
  const {adaptPassport}=await server.ssrLoadModule('/src/student/adapter.ts')
  const service=await server.ssrLoadModule('/src/student/service.ts')
  const {api,resetCsrfToken}=await server.ssrLoadModule('/src/services/api.ts')
  const pages=await server.ssrLoadModule('/src/student/pages.tsx')
  const {PdfActions}=await server.ssrLoadModule('/src/student/PdfActions.tsx')
  const parsed=contracts.parsePassport(passport), view=adaptPassport(parsed,contracts.parseVersion(version))
  assert.equal(view.categories[0].subcategories[0].name,'Reasoning')
  assert.equal(view.categories[0].subcategories[0].skills[0].stamp_type,'APPLIED')
  assert.equal(view.verificationReference,`passport-version:${version.public_reference}`)
  assert.ok(!('verificationStatus' in view) && !('proficiency' in view.categories[0].subcategories[0].skills[0]))
  assert.equal(view.categories[0].subcategories[0].subcategories,undefined,'Never invent deeper categories')
  assert.equal(adaptPassport(parsed,{...version,id:id(77)}).currentVersion,false)
  assert.equal(contracts.parsePassport({passport:null}),null)
  assert.throws(()=>contracts.parseDashboard({...dashboard,credentials:{total:'1'}}))
  assert.throws(()=>contracts.parseVersion({...version,skills:[{}]}))
  assert.throws(()=>contracts.parsePage({count:1,results:{},next:null,previous:null},contracts.parseCredential))
  let failure=0, hold=false, empty=false, noVersion=false, pdfState={...pdf}, downloads=0
  const calls=[]
  api.defaults.adapter=async config=>{
    calls.push(config)
    const response=(status,data,headers={})=>{
      const r={status,data,headers:new AxiosHeaders(headers),statusText:'Synthetic',config}
      if(status>=400)throw new AxiosError('Do not expose private internals','ERR_BAD_RESPONSE',config,undefined,r)
      return r
    }
    if(config.url==='accounts/me/')return response(200,{email:dashboard.profile.email,role:'STUDENT',email_verified:true,student_association:'linked'})
    if(config.url==='accounts/csrf/')return response(200,{csrfToken:'a'.repeat(64)})
    if(hold)await new Promise(r=>setTimeout(r,100))
    if(failure)return response(failure,{...pdfState,error:failure===422?'PDF_NOT_REPRESENTABLE':'GENERATION_UNAVAILABLE'},failure===422?{}:{'retry-after':'2'})
    if(config.method==='post'){
      assert.deepEqual(JSON.parse(config.data),{});assert.equal(config.headers.get('X-CSRFToken'),'a'.repeat(64))
      pdfState={...pdfState,status:'ISSUED',available_for_download:true,document_reference:id(20),download_document_reference:id(20),generated_at:'2026-10-01T10:00:00Z'}
      return response(200,pdfState)
    }
    if(config.url.endsWith('download/'))return response(200,new Blob(['%PDF-test'],{type:'application/pdf'}),{'content-type':'application/pdf','content-disposition':`attachment; filename="btu-passport-${version.public_reference}.pdf"`})
    if(config.url.endsWith('pdf/status/'))return response(200,pdfState)
    if(config.url==='student/dashboard/')return response(200,empty?{...dashboard,passport:null,recognized_skills:0,verified_achievements:0,credentials:{total:0,valid:0,expired:0,revoked:0,invalid:0},recent_achievements:[],recent_credentials:[],skills_by_category:[],skills_by_subcategory:[]}:noVersion?{...dashboard,passport:{...passport,latest_version:null}}:dashboard)
    if(config.url==='student/passport/')return response(200,empty?{passport:null}:passport)
    const resources={'skills':[{...skill,achievements:[achievement],achievements_limit:100}],'achievements':[achievement],'credentials':[credential],'passport/versions':[version]}
    for(const [resource,rows] of Object.entries(resources))if(config.url.startsWith(`student/${resource}/?page=`)){
      const page=new URL('http://test/'+config.url).searchParams.get('page')
      return response(200,{count:26,results:empty?[]:rows,next:page==='1'?'https://malicious.example/private':null,previous:page==='1'?null:'http://test/previous'})
    }
    if(config.url===`student/credentials/${credential.id}/`)return response(200,credential)
    if(config.url===`student/passport/versions/${version.id}/`)return response(200,version)
    throw new Error('Unexpected student route '+config.url)
  }
  assert.equal((await service.getDashboard()).recognized_skills,1)
  await service.getSkills(2);assert.equal(calls.at(-1).url,'student/skills/?page=2')
  assert.ok((await service.getCredentials()).hasNext)
  for(const state of ['VALID','EXPIRED','REVOKED','INVALID'])assert.equal(contracts.parseCredential({...credential,validity_status:state}).validity_status,state)
  for(const state of ['NOT_REQUESTED','PENDING','GENERATING','ISSUED','FAILED'])assert.equal(contracts.parsePDF({...pdf,status:state}).status,state)
  assert.throws(()=>service.getVersion('../../another-student'))
  resetCsrfToken();await service.generatePDF(version.id)
  assert.equal(calls.at(-1).url,`student/passport/versions/${version.id}/pdf/`)
  assert.match((await service.downloadPDF(version.id)).filename,/^btu-passport-/)
  failure=422;await assert.rejects(service.generatePDF(),e=>e.status===422&&e.message.includes('does not fit')&&!e.message.includes('internals'))
  failure=409;await assert.rejects(service.generatePDF(),e=>e.retryAfter===2&&e.pdf.status==='ISSUED')
  failure=0
  const clients=[]
  async function mount(Component,path='/student'){
    if(root)await act(async()=>root.unmount())
    const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});clients.push(client)
    root=createRoot(document.getElementById('root'))
    await act(async()=>root.render(React.createElement(QueryClientProvider,{client},React.createElement(MemoryRouter,{initialEntries:[path]},React.createElement(Routes,null,React.createElement(Route,{path:'*',element:React.createElement(Component)}))))))
  }
  async function until(check){const end=Date.now()+5000;while(!check()){if(Date.now()>end)throw new Error('Timed out: '+document.body.textContent);await act(async()=>new Promise(r=>setTimeout(r,20)))}}
  async function click(text){const b=[...document.querySelectorAll('button')].find(b=>b.textContent===text);assert.ok(b,text);await act(async()=>b.click())}
  hold=true;await mount(pages.LiveDashboard);assert.match(document.body.textContent,/Loading your passport/)
  await until(()=>document.body.textContent.includes('Authenticated Student'));hold=false
  assert.doesNotMatch(document.body.textContent,/78%|Nino|Demo credential/)
  await mount(pages.LiveSkills);await until(()=>document.body.textContent.includes('Persisted reasoning'))
  await click('Next');await until(()=>calls.some(c=>c.url==='student/skills/?page=2')&&document.body.textContent.includes('Page 2'))
  assert.ok(calls.every(c=>!c.url.includes('malicious.example')))
  assert.match(document.body.textContent,/not an assessed proficiency/)
  failure=500;await mount(pages.LiveCredentials);await until(()=>document.body.textContent.includes('Records unavailable'))
  assert.doesNotMatch(document.body.textContent,/Synthetic university|Nino|Demo/)
  failure=0;await click('Retry records');await until(()=>document.body.textContent.includes('Current validity: VALID'))
  const beforeBlank=calls.length
  empty=true;await mount(pages.LivePassport);await until(()=>document.body.textContent.includes('No academic records linked yet'))
  assert.equal(document.querySelectorAll('.passport-slide').length,4)
  assert.equal(document.querySelectorAll('.passport-green-seal').length,0,'A blank preview must not display an issuer seal')
  assert.ok([...document.querySelectorAll('button')].filter(b=>['Download PDF','Share Passport'].includes(b.textContent)).every(b=>b.disabled))
  assert.ok(calls.slice(beforeBlank).every(c=>c.method==='get'&&!c.url.includes('/pdf/')),'An unissued preview never requests or generates an official PDF')
  assert.doesNotMatch(document.querySelector('.blank-passport').textContent,/Persisted reasoning|Blockchain verified|00000000-/)
  empty=false
  noVersion=true;await mount(pages.LiveDashboard);await until(()=>document.body.textContent.includes('Your passport has not been issued yet'))
  assert.doesNotMatch(document.body.textContent,/No academic records linked yet/,'Existing approved records must not be described as missing')
  noVersion=false
  await mount(pages.LiveVersions);await until(()=>document.body.textContent.includes('Current version'))
  assert.equal(document.querySelector('.is-current a').textContent,'Version 1')
  await click('Next');await until(()=>document.body.textContent.includes('Page 2'))
  assert.ok(calls.some(c=>c.url==='student/passport/versions/?page=2'))
  empty=true;await mount(pages.LiveVersions);await until(()=>document.body.textContent.includes('No passport history yet'))
  assert.equal(document.querySelectorAll('.passport-version').length,0);empty=false
  pdfState={...pdf,status:'GENERATING'};await mount(PdfActions)
  await until(()=>document.body.textContent.includes('Generation in progress'))
  assert.ok([...document.querySelectorAll('button')].some(b=>b.textContent==='Generate Passport PDF'&&b.disabled))
  const postCount=calls.filter(c=>c.method==='post').length
  pdfState={...pdf,status:'ISSUED',available_for_download:true,document_reference:id(20),download_document_reference:id(20)}
  await until(()=>document.body.textContent.includes('Download registered PDF'))
  assert.equal(calls.filter(c=>c.method==='post').length,postCount,'In-progress status polling never repeats issuance')
  pdfState={...pdf};await mount(PdfActions);await until(()=>document.body.textContent.includes('Generate Passport PDF'))
  failure=422;await click('Generate Passport PDF');await until(()=>document.body.textContent.includes('does not fit the BTU PDF template'));failure=0
  await click('Generate Passport PDF');await until(()=>document.body.textContent.includes('Download registered PDF'))
  const originalCreate=URL.createObjectURL,originalRevoke=URL.revokeObjectURL,originalClick=dom.window.HTMLAnchorElement.prototype.click
  const revoked=[]
  URL.createObjectURL=()=> 'blob:synthetic-private-download';URL.revokeObjectURL=url=>revoked.push(url)
  dom.window.HTMLAnchorElement.prototype.click=function(){downloads++;assert.match(this.download,/^btu-passport-/)}
  try {await click('Download registered PDF');await until(()=>downloads===1);await act(async()=>root.unmount());root=null;assert.ok(revoked.length)}finally{URL.createObjectURL=originalCreate;URL.revokeObjectURL=originalRevoke;dom.window.HTMLAnchorElement.prototype.click=originalClick}
  for(const c of clients)c.clear()
  console.log('Student checks passed: actual DTO adapters, flat classification, pagination origin protection, status preservation, loading/error/empty states, retry, historical PDF/CSRF, overflow and private object URL cleanup. These are unit/DOM fixtures; run the separate real HTTP acceptance test.')
} finally {
  if(root)await (await import('react')).act(async()=>root.unmount())
  for(const t of timers){clearTimeout(t);clearInterval(t)}
  dom.window.close();for(const[k,v]of saved){if(v)Object.defineProperty(globalThis,k,v);else delete globalThis[k]}
  await server.close()
}
