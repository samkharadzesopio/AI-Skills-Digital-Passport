import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import http from 'node:http'
import path from 'node:path'
import os from 'node:os'
import {pathToFileURL} from 'node:url'
const tools=process.env.BTU_BROWSER_TOOLS || path.join(os.tmpdir(),'btu-passport-browser-tests')
const {chromium}=await import(pathToFileURL(path.join(tools,'node_modules/playwright/index.mjs')))
const csp=JSON.parse(await fs.readFile('deployment/vercel.demo.json','utf8')).headers[0].headers[0].value
const servers=[]
async function serve(dir,demo) {
 const server=http.createServer(async(req,res)=>{
  if(req.url.startsWith('/api/')){res.writeHead(404,{'Content-Type':'application/json'});res.end('{"detail":"Backend not configured"}');return}
  try {
   const url=new URL(req.url,'http://localhost');const rel=decodeURIComponent(url.pathname).replace(/^\/+/, '');
   const filename=path.resolve(dir,rel);if(!filename.startsWith(path.resolve(dir)+path.sep)&&rel!=='')throw Error('path')
   const target=path.extname(filename)?filename:path.join(dir,'index.html')
   const content=await fs.readFile(target);res.setHeader('Content-Type',target.endsWith('.js')?'text/javascript':target.endsWith('.css')?'text/css':target.endsWith('.html')?'text/html':target.endsWith('.svg')?'image/svg+xml':target.endsWith('.png')?'image/png':'application/octet-stream');
   if(demo)res.setHeader('Content-Security-Policy',csp);res.end(content)
  }catch{res.writeHead(404);res.end()}
 });await new Promise(r=>server.listen(0,'127.0.0.1',r));servers.push(server);return server.address().port
}
const browser=await chromium.launch({headless:true,args:['--no-proxy-server','--host-resolver-rules=MAP btu-synthetic-demo.vercel.app 127.0.0.1']})
const results=[],errors=[],apiRequests=[]
try {
 const demoPort=await serve('dist-demo',true),livePort=await serve('dist',false)
 for(const width of [390,768,1440]) {
  const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage()
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/')||new URL(r.url()).hostname!=='btu-synthetic-demo.vercel.app')apiRequests.push(r.url())})
  const base=`https://btu-synthetic-demo.vercel.app:${demoPort}`
  // Serve local built files under the guarded HTTPS origin; no hosted service is contacted.
  await page.route(base+'/**',async route=>{const u=new URL(route.request().url());const response=await fetch(`http://127.0.0.1:${demoPort}${u.pathname}${u.search}`);await route.fulfill({status:response.status,headers:Object.fromEntries(response.headers),body:Buffer.from(await response.arrayBuffer())})})
  for(const route of ['/','/verify','/student/login','/student/dashboard','/admin/login','/admin/dashboard','/admin/imports']) {
   console.log(width,route);await page.goto(base+route);await page.getByRole('complementary',{name:'Demo Mode'}).waitFor();
   await page.reload();await page.getByRole('complementary',{name:'Demo Mode'}).waitFor();
   if(route==='/student/dashboard')await page.getByText('My Passport',{exact:true}).waitFor()
   if(route==='/admin/dashboard')await page.getByText('Total students',{exact:true}).waitFor()
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width} ${route} overflow`)
  }
  await page.goto(base+'/');await page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0));const nav=page.getByRole('navigation',{name:'Passport workspaces'})
  for(const [label,route] of [['Student Dashboard','/student/dashboard'],['Admin Dashboard','/admin/dashboard'],['Verify Passport','/verify']]) {
   await nav.getByRole('link',{name:label,exact:true}).click();await page.waitForURL(base+route);await page.goto(base+'/')
  }
  await fs.mkdir('hosted-browser-artifacts',{recursive:true});await page.screenshot({path:`hosted-browser-artifacts/landing-${width}.png`,fullPage:true})
  results.push({width,routes:7,refresh:true,navigation:true,overflow:false});await context.close()
 }
 const page=await browser.newPage();await page.goto(`http://127.0.0.1:${demoPort}/student/dashboard`);await page.getByRole('heading',{name:'Demo deployment unavailable'}).waitFor()
 // Contract fixture only: this validates live route guards, not deployed Django authentication.
 await page.route('**/api/accounts/me/',r=>r.fulfill({status:403,contentType:'application/json',body:'{"detail":"Authentication credentials were not provided."}'}))
 for(const role of ['student','admin']){await page.goto(`http://127.0.0.1:${livePort}/${role}/dashboard`);await page.waitForURL(`**/${role}/login`);assert.equal(await page.getByRole('complementary',{name:'Demo Mode'}).count(),0)}
 assert.deepEqual(errors,[]);assert.deepEqual(apiRequests,[])
 const report={results,demoApiOrExternalRequests:apiRequests,errors,promotionGuard:true,liveAnonymousGuard:'PASS using synthetic 403 fixture; actual backend untested',hosting:'local static server, not Vercel edge'}
 await fs.writeFile('hosted-browser-results.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2))
}finally{await browser.close();for(const s of servers)await new Promise(r=>s.close(r))}
