import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { pathToFileURL } from 'node:url'

// Checks existing operator-started Vite servers, never starts a substitute server.
const studentUrl = process.env.BTU_STUDENT_URL || 'http://127.0.0.1:5174'
const verificationUrl = process.env.BTU_VERIFICATION_URL || 'http://127.0.0.1:5175'
const tooling = process.env.BTU_BROWSER_TOOLS || path.join(os.tmpdir(), 'btu-passport-browser-tests')
const { chromium } = await import(pathToFileURL(path.join(tooling, 'node_modules/playwright/index.mjs')).href)
const output = path.join(os.tmpdir(), 'btu-actual-website-results')
await fs.mkdir(output, { recursive: true })
const fixture = JSON.parse(await fs.readFile(new URL('./fixtures/backend-bec0d83.json', import.meta.url)))
const valid = fixture.responses.find(row => row.body.status === 'VALID').body
const samples = [
  ['VALID', valid, 'Valid passport document'],
  ['INVALID', { ...valid, status: 'INVALID', blockchain: undefined }, 'Invalid record or document'],
  ['REVOKED', fixture.responses.find(row => row.body.status === 'REVOKED').body, 'Revoked passport or credential'],
  ['REPLACED', fixture.responses.find(row => row.body.status === 'REPLACED').body, 'Replaced passport'],
  ['UNAVAILABLE', null, 'Verification unavailable'],
]
const browser = await chromium.launch({ headless: true }), results = []
try {
  for (const [width, height] of [[1920,1080],[1440,900],[1366,768],[1280,720],[768,1024],[390,844]]) {
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' }), page = await context.newPage()
    await page.goto(`${studentUrl}/student/dashboard`)
    await page.locator('.dashboard-passport .passport-carousel').waitFor()
    assert.equal(await page.locator('.stats,.dashboard-grid,.dashboard-greeting,.support,.next-step').count(), 0)
    assert.doesNotMatch(await page.locator('main').innerText(), /Welcome back|learning journey|competency overview|Learning momentum|Recent credentials/i)
    for (const title of ['Cover', 'About the Passport', 'Verified AI Skillset', 'AI Skill Supplement']) {
      await page.getByRole('button', { name: title, exact: true }).click()
      const metrics = await page.locator('.dashboard-passport').evaluate(element => {
        const main = element.closest('main').getBoundingClientRect(), rect = element.getBoundingClientRect(), active = element.querySelector('.passport-slide[aria-hidden=false]')
        return { centered: Math.abs(rect.x + rect.width / 2 - main.x - main.width / 2) < 2, bottom: rect.bottom, horizontal: document.documentElement.scrollWidth > innerWidth + 2, clipped: [...active.querySelectorAll('.passport-canvas,.passport-paper,.passport-page-content')].some(node => node.scrollWidth > node.clientWidth + 2 || node.scrollHeight > node.clientHeight + 2) }
      })
      assert.ok(metrics.centered && !metrics.horizontal && !metrics.clipped, JSON.stringify(metrics))
      if (width >= 1280) assert.ok(metrics.bottom <= height, JSON.stringify(metrics))
    }
    await page.getByRole('button', { name: 'Cover', exact: true }).click()
    await page.screenshot({ path: path.join(output, `student-${width}.png`), fullPage: true })
    await page.goto(`${verificationUrl}/verify`)
    await page.locator('#verification-reference').waitFor()
    assert.equal(await page.locator('.passport-carousel,.passport-viewport,.passport-landing,iframe,embed').count(), 0)
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
    await page.screenshot({ path: path.join(output, `verification-${width}.png`), fullPage: true })
    results.push({ width, height, student: true, verificationForm: true })
    await context.close()
    console.log(`PASS actual running website ${width}x${height}: passport-only student; no public passport visualization`)
  }
  // Synthetic responses intercepted in fresh test contexts; these are not Django successes.
  for (const width of [1366,390]) for (const [status, body, heading] of samples) {
    const context = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 768 } }), page = await context.newPage()
    await page.route('**/api/verification/passport/*/', async route => {
      assert.ok(!route.request().headers().authorization && !route.request().headers().cookie)
      if (!body) return route.abort('failed')
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    })
    await page.goto(`${verificationUrl}/verify`)
    await page.locator('#verification-reference').fill(`passport:${valid.blockchain.passport_reference}`)
    await page.locator('button[type=submit],button.verify-submit').click()
    await page.waitForURL('**/verify/result')
    if (body) await page.getByRole('heading', { name: heading, exact: true }).waitFor()
    else await page.locator('.verify-failure').waitFor()
    assert.equal(await page.locator('.passport-carousel,.passport-viewport,.passport-landing,iframe,embed').count(), 0)
    if (status !== 'VALID') assert.equal(await page.getByText('Blockchain Verified', { exact: true }).count(), 0)
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
    await page.screenshot({ path: path.join(output, `result-${status.toLowerCase()}-${width}.png`), fullPage: true })
    results.push({ width, status, syntheticResponse: true, passed: true })
    await context.close()
    console.log(`PASS running verification ${width}px ${status}: fixture response, compact result only`)
  }
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ studentUrl, verificationUrl, results }, null, 2))
  console.log(`Screenshots/report: ${output}. No real Django or chain confirmation tested.`)
} finally { await browser.close() }
