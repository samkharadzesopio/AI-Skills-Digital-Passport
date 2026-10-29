// Owned loopback browser regression. API replies are fixtures; no real login is attempted.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { preview } from 'vite'

if (!process.env.BTU_BROWSER_TOOLS || !process.env.BTU_NAV_ARTIFACTS) {
  throw new Error('Provide an isolated Playwright installation and run-owned artifact directory')
}
const { chromium } = await import(pathToFileURL(path.join(process.env.BTU_BROWSER_TOOLS, 'node_modules/playwright/index.mjs')).href)
const server = await preview({ preview: { host: '127.0.0.1', port: 0, strictPort: true } })
const base = `http://127.0.0.1:${server.httpServer.address().port}`
const results = [], errors = []
let browser
try {
  browser = await chromium.launch({ headless: true, executablePath: process.env.BTU_BROWSER_EXECUTABLE || undefined })
  await fs.mkdir(process.env.BTU_NAV_ARTIFACTS, { recursive: true })
  for (const width of [1440, 1024, 768, 375, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' })
    // Isolate UI routing and anonymous role guards from unavailable production services.
    await context.route('**/api/**', route => route.fulfill({ status: 403, contentType: 'application/json', body: '{}' }))
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    assert.equal((await page.goto(base + '/verify')).status(), 200)
    const student = page.getByRole('link', { name: 'Student sign in', exact: true })
    const admin = page.getByRole('link', { name: 'Administrator sign in', exact: true })
    for (const link of [student, admin]) {
      await link.waitFor({ state: 'visible' })
      const bounds = await link.boundingBox()
      assert.ok(bounds.height >= 44 && bounds.width > 50)
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true,
      `No horizontal overflow at ${width}px`)
    await page.screenshot({ path: path.join(process.env.BTU_NAV_ARTIFACTS, `verify-${width}.png`) })
    await page.locator('.verify-language').click()
    assert.equal(await page.locator('.verify-sign-in-nav a').count(), 2)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true,
      `No Georgian overflow at ${width}px`)
    await page.screenshot({ path: path.join(process.env.BTU_NAV_ARTIFACTS, `verify-ka-${width}.png`) })
    await page.locator('.verify-language').click()
    await student.click()
    await page.waitForURL('**/student/login?auth=live')
    await page.locator('.auth-form-panel').waitFor()
    assert.equal(await page.getByText('Open demo workspace', { exact: true }).count(), 0)
    assert.equal((await page.reload()).status(), 200)
    await page.locator('.auth-form-panel').waitFor()
    await page.goto(base + '/verify')
    await page.getByRole('link', { name: 'Administrator sign in', exact: true }).click()
    await page.waitForURL('**/admin/login?auth=live')
    await page.locator('#admin-password').waitFor({ state: 'visible' })
    assert.equal((await page.reload()).status(), 200)
    await page.locator('#admin-password').waitFor({ state: 'visible' })
    await page.goto(base + '/admin/dashboard')
    await page.waitForURL('**/admin/login')
    await page.locator('#admin-password').waitFor({ state: 'visible' })
    await page.goto(base + '/student/dashboard')
    await page.waitForURL('**/student/login')
    await page.locator('.auth-form-panel').waitFor()
    results.push({ width, buttonsVisible: true, englishAndGeorgianNoOverflow: true,
      studentAndAdminNavigation: true, loginRefresh: true, anonymousDashboardDenied: true })
    await context.close()
  }
  assert.deepEqual(errors, [])
  const report = { passed: true, target: 'owned loopback production build', api: 'anonymous fixtures', results }
  await fs.writeFile(path.join(process.env.BTU_NAV_ARTIFACTS, 'results.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} finally {
  await browser?.close()
  await new Promise(resolve => server.httpServer.close(resolve))
}
