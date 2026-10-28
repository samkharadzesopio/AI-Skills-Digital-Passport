import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { pathToFileURL } from 'node:url'
import { createServer } from 'vite'
const tools = process.env.BTU_BROWSER_TOOLS || path.join(os.tmpdir(),'btu-passport-browser-tests')
const { chromium } = await import(pathToFileURL(path.join(tools,'node_modules/playwright/index.mjs')).href)
const output = path.resolve(process.env.BTU_TEST_ARTIFACTS || 'restoration-review/admin')
await fs.mkdir(output,{recursive:true})
const server = await createServer({root:path.resolve(import.meta.dirname,'..'),define:{'import.meta.env.VITE_ENABLE_DEMO':'"true"'}, cacheDir:process.env.BTU_TEST_VITE_CACHE || path.join(os.tmpdir(),'btu-admin-ux-cache'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}})
await server.listen()
const browser = await chromium.launch({headless:true,executablePath:process.env.BTU_BROWSER_EXECUTABLE || undefined}), errors=[], requests=[], results=[]
try {
  for(const [width,height] of [[1366,768],[1440,900],[768,1024],[390,844]]) {
    const context = await browser.newContext({viewport:{width,height},reducedMotion:'reduce'}), page = await context.newPage()
    page.on('pageerror',error=>errors.push(error.message))
    page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/'))requests.push(request.url())})
    for(const route of ['dashboard','students','skills','course-mappings','imports','credentials','audit-logs','classroom-sync']) {
      await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/admin/${route}`)
      await page.locator('main h1').waitFor()
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2),false,`${route} ${width}: document overflow`)
      assert.equal(await page.locator('section[aria-label="Learning Data"]').count(),1)
      assert.equal(await page.locator('.demo-mode-banner').count(),1)
      if(route==='dashboard') {
        assert.equal(await page.locator('.recharts-surface').count(),0)
        await page.getByRole('link',{name:'Import Activity Records',exact:true}).waitFor()
      }
      if(route==='course-mappings')assert.match(await page.locator('main').innerText(),/Activity-to-Skill Mapping/)
      if(width<=760) {
        await page.locator('header .mobile-menu').click()
        await page.locator('.sidebar.open').waitFor()
        await page.locator('.sidebar a[href="/admin/students"]').click()
        assert.equal(await page.locator('.sidebar.open').count(),0)
        await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/admin/${route}`)
        await page.locator('main h1').waitFor()
      }
      await page.screenshot({path:path.join(output,`${route}-${width}.png`),fullPage:true})
      results.push({route,width,height,passed:true})
    }
    await context.close()
  }
  assert.deepEqual(errors,[])
  assert.deepEqual(requests,[],'Demo admin pages must not contact real APIs')
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify({results,errors,requests},null,2))
  console.log(`PASS: ${results.length} admin viewport/page checks; zero API requests and page errors. Screenshots: ${output}`)
} finally {await browser.close();await server.close()}
