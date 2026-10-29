// Actual Chrome -> Live React -> Django -> owned PostgreSQL/Anvil. No API mocks.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { pathToFileURL } from 'node:url'

const ready = JSON.parse(await fs.readFile(process.env.BTU_REVIEW_READY, 'utf8'))
assert.equal(ready.synthetic, true); assert.equal(ready.mode, 'LIVE')
const base = ready.frontend
assert.equal(new URL(base).hostname, '127.0.0.1')
const privateFixture = JSON.parse(await fs.readFile(ready.private_fixture, 'utf8'))
const output = path.dirname(process.env.BTU_REVIEW_READY)
const { chromium } = await import(pathToFileURL(path.join(process.env.BTU_BROWSER_TOOLS, 'node_modules/playwright/index.mjs')).href)
const browser = await chromium.launch({ headless: true, executablePath: process.env.BTU_BROWSER_EXECUTABLE })
const contexts = [], calls = [], errors = [], checks = []
let page, step = 'start'
async function tab() {
  const c = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
  contexts.push(c)
  const p = await c.newPage()
  p.on('pageerror', e => errors.push(e.name))
  p.on('response', r => { const u = new URL(r.url()); if (u.pathname.startsWith('/api/')) calls.push({ path: u.pathname, status: r.status(), method: r.request().method() }) })
  return p
}
async function waitFor(check) {
  for (let i = 0; i < 120; i++) { if (await check()) return; await new Promise(r => setTimeout(r, 500)) }
  throw new Error('Acceptance deadline expired')
}
async function submit(p) { await p.locator('form button:not([type="button"])').click() }
async function write(p, url, data) {
  return p.evaluate(async ({ url, data }) => {
    const bootstrap = await fetch('/api/accounts/csrf/'); const csrf = (await bootstrap.json()).csrfToken
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf }, body: JSON.stringify(data) })
    return response.status
  }, { url, data })
}
async function upload(p, bytes, status) {
  await p.goto(base + '/verify/upload')
  await p.locator('#verification-pdf').setInputFiles({ name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: bytes })
  await submit(p); await p.locator(`[data-verification-status="${status}"]`).waitFor()
}
try {
  step = 'administrator login and source authorization'
  const admin = page = await tab()
  await admin.goto(base + '/admin/login')
  await admin.locator('#auth-email-administrator').fill(privateFixture.adminEmail)
  await admin.locator('#admin-password').fill(privateFixture.adminPassword); await submit(admin)
  await admin.waitForURL(base + '/admin/dashboard')
  assert.doesNotMatch(await admin.locator('body').innerText(), /DEMO PREVIEW/)
  const old = await (await admin.request.get(base + '/api/admin/students/' + (JSON.parse(await fs.readFile(path.join(path.dirname(ready.private_fixture), 'preview-runtime.json'), 'utf8'))).studentId + '/')).json()
  const oldPassport = old.passport
  const oldPdf = await (await admin.request.get(base + `/api/admin/passports/${oldPassport.id}/pdf/download/`)).body()
  const oldHash = crypto.createHash('sha256').update(oldPdf).digest('hex')
  await admin.goto(base + '/admin/imports')
  await admin.locator('#automatic-source').selectOption(ready.profile_id)
  await admin.locator('#automatic-interval').fill('60')
  await admin.locator('#automatic-authorization').fill('SYNTHETIC-TEAM-ACCEPTANCE')
  await admin.getByLabel('I authorize periodic processing of this approved source under its existing institutional policy.').check()
  await admin.getByRole('button', { name: 'Enable automatic source', exact: true }).click()
  await admin.getByText('Automatic polling enabled for this approved source.', { exact: true }).waitFor()
  checks.push('Actual administrator login, Live imports and explicit source authorization')

  step = 'automatic award and actual Anvil confirmation'
  const studentId = old.profile.id
  let updated
  await waitFor(async () => {
    updated = await (await admin.request.get(base + '/api/admin/students/' + studentId + '/')).json()
    return updated.passport?.latest_version?.id !== oldPassport.latest_version?.id && updated.passport?.blockchain?.blockchain_verified === true
  })
  assert.equal(updated.passport.id, oldPassport.id)
  checks.push('Scheduled synthetic CONFIRMED discovery, permanent Passport identity and actual confirmed Anvil proof')

  step = 'student OTP and actual Passport PDF'
  const student = page = await tab()
  await student.goto(base + '/student/login')
  await student.locator('#auth-email-student').fill(privateFixture.studentEmail)
  const prior = (await fs.stat(ready.private_fixture)).mtimeMs
  await submit(student); await student.locator('#student-otp').waitFor()
  let code
  await waitFor(async () => { const value = JSON.parse(await fs.readFile(ready.private_fixture, 'utf8')); code = value.otp; return /^[0-9]{6}$/.test(code || '') && (await fs.stat(ready.private_fixture)).mtimeMs > prior })
  await student.locator('#student-otp').fill(code); await submit(student)
  await student.waitForURL(base + '/student/dashboard')
  await student.locator('.passport-carousel').waitFor()
  await student.getByRole('button', { name: 'Share Passport', exact: true }).click()
  const share = await student.locator('#passport-share').inputValue()
  assert.equal(new URL(share).origin, base)
  const event = student.waitForEvent('download')
  await student.getByRole('button', { name: 'Download PDF', exact: true }).click()
  const bytes = await fs.readFile(await (await event).path())
  assert.equal(bytes.subarray(0, 5).toString(), '%PDF-')
  await student.goto(base + '/student/skills')
  await student.getByRole('heading', { name: ready.skill_name, exact: true }).waitFor()
  await student.goto(base + '/student/passport/versions')
  await student.getByRole('link', { name: 'Version 1', exact: true }).waitFor()
  checks.push('Real student OTP/session, awarded skill, actual Passport, registered PDF download, share and history')

  step = 'public verification, history immutability and authorization'
  const anonymous = page = await tab()
  await anonymous.goto(share); await submit(anonymous)
  await anonymous.locator('[data-verification-status="valid"]').waitFor()
  await upload(anonymous, bytes, 'valid')
  await upload(anonymous, Buffer.concat([bytes, Buffer.from('\n%altered')]), 'unverifiable')
  const historic = await (await admin.request.get(base + `/api/admin/passports/${oldPassport.id}/pdf/download/?version_id=${oldPassport.latest_version.id}`)).body()
  assert.equal(crypto.createHash('sha256').update(historic).digest('hex'), oldHash)
  assert.equal((await anonymous.request.get(base + '/api/student/passport/')).status(), 403)
  const automatic = `/api/integrations/import/automatic-sources/${ready.profile_id}/`
  assert.equal(await write(student, automatic, { enabled: false }), 403)
  assert.equal((await admin.request.post(base + automatic, { data: { enabled: false } })).status(), 403)
  await admin.getByRole('button', { name: 'Disable automatic source', exact: true }).click()
  await admin.getByText('Automatic polling disabled for this source.', { exact: true }).waitFor()
  checks.push('Public original VALID, altered UNVERIFIABLE, historical bytes/hash unchanged, anonymous/student/CSRF denials and administrative disable')
  await student.goto(base + '/student/dashboard'); await student.locator('.passport-carousel').waitFor()
  await student.screenshot({ path: path.join(output, 'live-student.png'), fullPage: true })
  await admin.screenshot({ path: path.join(output, 'live-admin.png'), fullPage: true })
  await anonymous.goto(share); await submit(anonymous); await anonymous.locator('[data-verification-status="valid"]').waitFor()
  await anonymous.screenshot({ path: path.join(output, 'live-public.png'), fullPage: true })
  await student.getByRole('button', { name: 'Sign out', exact: true }).click(); await student.waitForURL(base + '/student/login')
  await student.goto(base + '/student/dashboard'); await student.waitForURL(base + '/student/login')
  await admin.getByRole('button', { name: 'Sign out', exact: true }).click(); await admin.waitForURL(base + '/admin/login')
  checks.push('Student and administrator logout invalidate protected navigation')
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'team-acceptance.json'), JSON.stringify({ passed: true, synthetic: true, mockedResponses: false, checks, calls, errors, public_url: share }, null, 2))
  console.log(`PASS integrated Chrome acceptance: ${checks.length} groups, ${calls.length} actual API responses`)
} catch (error) {
  await fs.writeFile(path.join(output, 'team-acceptance-failure.json'), JSON.stringify({ step, error: error.message, checks, calls }, null, 2))
  await page?.screenshot({ path: path.join(output, 'team-failure.png'), fullPage: true }).catch(() => {})
  console.error(`FAIL integrated Chrome acceptance at ${step}: ${error.message}`)
  process.exitCode = 1
} finally {
  for (const context of contexts) await context.close()
  await browser.close()
}
