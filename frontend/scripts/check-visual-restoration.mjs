import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
const toolsRoot = process.env.BTU_BROWSER_TOOLS || path.join(os.tmpdir(),'btu-passport-browser-tests')
const { chromium } = await import(pathToFileURL(path.join(toolsRoot,'node_modules/playwright/index.mjs')).href)
const phase=process.argv[2] || 'after', output=path.resolve(process.env.BTU_VISUAL_OUTPUT || 'restoration-review',phase)
await fs.mkdir(output,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.BTU_BROWSER_EXECUTABLE || undefined}), results=[], errors=[]
try {
  for(const demo of [true,false]) {
    const server=await createServer({define:{'import.meta.env.VITE_ENABLE_DEMO':JSON.stringify(String(demo))},cacheDir:path.join(output,'vite-cache-'+demo),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}})
    await server.listen()
    try {
      const base=`http://127.0.0.1:${server.httpServer.address().port}`
      for(const [width,height] of [[1366,768],[1440,900],[1920,1080],[768,1024],[390,844]]) {
        const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'}), page=await context.newPage()
        page.on('pageerror',e=>errors.push(e.message))
        const demoRequests=[]; if(demo)page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/'))demoRequests.push(request.url())})
        await page.route('**/api/**',route=>route.fulfill({status:403,contentType:'application/json',body:'{}'}))
        for(const route of demo?['/student/dashboard']:['/student/login','/admin/login','/verify']) {
          await page.goto(base+route)
          await page.locator(demo?'.passport-viewport':route==='/verify'?'a[href="/verify/upload"]':'form').first().waitFor()
          await page.evaluate(()=>document.fonts.ready)
          const key=route.slice(1).replaceAll('/','-')+`-${width}`
          const measure=await page.evaluate(()=>{const box=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}};return {passport:box('.passport-viewport'),actions:box('.dashboard-passport-actions'),scrollHeight:document.documentElement.scrollHeight,horizontalOverflow:document.documentElement.scrollWidth>innerWidth+2}})
          if(demo)measure.passportObscured=await page.locator('.passport-viewport').evaluate(e=>{const r=e.getBoundingClientRect();return !!document.elementFromPoint(r.left+4,Math.min(innerHeight-2,r.top+r.height/2))?.closest('.sidebar')})
          console.log(key,JSON.stringify(measure)); await page.screenshot({path:path.join(output,key+'.png'),fullPage:true}); assert.equal(measure.horizontalOverflow,false,key)
          if(demo)assert.equal(measure.passportObscured,false,key+' Passport must not be covered by the closed sidebar')
          if(demo&&width<=900){await page.getByRole('button',{name:'Toggle navigation',exact:true}).click();assert.equal(await page.locator('.sidebar.open').count(),1);await page.getByRole('navigation',{name:'Student navigation'}).getByRole('link',{name:'My Passport',exact:true}).click();assert.equal(await page.locator('.sidebar.open').count(),0)}
          if(phase==='after'&&demo&&width>=1366){assert.ok(measure.actions.bottom<=height+2,key+' actions must fit');assert.ok(measure.passport.width>=749,key+' enlarged passport');assert.ok(measure.scrollHeight<=height+2,key+' desktop should fit')}
          await page.screenshot({path:path.join(output,key+'.png'),fullPage:true})
          if(phase==='after'&&demo){for(const label of ['About the Passport','Verified AI Skillset','AI Skill Supplement','Cover'])await page.getByRole('button',{name:label,exact:true}).click();await page.locator('.passport-carousel').focus();await page.keyboard.press('ArrowRight');assert.match(await page.locator('.passport-slide[aria-hidden=false]').getAttribute('aria-label'),/^2 of/)}
          if(phase==='after'&&route==='/verify'){await page.locator('#verification-reference').fill('invalid-reference');await page.locator('#verification-reference').press('Enter');assert.ok(await page.locator('#reference-error').innerText());assert.ok(await page.locator('#verification-pdf').isVisible());await page.locator('#verification-pdf').setInputFiles({name:'unsupported.txt',mimeType:'text/plain',buffer:Buffer.from('not a PDF')});assert.ok(await page.locator('#pdf-error').innerText())}
          await page.keyboard.press('Tab'); assert.ok(await page.evaluate(()=>getComputedStyle(document.activeElement).outlineStyle!=='none'),'visible keyboard focus'); results.push({route,width,height,...measure})
          if(demo && width===1366) {
            for(const [destination,expected] of [['/student/skills','AI skills & competencies'],['/student/history','no issued history'],['/student/gap-analyzer','Coming Soon'],['/student/login','Open demo workspace'],['/admin/login','Open demo workspace'],['/verify','No login required']]) {
              await page.goto(base+destination); await page.getByText(expected,{exact:false}).first().waitFor()
            }
            assert.deepEqual(demoRequests,[],'Demo routes must not request real APIs')
          }
        }
        await context.close()
      }
    } finally {await server.close()}
  }
  assert.deepEqual(errors,[])
  await fs.writeFile(path.join(output,'measurements.json'),JSON.stringify(results,null,2))
  console.log(JSON.stringify(results,null,2))
}finally{await browser.close()}
