import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
const { chromium } = await import(pathToFileURL(path.join(os.tmpdir(),'btu-passport-browser-tests/node_modules/playwright/index.mjs')).href)
const phase=process.argv[2] || 'after', output=path.resolve('visual-review',phase)
await fs.mkdir(output,{recursive:true})
const browser=await chromium.launch({headless:true}), results=[], errors=[]
try {
  for(const demo of [true,false]) {
    const server=await createServer({define:{'import.meta.env.VITE_ENABLE_DEMO':JSON.stringify(String(demo))},cacheDir:path.join(os.tmpdir(),'btu-redesign-cache-'+demo),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}})
    await server.listen()
    try {
      const base=`http://127.0.0.1:${server.httpServer.address().port}`
      for(const [width,height] of [[1366,768],[1440,900],[1920,1080],[768,1024],[390,844]]) {
        const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'}), page=await context.newPage()
        page.on('pageerror',e=>errors.push(e.message))
        await page.route('**/api/**',route=>route.fulfill({status:403,contentType:'application/json',body:'{}'}))
        for(const route of demo?['/student/dashboard']:['/student/login','/admin/login','/verify']) {
          await page.goto(base+route)
          await page.locator(demo?'.passport-viewport':route==='/verify'?'a[href="/verify/upload"]':'form').first().waitFor()
          await page.evaluate(()=>document.fonts.ready)
          const key=route.slice(1).replaceAll('/','-')+`-${width}`
          const measure=await page.evaluate(()=>{const box=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}};return {passport:box('.passport-viewport'),actions:box('.dashboard-passport-actions'),scrollHeight:document.documentElement.scrollHeight,horizontalOverflow:document.documentElement.scrollWidth>innerWidth+2}})
          console.log(key,JSON.stringify(measure)); await page.screenshot({path:path.join(output,key+'.png'),fullPage:true}); assert.equal(measure.horizontalOverflow,false,key)
          if(phase==='after'&&demo&&width>=1366){assert.ok(measure.actions.bottom<=height+2,key+' actions must fit');assert.ok(measure.passport.width>=749,key+' enlarged passport');assert.ok(measure.scrollHeight<=height+2,key+' desktop should fit')}
          await page.screenshot({path:path.join(output,key+'.png'),fullPage:true})
          if(phase==='after'&&demo){for(const label of ['About the Passport','Verified AI Skillset','AI Skill Supplement','Cover'])await page.getByRole('button',{name:label,exact:true}).click();await page.locator('.passport-carousel').focus();await page.keyboard.press('ArrowRight');assert.match(await page.locator('.passport-slide[aria-hidden=false]').getAttribute('aria-label'),/^2 of/)}
          if(phase==='after'&&route==='/verify'){await page.locator('#verification-reference').fill('invalid-reference');await page.locator('#verification-reference').press('Enter');assert.ok(await page.locator('#reference-error').innerText());assert.ok(await page.locator('#verification-pdf').isVisible());await page.locator('#verification-pdf').setInputFiles({name:'unsupported.txt',mimeType:'text/plain',buffer:Buffer.from('not a PDF')});assert.ok(await page.locator('#pdf-error').innerText())}
          await page.keyboard.press('Tab'); assert.ok(await page.evaluate(()=>getComputedStyle(document.activeElement).outlineStyle!=='none'),'visible keyboard focus'); results.push({route,width,height,...measure})
        }
        await context.close()
      }
    } finally {await server.close()}
  }
  assert.deepEqual(errors,[])
  await fs.writeFile(path.join(output,'measurements.json'),JSON.stringify(results,null,2))
  console.log(JSON.stringify(results,null,2))
}finally{await browser.close()}

