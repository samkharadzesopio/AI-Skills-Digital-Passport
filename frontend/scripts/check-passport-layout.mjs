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
  for (const [width, height] of [[1440,900],[1920,1080],[1366,768],[1024,768],[768,1024],[390,844],[375,667]]) {
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
    assert.equal(await page.locator('.stats').count(), 0)
    for (const label of ['Cover','About the Passport','Verified AI Skillset','AI Skill Supplement']) {
      await page.getByRole('button', { name: label, exact: true }).click()
      await checkCard(`dashboard ${label}`)
      if (label === 'Cover' && [1920,390].includes(width)) { await page.evaluate(() => window.scrollTo(0,0)); await page.screenshot({ path: path.join(output, `dashboard-${width}.png`), fullPage: true }) }
    }
    await page.goto(`${base}/verify`)
    assert.equal(await page.locator('.passport-carousel').count(), 0)
    await page.locator('a[href="/verify/upload"]').first().waitFor()
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
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ results, failures, apiCalls }, null, 2))
  console.log(`Screenshots and report: ${output}`)
} finally { await browser.close(); await server.close() }
