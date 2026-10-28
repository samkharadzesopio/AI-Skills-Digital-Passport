// Actual Chrome -> Vite -> Django acceptance. No API responses are intercepted.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import crypto from 'node:crypto'
const artifacts = process.env.BTU_LIVE_TEST_ARTIFACTS
if (!artifacts || !process.env.BTU_BROWSER_TOOLS) throw new Error('Use an owned synthetic preview and isolated browser tools')
const base = process.env.BTU_LIVE_TEST_URL || 'http://127.0.0.1:5175'
if (new URL(base).hostname !== '127.0.0.1') throw new Error('Loopback only')
const runtime = JSON.parse(await fs.readFile(path.join(artifacts, 'preview-runtime.json'), 'utf8'))
if (runtime.synthetic !== true) throw new Error('Synthetic preview required')
const privateFixture = JSON.parse(await fs.readFile(path.join(artifacts, 'preview-private.json'), 'utf8'))
const { chromium } = await import(pathToFileURL(path.join(process.env.BTU_BROWSER_TOOLS, 'node_modules/playwright/index.mjs')).href)
const browser = await chromium.launch({ headless: true, executablePath: process.env.BTU_BROWSER_EXECUTABLE || undefined })
const requests = [], journeys = [], layouts = [], measurements = [], errors = [], contexts = []
let step = 'initialize', page, publicPage
async function context(options = {}) {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', acceptDownloads: true, ...options })
  contexts.push(c)
  c.on('page', p => {
    p.on('pageerror', error => errors.push({ name: error.name }))
    p.on('response', response => {
      const u = new URL(response.url())
      if (u.pathname.startsWith('/api/')) requests.push({ path: u.pathname, method: response.request().method(), status: response.status() })
    })
  })
  return c
}
async function submit(p) { await p.locator('form button:not([type="button"])').click() }
async function result(p, status) { await p.locator(`[data-verification-status="${status}"]`).waitFor() }
async function loginStudent(p) {
  await p.goto(base + '/student/login')
  await p.locator('#auth-email-student').fill(privateFixture.studentEmail)
  const previousMailTime = (await fs.stat(path.join(artifacts, 'preview-private.json'))).mtimeMs
  await submit(p); await p.locator('#student-otp').waitFor()
  let code
  for (let i = 0; i < 100; i++) {
    code = JSON.parse(await fs.readFile(path.join(artifacts, 'preview-private.json'), 'utf8')).otp
    if (/^[0-9]{6}$/.test(code ?? '') && (await fs.stat(path.join(artifacts, 'preview-private.json'))).mtimeMs > previousMailTime) break
    code = undefined
    await new Promise(resolve => setTimeout(resolve, 25))
  }
  assert.match(code ?? '', /^[0-9]{6}$/)
  await p.locator('#student-otp').fill(code); await submit(p)
  await p.waitForURL(base + '/student/dashboard')
  await p.locator('.dashboard-passport .passport-carousel').waitFor()
}
async function upload(p, bytes, status) {
  await p.goto(base + '/verify/upload')
  await p.locator('#verification-pdf').setInputFiles({ name: 'synthetic-passport.pdf', mimeType: 'application/pdf', buffer: bytes })
  const response = p.waitForResponse(r => new URL(r.url()).pathname === '/api/verification/document/' && r.request().method() === 'POST')
  await submit(p); assert.equal((await response).status(), 200)
  await result(p, status)
}
try {
  step = 'student OTP and session'
  const studentContext = await context(); page = await studentContext.newPage()
  await loginStudent(page)
  await page.reload(); await page.locator('.dashboard-passport .passport-carousel').waitFor()
  await page.getByRole('button', { name: 'Share Passport', exact: true }).waitFor()
  // The card can render before its registered-PDF metadata request completes.
  // Wait for the actual enabled control; retain all assertions/default budgets.
  await page.waitForFunction(() => [...document.querySelectorAll('button')]
    .some(button => button.textContent.trim() === 'Share Passport' && !button.disabled))
  assert.equal(await page.locator('.stats,.dashboard-grid,.dashboard-greeting,.support,.next-step').count(), 0)
  assert.doesNotMatch(await page.locator('main').innerText(), /Welcome,|competency overview|Recent credentials|Save Preferences/)
  const navigation = page.getByRole('navigation', { name: 'Student navigation' })
  assert.deepEqual(await navigation.locator('a').evaluateAll(nodes => nodes.map(n => n.getAttribute('href'))),
    ['/student/dashboard', '/student/skills', '/student/passport/versions', '/student/gap-analyzer', '/verify'])
  assert.doesNotMatch(await page.locator('.sidebar').innerText(), /Credentials|Profile & Settings|AI Playground|University Admin|Passport Details/)
  assert.match(await page.locator('.student-identity').innerText(), /Read-only Student identity/)
  assert.equal(await page.getByRole('button', { name: 'Share Passport', exact: true }).isEnabled(), true)
  assert.match(await page.locator('.passport-frame-footer').first().innerText(), /Blockchain verified.*Local Anvil/)
  journeys.push('Real OTP, restored session, simplified sidebar, read-only identity and authoritative Anvil proof')

  step = 'sharing and original PDF'
  await page.getByRole('button', { name: 'Share Passport', exact: true }).click()
  const share = await page.locator('#passport-share').inputValue()
  assert.equal(new URL(share).origin, base); assert.ok(share.includes(runtime.passportReference))
  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download PDF', exact: true }).click()
  const download = await downloadEvent, bytes = await fs.readFile(await download.path())
  assert.equal(bytes.subarray(0, 5).toString(), '%PDF-')
  const registered = await fs.readFile(runtime.pdfPath)
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), crypto.createHash('sha256').update(registered).digest('hex'))
  journeys.push('Current PDF download matches registered bytes; current-only share link')

  step = 'Student routes and exact history'
  await navigation.getByRole('link', { name: 'My Skills', exact: true }).click()
  await page.getByRole('heading', { name: 'Synthetic AI Reasoning', exact: true }).waitFor()
  await page.goto(base + '/student/achievements'); await page.getByRole('heading', { name: 'Verified achievements', exact: true }).waitFor()
  await page.goto(base + '/student/profile'); await page.getByText('Academic identity is maintained by the university.', { exact: true }).waitFor()
  assert.equal(await page.locator('main input,main textarea,main select,main form').count(), 0)
  await page.goto(base + '/student/credentials/' + runtime.credentialId)
  await page.getByRole('heading', { name: 'Credential details', exact: true }).waitFor()
  await page.getByText(runtime.credentialReference, { exact: false }).first().waitFor()
  await page.goto(base + '/student/history'); await page.waitForURL(base + '/student/passport/versions')
  await page.getByRole('link', { name: 'Version 1', exact: true }).waitFor()
  await page.getByRole('link', { name: 'Version 2', exact: true }).waitFor()
  await page.getByRole('link', { name: 'Version 1', exact: true }).click()
  await page.getByRole('heading', { name: 'Issued Passport version', exact: true }).waitFor()
  await page.getByText('Historical version; a newer version is published', { exact: false }).waitFor()
  const historicalEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download registered PDF', exact: true }).click()
  const historical = await fs.readFile(await (await historicalEvent).path())
  assert.ok(requests.some(r => r.path.includes('/versions/' + runtime.historicalVersionId + '/pdf/download/') && r.status === 200))
  await page.goto(base + '/student/gap-analyzer'); await page.getByRole('heading', { name: 'Coming Soon', exact: true }).waitFor()
  assert.equal(await page.locator('main input,main form').count(), 0)
  journeys.push('Real My Skills, read-only profile, achievement/credential deep links, history, exact-version PDF and Coming Soon')

  step = 'anonymous reference and PDF verification'
  const anonymous = await context(); publicPage = await anonymous.newPage()
  const publicRequests = []
  publicPage.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) publicRequests.push(request)
  })
  await publicPage.goto(share)
  assert.equal(await publicPage.locator('#reference-method').getAttribute('type'), 'hidden')
  assert.equal(await publicPage.locator('select').count(), 0)
  await submit(publicPage); await result(publicPage, 'valid')
  assert.match(await publicPage.locator('[data-fact="blockchain"]').innerText(), /Blockchain proof verified/)
  await upload(publicPage, bytes, 'valid')
  await upload(publicPage, historical, 'outdated')
  await publicPage.goto(base + '/verify/qr/passport-version:' + runtime.historicalVersionReference)
  await submit(publicPage); await result(publicPage, 'outdated')
  await publicPage.goto(base + '/verify')
  assert.equal(await publicPage.locator('.passport-carousel,iframe,embed').count(), 0)
  for (const request of publicRequests) {
    assert.ok(new URL(request.url()).pathname.startsWith('/api/verification/'))
    const headers = await request.allHeaders()
    for (const key of ['cookie', 'authorization', 'x-csrftoken']) assert.equal(headers[key], undefined)
  }
  journeys.push('Real anonymous current/historical reference and PDF verification through native frontend multipart; no credentials or sample preview')

  step = 'Admin route preservation'
  const administrator = await context(), admin = await administrator.newPage()
  await admin.goto(base + '/admin/login')
  await admin.locator('#auth-email-administrator').fill(privateFixture.adminEmail)
  await admin.locator('#admin-password').fill(privateFixture.adminPassword); await submit(admin)
  await admin.waitForURL(base + '/admin/dashboard')
  for (const [route, content] of [
    ['/admin/dashboard', 'Administration dashboard'], ['/admin/students', 'University Student records'],
    ['/admin/skills', 'Skill catalog'], ['/admin/course-mappings', 'Approved course mappings'],
    ['/admin/credentials', 'Credentials'], ['/admin/imports', 'Persisted import history'],
    ['/admin/classroom-sync', 'SIMULATED'], ['/admin/audit-logs', 'General security-audit reading'],
    ['/admin/students/' + runtime.studentId + '/passport', 'Issued Passport versions'],
  ]) { step = 'Admin route ' + route; await admin.goto(base + route); await admin.getByText(content, { exact: false }).first().waitFor() }
  journeys.push('Real Admin password session, dashboard, Students, credentials, catalog, mappings, imports/sync, audit and Passport management')

  step = 'mobile Admin and public verification layouts'
  await admin.setViewportSize({ width: 390, height: 844 })
  await admin.goto(base + '/admin/dashboard')
  await admin.getByRole('heading', { name: 'Administration dashboard', exact: true }).waitFor()
  assert.ok(await admin.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
  await admin.screenshot({ path: path.join(artifacts, 'live-admin-390.png'), fullPage: true })
  await publicPage.setViewportSize({ width: 390, height: 844 })
  for (const route of ['/verify', '/verify/upload']) {
    await publicPage.goto(base + route)
    assert.ok(await publicPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
  }
  await publicPage.screenshot({ path: path.join(artifacts, 'live-verify-390.png'), fullPage: true })

  step = 'live responsive layouts'
  await page.goto(base + '/student/dashboard')
  for (const [width, height] of [[1440, 900], [1366, 768], [1280, 720], [1024, 768], [768, 1024], [390, 844], [375, 667]]) {
    await page.setViewportSize({ width, height }); await page.locator('.passport-carousel').waitFor()
    for (const title of ['Cover', 'About the Passport', 'Verified AI Skillset', 'AI Skill Supplement']) {
      step = `live responsive layouts ${width}x${height} ${title}`
      await page.getByRole('button', { name: title, exact: true }).click()
      const measure = await page.locator('.dashboard-passport').evaluate(element => {
        const main = element.closest('main').getBoundingClientRect(), r = element.getBoundingClientRect()
        const slide = element.querySelector('.passport-slide[aria-hidden=false]')
        return { centered: Math.abs(r.x + r.width / 2 - main.x - main.width / 2) < 3,
          overflow: document.documentElement.scrollWidth > innerWidth + 2,
          clipped: [...slide.querySelectorAll('.passport-canvas,.passport-paper,.passport-page-content')].some(n => n.scrollWidth > n.clientWidth + 2 || n.scrollHeight > n.clientHeight + 2),
          bottom: r.bottom }
      })
      measurements.push({ width, height, title, ...measure })
      assert.ok(measure.centered && !measure.overflow && !measure.clipped)
      if (width >= 1280) assert.ok(measure.bottom <= height + 2)
    }
    await page.getByRole('button', { name: 'Cover', exact: true }).click()
    if (width < 500) { await page.getByRole('button', { name: 'Toggle navigation' }).click(); await page.getByRole('link', { name: 'My Skills', exact: true }).click(); await page.getByRole('heading', { name: 'Recognized skills', exact: true }).waitFor(); await page.goto(base + '/student/dashboard'); await page.locator('.passport-carousel').waitFor() }
    await page.screenshot({ path: path.join(artifacts, `live-student-${width}.png`), fullPage: true })
    layouts.push({ width, height, passed: true })
  }
  step = 'secure logout'
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await page.waitForURL(base + '/student/login')
  await page.goto(base + '/student/dashboard'); await page.waitForURL(base + '/student/login')
  assert.equal((await studentContext.cookies()).some(cookie => cookie.name === 'sessionid'), false)

  step = 'Passport revocation heading with valid supporting credentials'
  const revocationStatus = await admin.evaluate(async ({ studentId, reference }) => {
    const rows = await (await fetch('/api/admin/passports/?student_id=' + studentId)).json()
    const passport = rows.results.find(p => p.public_reference === reference)
    if (!passport) return 404
    await fetch('/api/accounts/csrf/')
    const csrf = document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.slice('csrftoken='.length)
    const response = await fetch('/api/admin/passports/' + passport.id + '/revoke/', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf || '') },
      body: JSON.stringify({ idempotency_key: 'SYNTHETIC-BROWSER-REVOKE', reason: 'Synthetic browser revocation check' }),
    })
    return response.status
  }, { studentId: runtime.studentId, reference: runtime.passportReference })
  assert.equal(revocationStatus, 200)
  await publicPage.setViewportSize({ width: 1440, height: 900 })
  await upload(publicPage, bytes, 'revoked')
  await publicPage.getByRole('heading', { name: 'Passport revoked', exact: true }).waitFor()
  // Cancelled public identities deliberately skip credential assessment. Check
  // that public fact unchanged, and verify the underlying credential privately.
  assert.equal(await publicPage.locator('[data-fact="credential-validity"]').innerText(), 'Could not be established')
  const supportingCredential = await admin.evaluate(async id => {
    const response = await fetch('/api/admin/credentials/' + id + '/')
    const data = await response.json()
    return { httpStatus: response.status, status: data.status, validity: data.validity_status }
  }, runtime.credentialId)
  assert.deepEqual(supportingCredential, { httpStatus: 200, status: 'ISSUED', validity: 'VALID' })
  assert.doesNotMatch(await publicPage.locator('main').innerText(), /Credential support has been revoked/)
  assert.doesNotMatch(await publicPage.locator('[data-fact="blockchain"]').innerText(), /proof verified by the backend for the current/)
  await publicPage.screenshot({ path: path.join(artifacts, 'live-passport-revoked.png'), fullPage: true })
  journeys.push('Real Passport revocation/PDF: distinct identity heading, public credential assessment unavailable, authorized Credential API still VALID, no current blockchain badge')
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(artifacts, 'browser-acceptance-results.json'), JSON.stringify({ passed: true, synthetic: true, mockedResponses: false, journeys, layouts, requests }, null, 2))
  console.log(`PASS real Chrome/Django acceptance: ${journeys.length} journeys, ${layouts.length} live viewports, ${requests.length} API responses; native public PDF verification, critical routes and logout passed.`)
} catch (error) {
  if (step.startsWith('live responsive layouts')) await page.screenshot({ path: path.join(artifacts, 'live-layout-failure.png'), fullPage: true })
  const assertionLine = /check-passport-browser\.mjs:(\d+):\d+/.exec(error.stack || '')?.[1]
  await fs.writeFile(path.join(artifacts, 'browser-acceptance-failure.json'), JSON.stringify({ step, errorType: error.name, assertionLine, journeys, layouts, measurements, requests }, null, 2))
  console.error('FAIL real browser acceptance at: ' + step + ' (' + error.name + ')')
  process.exitCode = 1
} finally {
  for (const c of contexts) await c.close()
  await browser.close()
}
