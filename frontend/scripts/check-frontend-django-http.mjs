// Native Chrome -> React/Vite -> Django -> owned PostgreSQL; no response interception.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { pathToFileURL } from 'node:url'
import { createServer } from 'vite'

assert.ok(process.env.BTU_FRONTEND_DJANGO_FIXTURE && process.env.BTU_TEST_VITE_CACHE && process.env.BTU_BROWSER_TOOLS, 'Use ops/run_isolated_tests.py --frontend-django')
const fixture = JSON.parse(process.env.BTU_FRONTEND_DJANGO_FIXTURE)
delete process.env.BTU_FRONTEND_DJANGO_FIXTURE
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
const contexts = [], calls = [], errors = [], journeys = [], bodies = []
let step = 'start', page
async function context() {
  const c = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true, reducedMotion: 'reduce' })
  contexts.push(c)
  c.on('page', p => {
    p.on('pageerror', e => errors.push(e.name))
    p.on('response', response => {
      const url = new URL(response.url())
      if (url.pathname.startsWith('/api/')) {
        assert.equal(url.origin, base)
        calls.push({ path: url.pathname, method: response.request().method(), status: response.status() })
        if (response.headers()['content-type']?.includes('application/json')) bodies.push(response.json().catch(() => null))
      }
    })
  })
  return c
}
async function submit(p) { await p.locator('form button:not([type="button"])').click() }
async function route(p, url) { await p.goto(base + url); await p.locator('main').waitFor() }
async function csrf(c) { return (await (await c.request.get(base + '/api/accounts/csrf/')).json()).csrfToken }
async function contains(p, text) { await p.getByText(text, { exact: false }).first().waitFor() }
async function reference(p, value) {
  await route(p, '/verify/reference')
  await p.locator('#verification-reference').fill(value)
  await submit(p)
}
try {
  const ac = await context(), admin = await ac.newPage()
  page = admin
  assert.equal((await ac.request.get(base + '/api/admin/students/')).status(), 403)
  step = 'Admin session and management/navigation'
  await route(admin, '/admin/login')
  await admin.locator('#auth-email-administrator').fill(fixture.adminEmail)
  await admin.locator('#admin-password').fill(fixture.adminPassword)
  await submit(admin); await admin.waitForURL(base + '/admin/dashboard')
  await contains(admin, 'Total issued credentials')
  await admin.getByRole('link', { name: 'Students', exact: true }).click()
  await contains(admin, fixture.studentName)
  for (const [url, label] of [['/admin/skills', 'Synthetic integration skill'], ['/admin/course-mappings', 'Activity-to-Skill Mapping'],
    ['/admin/credentials', 'Credentials'], ['/admin/audit-logs', 'General security-audit reading']]) {
    await route(admin, url); await contains(admin, label)
    assert.doesNotMatch(await admin.locator('main').innerText(), /Nino|DEMO-2026/)
  }
  journeys.push('Admin session, Students, catalog, course-only mappings, credentials and honest audit-API boundary')
  step = 'Reviewed awarded-skill Excel preview'
  await route(admin, '/admin/imports')
  await admin.locator('#import-profile').selectOption(fixture.officialProfileId)
  await admin.locator('#reviewed-workbook').setInputFiles(fixture.originalFormatWorkbook)
  const originalResponse = admin.waitForResponse(r => new URL(r.url()).pathname.endsWith('/import/excel/preview/') && r.request().method() === 'POST')
  await admin.getByRole('button', { name: 'Preview incoming records', exact: true }).click()
  const original = await originalResponse
  assert.equal(original.status(), 201)
  const originalPreview = await original.json()
  assert.equal(originalPreview.report.valid_records, 0)
  assert.equal(originalPreview.report.review_records, 1)
  assert.equal(originalPreview.report.rows[0].code, 'INSTITUTIONAL_CONFIRMATION_REQUIRED')
  assert.equal(await admin.getByRole('button', { name: 'Confirm reviewed import', exact: true }).isDisabled(), true)
  journeys.push('Original 20-column BTU header shape parses as awards; sync output cannot authorize issuance, so independent approval is required')
  await admin.locator('#import-profile').selectOption(fixture.profileId)
  await admin.locator('#reviewed-workbook').setInputFiles(fixture.workbook)
  const before = admin.waitForResponse(r => new URL(r.url()).pathname.endsWith('/import/excel/preview/') && r.request().method() === 'POST')
  await admin.getByRole('button', { name: 'Preview incoming records', exact: true }).click()
  const previewResponse = await before
  assert.equal(previewResponse.status(), 201)
  const preview = await previewResponse.json()
  assert.equal(preview.report.header_row, 4)
  assert.deepEqual([preview.report.valid_records, preview.report.duplicate_records, preview.report.invalid_records, preview.report.review_records], [1, 1, 3, 2])
  assert.deepEqual(preview.report.columns, { external_student_id: 1, source_event_id: 10, skill_code: 11, earned_on: 16, approval_status: 21 })
  assert.equal(await admin.getByRole('button', { name: 'Confirm reviewed import', exact: true }).isDisabled(), true)
  const credentials = await (await ac.request.get(base + '/api/admin/credentials/')).json()
  assert.equal(credentials.count, 0)
  const target = base + `/api/integrations/import/previews/${preview.id}/confirm/`
  const payload = { confirm: true, snapshot_sha256: preview.snapshot_sha256 }, token = await csrf(ac)
  assert.equal((await ac.request.post(target, { data: payload })).status(), 403)
  const mismatch = await ac.request.post(target, { headers: { 'X-CSRFToken': token }, data: { ...payload, snapshot_sha256: '0'.repeat(64) } })
  assert.equal(mismatch.status(), 409); assert.equal((await mismatch.json()).code, 'PREVIEW_DIGEST_MISMATCH')
  await admin.screenshot({ path: path.join(output, 'admin-reviewed-awards.png'), fullPage: true })
  await admin.setViewportSize({ width: 390, height: 844 })
  assert.ok(await admin.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
  await admin.screenshot({ path: path.join(output, 'admin-reviewed-awards-mobile.png'), fullPage: true })
  await admin.setViewportSize({ width: 1440, height: 1000 })
  journeys.push('Real XLSX row-4 aliases, awards/duplicates/invalid/pending/rejected decisions; zero credentials before CSRF/digest confirmation')
  step = 'Confirmation, persistence, history and replay'
  await admin.getByLabel('I reviewed this snapshot and confirm importing its eligible records.').check()
  const confirmedResponse = admin.waitForResponse(r => r.url() === target && r.request().method() === 'POST')
  await admin.getByRole('button', { name: 'Confirm reviewed import', exact: true }).click()
  const confirmed = await confirmedResponse
  assert.equal(confirmed.status(), 200)
  assert.deepEqual(confirmed.request().postDataJSON(), payload)
  const result = await confirmed.json()
  assert.equal(result.result.issued, 1)
  await contains(admin, 'Persisted import result')
  await contains(admin, `Import ${result.result.import_id}`)
  const replay = await ac.request.post(target, { headers: { 'X-CSRFToken': token }, data: payload })
  assert.equal(replay.status(), 200); assert.deepEqual((await replay.json()).result, result.result)
  await admin.getByRole('button', { name: 'Preview incoming records', exact: true }).click()
  await contains(admin, 'ALREADY_IMPORTED')
  await admin.getByRole('button', { name: `Inspect import ${result.result.import_id} events`, exact: true }).click()
  await route(admin, `/admin/students/${fixture.studentId}`)
  await contains(admin, 'Synthetic integration skill')
  journeys.push('One explicit award/credential, persisted partial import history, duplicate replay and Student evidence')
  step = 'Configured Google interface without external access'
  await route(admin, '/admin/imports')
  await admin.locator('#import-source').selectOption('BTU_GOOGLE_SHEETS')
  await admin.locator('#import-profile').selectOption(fixture.googleProfileId)
  const googleResponse = admin.waitForResponse(r => new URL(r.url()).pathname.endsWith('/import/google-sheets/preview/'))
  await admin.getByRole('button', { name: 'Preview incoming records', exact: true }).click()
  const google = await googleResponse
  assert.equal(google.status(), 503); assert.equal((await google.json()).code, 'GOOGLE_SOURCE_UNAVAILABLE')
  await contains(admin, 'No successful import is assumed')
  journeys.push('Google profile/request contract and safe missing-credential error; real Google API NOT RUN')
  step = 'Student OTP, Passport, achievements and native PDF download'
  const sc = await context(), student = await sc.newPage()
  page = student
  await route(student, '/student/login')
  const studentCsrf = (await (await student.request.get(base + '/api/accounts/csrf/')).json()).csrfToken
  assert.equal((await student.request.post(base + '/api/accounts/otp/request/', {data:{email:fixture.studentEmail},headers:{'X-CSRFToken':studentCsrf}})).status(),202)
  let code
  for (let i = 0; i < 80; i++) {
    try { code = await fs.readFile(fixture.mailbox, 'utf8'); break } catch { await new Promise(resolve => setTimeout(resolve, 50)) }
  }
  assert.match(code || '', /^[0-9]{6}$/)
  assert.equal((await student.request.post(base + '/api/accounts/otp/verify/', {data:{email:fixture.studentEmail,code},headers:{'X-CSRFToken':studentCsrf}})).status(),200)
  await student.goto(base + '/student/dashboard')
  await student.waitForURL(base + '/student/dashboard')
  await student.getByText('Read-only Student identity and record details', { exact: true }).click()
  await contains(student, fixture.studentName)
  const passport = await (await sc.request.get(base + '/api/student/passport/')).json()
  assert.equal(passport.blockchain.blockchain_verified, false)
  assert.equal(passport.blockchain.status, 'NOT_CONFIGURED')
  assert.equal(await student.getByRole('button', { name: 'Share Passport', exact: true }).isDisabled(), true)
  step = 'Student earned skills and PDF controls'
  await route(student, '/student/achievements'); await contains(student, 'Synthetic integration skill')
  await route(student, '/student/passport'); await contains(student, 'Blockchain not configured')
  await student.getByRole('button', { name: /^(Generate Passport PDF|Download registered PDF)$/ }).first().waitFor()
  const generate = student.getByRole('button', { name: 'Generate Passport PDF', exact: true })
  if (await generate.count()) await generate.click()
  const download = student.waitForEvent('download')
  await student.getByRole('button', { name: 'Download registered PDF', exact: true }).click()
  const downloaded = await download, pdfPath = await downloaded.path(), bytes = await fs.readFile(pdfPath)
  assert.equal(bytes.subarray(0, 5).toString(), '%PDF-')
  await student.screenshot({ path: path.join(output, 'student-backend-passport.png'), fullPage: true })
  for (const width of [1440, 1024, 768, 390]) {
    await student.setViewportSize({ width, height: 1000 })
    await route(student, '/student/dashboard')
    await contains(student, 'Sharing requires a confirmed current Passport')
    assert.ok(await student.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
    assert.doesNotMatch(await student.locator('main').innerText(), /Nino|DEMO-2026|Blockchain verified/)
  }
  assert.equal((await sc.request.get(base + '/api/admin/students/')).status(), 403)
  journeys.push('Real Student OTP/session, DB-backed Passport/skills, native PDF download, four responsive widths; no blockchain success inferred')
  step = 'Anonymous public reference/PDF results'
  const pc = await context(), publicPage = await pc.newPage()
  page = publicPage
  const known = pc.request.get(base + `/api/verification/passport/${passport.public_reference}/`)
  await reference(publicPage, passport.public_reference)
  const knownResult = await (await known).json()
  await publicPage.locator('[data-verification-status]').waitFor()
  assert.equal(await publicPage.locator('[data-verification-status]').getAttribute('data-verification-status'), knownResult.status.toLowerCase())
  assert.equal(knownResult.blockchain.blockchain_verified, false)
  await reference(publicPage, crypto.randomUUID())
  await publicPage.locator('[data-verification-status="not_found"]').waitFor()
  await route(publicPage, '/verify/upload')
  await publicPage.locator('#verification-pdf').setInputFiles({ name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: bytes })
  const originalPdf = publicPage.waitForResponse(r => new URL(r.url()).pathname === '/api/verification/document/' && r.request().method() === 'POST')
  await submit(publicPage); await publicPage.locator('[data-verification-status]').waitFor()
  assert.equal((await (await originalPdf).json()).authentic, true)
  await route(publicPage, '/verify/upload')
  await publicPage.locator('#verification-pdf').setInputFiles({ name: 'modified.pdf', mimeType: 'application/pdf', buffer: Buffer.concat([bytes, Buffer.from('\n%modified')]) })
  const modifiedPdf = publicPage.waitForResponse(r => new URL(r.url()).pathname === '/api/verification/document/' && r.request().method() === 'POST')
  await submit(publicPage); await publicPage.locator('[data-verification-status="unverifiable"]').waitFor()
  assert.equal((await (await modifiedPdf).json()).authentic, false)
  journeys.push('Public known/unknown references show actual backend verdicts; original PDF accepted and modified bytes rejected, without proof fabrication')
  step = 'Final evidence and browser errors'
  const responses = await Promise.all(bodies)
  assert.equal(responses.some(body => body?.blockchain?.blockchain_verified === true), false)
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'chrome-django-results.json'), JSON.stringify({ synthetic: true, demo: false, mockedResponses: false,
    googleApiAccess: false, blockchainAcceptance: 'NOT_RUN', journeys, calls, errors }, null, 2))
  console.log(`PASS real Chrome/React/Django: ${journeys.length} journey groups, ${calls.length} API responses; synthetic PostgreSQL awards/PDF, no API interception or Google/chain acceptance.`)
} catch (error) {
  await fs.writeFile(path.join(output, 'chrome-django-failure.json'), JSON.stringify({ step, errorType: error.name, journeys, calls }, null, 2))
  if (page) await page.screenshot({ path: path.join(output, 'chrome-django-failure.png'), fullPage: true }).catch(() => {})
  console.error(`FAIL real Chrome/Django at ${step}: ${error.name}`)
  process.exitCode = 1
} finally {
  for (const c of contexts) await c.close()
  await browser.close(); await server.close()
}
