// Native Chrome -> React/Vite -> Django -> owned PostgreSQL. No API interception.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { createServer } from 'vite'

assert.ok(process.env.BTU_AUTOMATION_FIXTURE && process.env.BTU_BROWSER_TOOLS && process.env.BTU_TEST_VITE_CACHE)
const fixture = JSON.parse(process.env.BTU_AUTOMATION_FIXTURE)
delete process.env.BTU_AUTOMATION_FIXTURE
assert.equal(fixture.synthetic, true)
assert.equal(new URL(process.env.BTU_DEV_API_TARGET).hostname, '127.0.0.1')
const output = process.env.BTU_TEST_ARTIFACTS || process.env.BTU_TEST_VITE_CACHE
await fs.mkdir(output, { recursive: true })
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, cacheDir: process.env.BTU_TEST_VITE_CACHE,
  server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } })
await server.listen()
const base = `http://127.0.0.1:${server.httpServer.address().port}`
const { chromium } = await import(pathToFileURL(path.join(process.env.BTU_BROWSER_TOOLS, 'node_modules/playwright/index.mjs')).href)
const browser = await chromium.launch({ headless: true, executablePath: process.env.BTU_BROWSER_EXECUTABLE || undefined })
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' })
const page = await context.newPage(), calls = [], errors = [], journeys = []
page.on('pageerror', e => errors.push(e.name))
page.on('response', r => { const u = new URL(r.url()); if (u.pathname.startsWith('/api/')) calls.push({ path: u.pathname, method: r.request().method(), status: r.status() }) })
let step = 'initialize'
const automatic = `/api/integrations/import/automatic-sources/${fixture.profileId}/`
async function source(rows) { await fs.writeFile(fixture.sourceFile + '.next', JSON.stringify([['Synthetic approved awards'], [], [], ['Student ID', 'Record ID', 'Skill ID', 'Date Earned', 'Institutional Approval'], ...rows])); await fs.rename(fixture.sourceFile + '.next', fixture.sourceFile) }
async function credentials(count) {
  for (let i = 0; i < 200; i++) {
    const response = await context.request.get(base + '/api/admin/credentials/')
    assert.equal(response.status(), 200)
    const data = await response.json()
    if (data.count === count) return data
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('EXPECTED_CREDENTIAL_COUNT')
}
async function select() { await page.locator('#automatic-source').selectOption(fixture.profileId) }
async function refresh() { await page.getByRole('button', { name: 'Refresh automatic sources', exact: true }).click(); await select() }
async function enable() {
  await page.locator('#automatic-interval').fill('60')
  await page.locator('#automatic-authorization').fill('SYNTHETIC-CONTINUING-AUTHORITY')
  await page.getByLabel('I authorize periodic processing of this approved source under its existing institutional policy.').check()
  const response = page.waitForResponse(r => new URL(r.url()).pathname === automatic && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Enable automatic source', exact: true }).click()
  assert.equal((await response).status(), 200)
  await page.getByText('Automatic polling enabled for this approved source.', { exact: true }).waitFor()
}
try {
  step = 'Session and default off'
  await page.goto(base + '/admin/login')
  await page.locator('#auth-email-administrator').fill(fixture.adminEmail)
  await page.locator('#admin-password').fill(fixture.adminPassword)
  await page.locator('form button:not([type="button"])').click()
  await page.waitForURL(base + '/admin/dashboard')
  await page.goto(base + '/admin/imports')
  await page.getByRole('heading', { name: 'Automatic confirmed-skill synchronization', exact: true }).waitFor()
  await select()
  assert.equal(await page.getByRole('button', { name: 'Enable automatic source', exact: true }).isDisabled(), true)
  assert.equal((await (await context.request.get(base + automatic.replace(/[^/]+\/$/, ''))).json()).results[0].enabled, false)
  await credentials(0)
  // All mutation requests still use the existing session+CSRF boundary.
  assert.equal((await context.request.post(base + automatic, { data: { enabled: false } })).status(), 403)
  journeys.push('Existing administrator session, default off, explicit authorization gating and CSRF rejection')

  step = 'Enable and pending exclusion'
  await enable()
  await page.reload(); await select()
  await page.getByRole('heading', { name: 'synthetic-auto-awards · Enabled', exact: true }).waitFor()
  for (let i = 0; i < 100; i++) {
    const rows = (await (await context.request.get(base + automatic + 'history/')).json()).results
    if (rows.some(row => row.state === 'EXCLUDED')) break
    if (i === 99) throw new Error('NO_EXCLUDED_POLL')
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  await credentials(0)
  journeys.push('Explicit enable persists after reload; polling sees pending evidence and excludes issuance')

  step = 'New confirmed discovery and source validation'
  const row = fixture.row
  await source([row, row, [row[0], 'SYNTHETIC-PENDING', row[2], row[3], 'PENDING'],
    [row[0], 'SYNTHETIC-REJECTED', row[2], row[3], 'REJECTED'], ['UNKNOWN', 'SYNTHETIC-INVALID', row[2], row[3], 'CONFIRMED']])
  await credentials(1)
  const first = (await (await context.request.get(base + automatic + 'history/')).json()).results.find(r => r.state === 'COMPLETED')
  assert.ok(first)
  assert.deepEqual([first.counts.valid_records, first.counts.duplicate_records, first.counts.review_records, first.counts.invalid_records], [1, 1, 2, 1])
  await source([row, [row[0], 'SYNTHETIC-SECOND', row[2], '2026-01-02', 'CONFIRMED']])
  await credentials(2)
  await refresh()
  await page.getByRole('button', { name: 'Inspect automatic history', exact: true }).click()
  await page.getByRole('region', { name: 'Automatic source history' }).waitFor()
  await page.getByRole('button', { name: 'Refresh automatic history', exact: true }).click()
  await page.getByRole('region', { name: 'Automatic source history' }).getByRole('heading', { name: /COMPLETED/ }).first().waitFor()
  await page.screenshot({ path: path.join(output, 'automation-history-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true)
  await page.screenshot({ path: path.join(output, 'automation-history-mobile.png'), fullPage: true })
  journeys.push('Automatic new CONFIRMED records create real awards; duplicates, pending, rejected and unknown students excluded; persisted history on desktop/mobile')

  step = 'Disable and retained manual workflow'
  const disabled = page.waitForResponse(r => new URL(r.url()).pathname === automatic && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Disable automatic source', exact: true }).click()
  assert.equal((await disabled).status(), 200)
  await page.getByText('Automatic polling disabled for this source.', { exact: true }).waitFor()
  await source([row, [row[0], 'SYNTHETIC-SECOND', row[2], '2026-01-02', 'CONFIRMED'], [row[0], 'SYNTHETIC-MANUAL', row[2], '2026-01-03', 'CONFIRMED']])
  await new Promise(resolve => setTimeout(resolve, 600))
  await credentials(2)
  await page.reload(); await select()
  await page.getByRole('heading', { name: 'synthetic-auto-awards · Disabled', exact: true }).waitFor()
  await page.locator('#import-source').selectOption('BTU_GOOGLE_SHEETS')
  await page.locator('#import-profile').selectOption(fixture.profileId)
  const previewResponse = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/google-sheets/preview/') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Preview incoming records', exact: true }).click()
  const response = await previewResponse
  assert.equal(response.status(), 201)
  const preview = await response.json()
  assert.equal(preview.report.valid_records, 1)
  await page.getByLabel('I reviewed this snapshot and confirm importing its eligible records.').check()
  const confirmed = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/confirm/') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Confirm reviewed import', exact: true }).click()
  assert.equal((await confirmed).status(), 200)
  await credentials(3)
  journeys.push('Disable persists and prevents new discovery; creator-owned digest-bound manual Google preview/confirmation remains available')
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'automation-chrome-results.json'), JSON.stringify({ synthetic: true, mockedResponses: false, googleAccess: false, journeys, calls, errors }, null, 2))
  console.log(`PASS Chrome automation: ${journeys.length} journey groups, ${calls.length} actual API responses`)
} catch (error) {
  await fs.writeFile(path.join(output, 'automation-chrome-failure.json'), JSON.stringify({ step, error: error.message, journeys, calls }, null, 2))
  await page.screenshot({ path: path.join(output, 'automation-chrome-failure.png'), fullPage: true }).catch(() => {})
  console.error(`FAIL Chrome automation at ${step}: ${error.message}`)
  process.exitCode = 1
} finally {
  await context.close(); await browser.close(); await server.close()
}
