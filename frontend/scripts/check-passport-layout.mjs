import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { createServer } from 'vite'

// Optional isolated test dependency; does not alter the application's package dependencies.
const toolsRoot = process.env.BTU_BROWSER_TOOLS || path.join(os.tmpdir(), 'btu-passport-browser-tests')
const { chromium } = await import(pathToFileURL(path.join(toolsRoot, 'node_modules/playwright/index.mjs')).href)
const output = path.join(os.tmpdir(), 'btu-passport-layout-results')
await fs.mkdir(output, { recursive: true })
const fixture = {
  demonstration: true, firstName: '\u10e5\u10d0'.repeat(70), lastName: 'Long surname '.repeat(10), issuer: null, reference: null, issuedOn: null, status: 'DEMONSTRATION',
  skills: Array.from({ length: 25 }, (_, index) => ({ id: `layout-${index}`, name: index === 0 ? 'LongSkillName'.repeat(12) : `Synthetic AI skill ${index}`,
    description: index === 0 ? 'Full long description with no truncation. '.repeat(70) : `Complete description for synthetic skill ${index}.`,
    experience: `Synthetic learning experience ${index}`, earnedOn: '2026-10-20', learningExperiences: index < 2 ? [{title:'First experience',earnedOn:'2026-10-20'},{title:'Second experience',earnedOn:'2026-10-21'}] : undefined, stampType: ['FOCUSED', 'APPLIED', 'ADVANCED'][index % 3] })),
}
const server = await createServer({ root: path.resolve(import.meta.dirname, '..'), cacheDir: path.join(output, 'vite-cache'),
  define: { 'import.meta.env.VITE_ENABLE_DEMO': JSON.stringify('true') }, optimizeDeps: { include: ['react', 'react-dom/client', 'react-router-dom'] },
  plugins: [{name: 'passport-layout-fixture',configureServer(instance) { instance.middlewares.use('/__passport-layout-fixture', async (_request, response) => {
  const html = await instance.transformIndexHtml('/__passport-layout-fixture', `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:16px}*{box-sizing:border-box}</style></head><body><div id="root"></div><script type="module">import React from 'react';import{createRoot}from'react-dom/client';import{PassportCard}from'/src/components/PassportCard.tsx';createRoot(document.getElementById('root')).render(React.createElement(PassportCard,{data:${JSON.stringify(fixture)}}));</script></body></html>`)
  response.setHeader('Content-Type', 'text/html'); response.end(html)
}) }}],
  server: { host: '127.0.0.1', port: 0, strictPort: true, hmr: false, watch: null } })

await server.listen()
const base = `http://127.0.0.1:${server.httpServer.address().port}`
const browser = await chromium.launch({ headless: true })
const results = [], apiCalls = [], failures = []
try {
  for (const [width, height] of [[1920,1080],[1440,900],[1366,768],[1280,720],[1024,768],[768,1024],[390,844],[375,667]]) {
    const context = await browser.newContext({ viewport: { width, height }, hasTouch: width < 500, reducedMotion: 'reduce' })
    const page = await context.newPage()
    await page.route('**/api/**', route => route.abort())
    page.on('pageerror', error => { failures.push(error.message); console.error('Browser error: '+error.message) })
    page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) apiCalls.push(request.url()) })
    async function checkCard(label) {
      const errors = await page.locator('.passport-carousel').first().evaluate(card => {
        const active = card.querySelector('.passport-slide[aria-hidden=false]'), paper = active.querySelector('.passport-paper'), canvas = active.querySelector('.passport-canvas'), content = active.querySelector('.passport-page-content')
        const issues = []
        for (const [name, node] of [['paper',paper],['content',content],['canvas',canvas]]) {
          if (node.scrollHeight > node.clientHeight + 2) issues.push(`${name}: vertical overflow ${node.scrollHeight}/${node.clientHeight}`)
          if (node.scrollWidth > node.clientWidth + 2) issues.push(`${name}: horizontal overflow ${node.scrollWidth}/${node.clientWidth}`)
          if (['auto','scroll'].includes(getComputedStyle(node).overflowY) || ['auto','scroll'].includes(getComputedStyle(node).overflowX)) issues.push(`${name}: scrollable`)
        }
        const boundary = content.getBoundingClientRect(), tolerance = 2
        for (const node of content.querySelectorAll('h2,h3,p,td,.passport-text-line')) {
          const rect = node.getBoundingClientRect()
          if (rect.bottom > boundary.bottom + tolerance || rect.right > boundary.right + tolerance || rect.left < boundary.left - tolerance) issues.push(`content outside frame: ${node.tagName} ${node.textContent.slice(0,45)}`)
        }
        const rect = active.getBoundingClientRect()
        if (Math.abs(rect.width / rect.height - 841.89 / 595.276) > .002) issues.push('aspect ratio changed')
        if (document.documentElement.scrollWidth > window.innerWidth + 2) issues.push('document horizontal overflow')
        return issues
      })
      assert.deepEqual(errors, [], `${width}x${height} ${label}`)
    }
    await page.emulateMedia({reducedMotion:'reduce'})
    await page.goto(`${base}/student/dashboard`)
    await page.locator('.dashboard-passport .passport-carousel').waitFor({timeout:10000}).catch(async error => { console.log('Dashboard text: '+(await page.locator('body').innerText()).slice(0,1600)); await page.screenshot({path:path.join(output,'debug.png'),fullPage:true}); throw error })
    assert.equal(await page.locator('.hero').count(), 0)
    assert.equal(await page.locator('.passport-carousel').count(), 1)
    assert.equal(await page.locator('.stats,.dashboard-grid,.next-step,.dashboard-greeting').count(),0)
    const composition = await page.locator('.dashboard-passport').evaluate(element => {
      const main = element.closest('main').getBoundingClientRect(), card = element.getBoundingClientRect(), controls = element.querySelector('.passport-navigation').getBoundingClientRect(), actions = element.querySelector('.dashboard-passport-actions').getBoundingClientRect()
      return { centered: Math.abs(card.x + card.width/2 - main.x - main.width/2) < 2, controlsCentered: Math.abs(controls.x + controls.width/2 - card.x - card.width/2) < 2, actionsCentered: Math.abs(actions.x + actions.width/2 - card.x - card.width/2) < 2, bottom: card.bottom, top: card.top, verticalCenterError: Math.abs(card.y + card.height/2 - main.y - main.height/2) }
    })
    assert.ok(composition.centered && composition.controlsCentered && composition.actionsCentered, JSON.stringify(composition))
    if (width >= 1280) { assert.ok(composition.top >= 0 && composition.bottom <= height, JSON.stringify(composition)); assert.ok(composition.verticalCenterError < 3, JSON.stringify(composition)) }
    assert.equal(await page.locator('.dashboard-passport-actions button:disabled').count(),3)
    for (const label of ['Cover','About the Passport','Verified AI Skillset','AI Skill Supplement']) {
      await page.getByRole('button', { name: label, exact: true }).click()
      await checkCard(`dashboard ${label}`)
      if (label === 'Cover' && [1920,1440,1366,390].includes(width)) { await page.evaluate(() => window.scrollTo(0,0)); await page.screenshot({ path: path.join(output, `dashboard-${width}.png`), fullPage: true }) }
    }
    await page.goto(`${base}/verify`)
    assert.equal(await page.locator('.passport-carousel,.passport-viewport,.passport-landing').count(),0)
    await page.locator('#verification-reference').waitFor()
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2))
    await page.goto(`${base}/__passport-layout-fixture`)
    await page.locator('.passport-carousel').waitFor()
    assert.equal(await page.locator('.passport-track').evaluate(element=>getComputedStyle(element).transitionDuration),'0s')
    const count = await page.locator('.passport-slide').count()
    assert.ok(count > 4, 'Large collection must produce additional pages')
    for (let index = 0; index < count; index++) {
      await checkCard(`variable collection page ${index+1}/${count}`)
      if (index + 1 < count) await page.getByRole('button', { name: 'Next passport view', exact: true }).click()
    }
    await page.locator('.passport-carousel').focus(); await page.keyboard.press('Home')
    assert.equal(await page.locator('.passport-slide[aria-hidden=false]').getAttribute('aria-label'), `1 of ${count}: Cover`)
    if (width < 500) {
      const frame = await page.locator('.passport-viewport').boundingBox()
      const cdp = await context.newCDPSession(page)
      await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:frame.x+frame.width-30,y:frame.y+frame.height/2}]})
      await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:frame.x+30,y:frame.y+frame.height/2}]})
      await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
      await page.waitForFunction(()=>document.querySelector('.passport-slide[aria-hidden=false]').getAttribute('aria-label').startsWith('2 of'))
      await page.locator('.passport-carousel').focus(); await page.keyboard.press('Home')
      await page.getByText('Read this page as text', { exact: true }).click()
      assert.ok(await page.locator('.passport-readable dd').first().evaluate(element => parseFloat(getComputedStyle(element).fontSize) >= 16))
    }
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2))
    results.push({ width, height, largeCollectionPages: count, passed: true })
    await context.close()
    console.log(`PASS ${width}x${height}: dashboard, landing, all ${count} variable-content pages; no internal scroll or clipping`)
  }
  assert.deepEqual(failures, []); assert.deepEqual(apiCalls, [], 'Demo layout tests must never call private APIs')
  // Real React Live Mode routes, served with synthetic HTTP responses only.
  const liveServer = await createServer({ root: path.resolve(import.meta.dirname, '..'), cacheDir: path.join(output, 'live-vite-cache'), define: { 'import.meta.env.VITE_ENABLE_DEMO': JSON.stringify('false') }, optimizeDeps: { include: ['react', 'react-dom/client', 'react-router-dom'] }, server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } })
  await liveServer.listen()
  try {
    for (const [width,height] of [[1920,1080],[1440,900],[1366,768],[1280,720],[768,1024],[390,844]]) {
      const context = await browser.newContext({ viewport:{width,height}, reducedMotion:'reduce' }), page = await context.newPage()
      await page.route('**/api/**', async route => {
        const path = new URL(route.request().url()).pathname
        const data = path.endsWith('/accounts/me/') ? { email:'layout.synthetic@btu.edu.ge', role:'STUDENT', email_verified:true, student_association:'linked', capabilities:[] } : path.endsWith('/student/dashboard/') ? { profile:{first_name:'Synthetic',last_name:'Student'}, passport:{id:'00000000-0000-0000-0000-000000000001',public_reference:'00000000-0000-0000-0000-000000000001',status:'ISSUED',latest_version:{status:'ISSUED',skills:[]}} } : path.endsWith('/pdf/status/') ? {status:'ISSUED',available_for_download:true} : null
        if (!data) throw new Error('Unexpected live-layout fixture request '+path)
        await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)})
      })
      await page.goto('http://127.0.0.1:'+liveServer.httpServer.address().port+'/student/dashboard')
      await page.locator('.dashboard-passport .passport-carousel').waitFor()
      assert.equal(await page.locator('.stats,.dashboard-grid,.dashboard-greeting').count(),0)
      for (const label of ['Cover','About the Passport','Verified AI Skillset','AI Skill Supplement']) {
        await page.getByRole('button',{name:label,exact:true}).click()
        const geometry = await page.locator('.dashboard-passport').evaluate(element=>{
          const card=element.getBoundingClientRect(),main=element.closest('main').getBoundingClientRect(),active=element.querySelector('.passport-slide[aria-hidden=false]'),canvas=active.querySelector('.passport-canvas')
          return {centered:Math.abs(card.x+card.width/2-main.x-main.width/2)<2,bottom:card.bottom,overflow:document.documentElement.scrollWidth>innerWidth+2,internalOverflow:canvas.scrollWidth>canvas.clientWidth+2||canvas.scrollHeight>canvas.clientHeight+2}
        })
        assert.ok(geometry.centered&&!geometry.overflow&&!geometry.internalOverflow,JSON.stringify(geometry))
        if(width>=1280) assert.ok(geometry.bottom<=height,JSON.stringify(geometry))
      }
      if(width===1366) await page.screenshot({path:path.join(output,'student-live-fixture-1366.png'),fullPage:true})
      await context.close()
      console.log('PASS synthetic Live Mode landing '+width+'x'+height+': all sections centered, controls visible, no overflow')
    }
  } finally { await liveServer.close() }

  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ results, failures, apiCalls }, null, 2))
  console.log(`Screenshots and report: ${output}`)
} finally { await browser.close(); await server.close() }
