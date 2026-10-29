import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
// Uses the real .env.local via Vite. No define override and no seeded query data.
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost:5173/', pretendToBeVisual: true })
const previous = new Map()
function expose(key,value) { previous.set(key,Object.getOwnPropertyDescriptor(globalThis,key)); Object.defineProperty(globalThis,key,{ configurable:true,writable:true,value }) }
let root
const queryTimers=new Set()
const consoleErrors=[]
const originalConsoleError=console.error
console.error=(...args)=>{consoleErrors.push(args);originalConsoleError(...args)}
try {
  for (const key of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage']) expose(key,dom.window[key])
  expose('IS_REACT_ACT_ENVIRONMENT',true)
  expose('requestAnimationFrame',dom.window.requestAnimationFrame.bind(dom.window))
  expose('cancelAnimationFrame',dom.window.cancelAnimationFrame.bind(dom.window))
  class TestResizeObserver {
    constructor(callback) { this.callback=callback }
    observe(target) { this.active=true; queueMicrotask(()=>{if(this.active)this.callback([{ target,contentRect:{width:900,height:280} }])}) }
    disconnect(){this.active=false}
    unobserve(){this.active=false}
  }
  expose('ResizeObserver',TestResizeObserver)
  dom.window.ResizeObserver=TestResizeObserver
  dom.window.HTMLElement.prototype.getBoundingClientRect=function(){return { width:900,height:280,top:0,left:0,right:900,bottom:280,x:0,y:0,toJSON(){} }}
  const runtimeErrors=[]
  dom.window.addEventListener('error',event=>runtimeErrors.push(event.error??event.message))
  const requests=[]
  expose('fetch',async (...args)=>{ requests.push(args); throw new Error('Unexpected network request in demo') })
  const React=await import('react'), {act}=React, {createRoot}=await import('react-dom/client')
  const {timeoutManager}=await import('@tanstack/react-query')
  // Track query GC timers so this DOM check exits cleanly after unmounting.
  timeoutManager.setTimeoutProvider({
    setTimeout: (callback,delay)=>{const id=setTimeout(callback,delay);queryTimers.add(id);return id},
    clearTimeout: id=>{queryTimers.delete(id);clearTimeout(id)},
    setInterval: (callback,delay)=>{const id=setInterval(callback,delay);queryTimers.add(id);return id},
    clearInterval: id=>{queryTimers.delete(id);clearInterval(id)},
  })
  const {demoMode}=await server.ssrLoadModule('/src/demo/mode.ts')
  assert.equal(demoMode,true,'Actual Vite configuration must load VITE_ENABLE_DEMO=true from frontend/.env.local')
  const {default:App}=await server.ssrLoadModule('/src/App.tsx')
  async function until(check) {
    const deadline=Date.now()+4000
    while(!check()) { if(Date.now()>deadline)throw new Error('Timed out waiting for rendered route'); await act(async()=>{await new Promise(resolve=>setTimeout(resolve,20))}) }
  }
  const cases=[
    ['/student','/student/dashboard','My Passport'],
    ['/student/dashboard','/student/dashboard','My Passport'],
    ['/student/skills','/student/skills','AI skills & competencies'],
    ['/student/credentials','/student/credentials','Sample credentials only'],
    ['/student/passport','/student/dashboard','My Passport'],
    ['/student/gap-analyzer','/student/gap-analyzer','Coming Soon'],
    ['/student/profile','/student/profile','Read-only Student identity'],
    ['/admin','/admin/dashboard','Import Activity Records'],
    ['/admin/dashboard','/admin/dashboard','Total students'],
    ['/admin/students','/admin/students','Demo student 01'],
    ['/admin/skills','/admin/skills','Data communication'],
    ['/admin/course-mappings','/admin/course-mappings','AI for business'],
    ['/admin/passports/preview','/admin/passports/preview','Passport Version ID (public reference)'],
    ['/admin/students/DEMO-ST-001/passport','/admin/students/DEMO-ST-001/passport','Demo student 01 (demo)'],
    ['/admin/credentials','/admin/credentials','Request issuance'],
    ['/admin/credentials/DEMO-CR-1','/admin/credentials/DEMO-CR-1','Request revocation'],
    ['/admin/classroom-sync','/admin/classroom-sync','DEMO-SYNC-01'],
    ['/admin/imports','/admin/imports','Validate local workbook'],
    ['/admin/audit-logs','/admin/audit-logs','Affected record'],
    ['/admin/courses?from=legacy#mapping','/admin/course-mappings','AI for business'],
    ['/admin/sync','/admin/classroom-sync','DEMO-SYNC-01'],
    ['/admin/audit','/admin/audit-logs','Affected record'],
    ['/verify','/verify','Verify an AI Skills Passport.'],
    ['/verify/reference','/verify/reference','Verification reference'],
    ['/verify/upload','/verify/upload','Drop a PDF here'],
  ]
  for(const [path,target,content] of cases) {
    window.history.replaceState({},'',path)
    root=createRoot(document.getElementById('root'))
    await act(async()=>{root.render(React.createElement(App))})
    await until(()=>window.location.pathname===target&&document.body.textContent.includes(content))
    assert.match(document.body.textContent,/Demo Mode/)
    assert.doesNotMatch(document.body.textContent,/Authentication integration pending/)
    if(target==='/admin/dashboard') { assert.equal(document.querySelector('.recharts-surface'),null); assert.ok(document.querySelector('a[href="/admin/imports"]')); assert.ok(document.querySelector('section[aria-label="Learning Data"]')); }
    if(path.includes('?from=legacy')){assert.equal(window.location.search,'?from=legacy');assert.equal(window.location.hash,'#mapping')}
    if(path==='/admin/credentials') assert.ok([...document.querySelectorAll('button')].find(b=>b.textContent==='Request issuance')?.disabled)
    if(path==='/admin/credentials/DEMO-CR-1')assert.ok([...document.querySelectorAll('button')].find(b=>b.textContent==='Request revocation')?.disabled)
    if(path==='/admin/classroom-sync')assert.ok([...document.querySelectorAll('button')].filter(b=>b.textContent==='Request retry').every(b=>b.disabled))
    if(path==='/admin/dashboard'||path==='/student/dashboard'){
      const menu=document.querySelector('.mobile-menu')
      await act(async()=>menu.dispatchEvent(new window.MouseEvent('click',{bubbles:true})))
      assert.ok(document.querySelector('.sidebar.open'),'Mobile navigation opens')
      const destination=path.startsWith('/admin')?'/admin/students':'/student/skills'
      const expected=path.startsWith('/admin')?'Demo student 01':'AI skills & competencies'
      const navLink=document.querySelector('.sidebar a[href="'+destination+'"]')
      await act(async()=>navLink.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true,button:0})))
      await until(()=>window.location.pathname===destination&&document.body.textContent.includes(expected))
      assert.equal(document.querySelector('.sidebar.open'),null,'Navigation closes after selection')
    }
    console.log('Rendered:',path,'->',target,'|',content)
    if(path==='/student') {
      const link=document.querySelector('.demo-mode-banner a[href="/admin/dashboard"]')
      await act(async()=>link.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true,button:0})))
      await until(()=>window.location.pathname==='/admin/dashboard'&&document.body.textContent.includes('Total students'))
      console.log('Client navigation: Student -> Admin via Demo Mode banner')
    }
    await act(async()=>root.unmount());root=null
  }
  assert.equal(consoleErrors.length,0,'No React console errors during tested renders/navigation')
  assert.equal(runtimeErrors.length,0,'No DOM runtime errors')
  assert.equal(requests.length,0,'No Django, authenticated, private or verification requests during demo navigation')
  console.log('Actual-config DOM route checks passed: local env loading, async mock queries, redirects, layouts, chart mounts, public pages, disabled issuance and zero API calls.')
} finally {
  console.error=originalConsoleError
  if(root)root.unmount()
  for(const timer of queryTimers){clearTimeout(timer);clearInterval(timer)}
  dom.window.close()
  for(const [key,descriptor] of previous){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key]}
  await server.close()
}
