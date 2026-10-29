// Real browser/React/Django/PG; only GIS and Google's certificate keys are synthetic.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { pathToFileURL } from 'node:url'
const dir = process.env.BTU_LIVE_TEST_ARTIFACTS, base = process.env.BTU_LIVE_TEST_URL
assert.equal(new URL(base).hostname, '127.0.0.1')
const fixture = JSON.parse(await fs.readFile(path.join(dir, 'preview-private.json'), 'utf8'))
const key = await fs.readFile(path.join(dir, 'google-test-private.pem'))
const { chromium } = await import(pathToFileURL(path.join(process.env.BTU_BROWSER_TOOLS, 'node_modules/playwright/index.mjs')).href)
const browser = await chromium.launch({ headless: true, executablePath: process.env.BTU_BROWSER_EXECUTABLE })
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const calls = [], errors = [], checks = []
let step = 'initialize', lastChallenge
const page = await context.newPage()
page.on('pageerror', e => errors.push(e.name))
page.on('response', async r => {
  if (new URL(r.url()).pathname.startsWith('/api/')) calls.push({ path: new URL(r.url()).pathname, method: r.request().method(), status: r.status() })
  if (new URL(r.url()).pathname === '/api/accounts/google/challenge/' && r.status() === 200) lastChallenge = await r.json()
})
await context.route('**/*', route => {
  const url = new URL(route.request().url())
  if (url.origin === base) return route.continue()
  if (url.href === 'https://accounts.google.com/gsi/client') return route.fulfill({ contentType: 'text/javascript', body: `
    window.google={accounts:{id:{initialize(options){window.__syntheticGIS=options},renderButton(el){
      const b=document.createElement('button');b.type='button';b.textContent='Continue with Google';b.dataset.testid='synthetic-google';
      b.onclick=()=>window.__syntheticGIS.callback({credential:window.__syntheticCredential});el.append(b)
    },disableAutoSelect(){}}}};` })
  return route.abort()
})
async function submit() { await page.locator('form button:not([type="button"])').click() }
async function google(intent = 'login', changes = {}) {
  await page.getByRole('button', { name: intent === 'link' ? 'Link Google account' : 'Continue with Google', exact: true }).click()
  await page.getByTestId('synthetic-google').waitFor()
  const nonce = await page.evaluate(() => window.__syntheticGIS.nonce)
  const now = Math.floor(Date.now() / 1000)
  const claims = { iss: 'https://accounts.google.com', aud: '123456789-synthetic.apps.googleusercontent.com',
    sub: 'synthetic-browser-google-subject', email: fixture.studentEmail, email_verified: true, hd: 'btu.edu.ge',
    nonce, iat: now - 1, exp: now + 300, ...changes }
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'synthetic-key', typ: 'JWT' })).toString('base64url')
  const payload = header + '.' + Buffer.from(JSON.stringify(claims)).toString('base64url')
  const token = payload + '.' + crypto.sign('RSA-SHA256', Buffer.from(payload), key).toString('base64url')
  await page.evaluate(value => { window.__syntheticCredential = value }, token)
  const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/accounts/google/authenticate/' && r.request().method() === 'POST')
  await page.getByTestId('synthetic-google').click()
  return { response: await response, token, challenge: lastChallenge }
}
try {
  step = 'unlinked Google user and strict hosted domain'
  await page.goto(base + '/student/login')
  let attempt = await google()
  assert.equal(attempt.response.status(), 403)
  await page.getByRole('alert').getByText(/not linked/).waitFor()
  attempt = await google('login', { hd: 'other.edu.ge' })
  assert.equal(attempt.response.status(), 400)
  await page.getByRole('alert').getByText(/hd=btu.edu.ge/).waitFor()
  checks.push('Unlinked identity receives actionable OTP instructions; wrong hosted domain rejected')

  step = 'real OTP then Google binding'
  await page.locator('#auth-email-student').fill(fixture.studentEmail)
  const before = (await fs.stat(path.join(dir, 'preview-private.json'))).mtimeMs
  await submit(); await page.locator('#student-otp').waitFor()
  let code
  for (let i = 0; i < 150; i++) {
    const file = path.join(dir, 'preview-private.json'); code = JSON.parse(await fs.readFile(file, 'utf8')).otp
    if (/^[0-9]{6}$/.test(code ?? '') && (await fs.stat(file)).mtimeMs > before) break
    code = undefined; await new Promise(r => setTimeout(r, 50))
  }
  assert.match(code ?? '', /^[0-9]{6}$/)
  await page.locator('#student-otp').fill(code); await submit(); await page.waitForURL(base + '/student/dashboard')
  await page.getByRole('link', { name: 'Google sign-in settings', exact: true }).click()
  attempt = await google('link')
  assert.equal(attempt.response.status(), 200)
  await page.getByRole('status').getByText(/Google account linked/).waitFor()
  await page.screenshot({ path: path.join(dir, 'google-linked.png'), fullPage: true })
  checks.push('Real email OTP authentication followed by explicit secure Google subject binding')

  step = 'logout and returning Google session'
  await page.goto(base + '/student/dashboard'); await page.locator('.passport-carousel').waitFor()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await page.waitForURL(base + '/student/login')
  attempt = await google()
  assert.equal(attempt.response.status(), 200)
  await page.waitForURL(base + '/student/dashboard'); await page.locator('.passport-carousel').waitFor()
  await page.reload(); await page.locator('.passport-carousel').waitFor()
  checks.push('Returning Google subject creates/restores existing student session and Passport navigation')

  step = 'CSRF and replay'
  const body = { challenge_id: attempt.challenge.challenge_id, credential: attempt.token }
  assert.equal((await context.request.post(base + '/api/accounts/google/authenticate/', { data: body })).status(), 403)
  const csrf = (await (await context.request.get(base + '/api/accounts/csrf/')).json()).csrfToken
  const replay = await context.request.post(base + '/api/accounts/google/authenticate/', { data: body, headers: { 'X-CSRFToken': csrf } })
  assert.equal(replay.status(), 400)
  assert.equal((await replay.json()).code, 'GOOGLE_INVALID_CHALLENGE')
  checks.push('Native frontend sends CSRF; missing CSRF and replayed challenge rejected')

  step = 'fresh OTP requirement and role isolation'
  await page.getByRole('link', { name: 'Google sign-in settings', exact: true }).click()
  await page.getByRole('button', { name: 'Link Google account', exact: true }).click()
  await page.getByRole('alert').getByText(/within the last five minutes/).waitFor()
  await page.goto(base + '/student/dashboard')
  await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await page.waitForURL(base + '/student/login')
  await page.goto(base + '/student/dashboard'); await page.waitForURL(base + '/student/login')
  await page.screenshot({ path: path.join(dir, 'google-student-login.png'), fullPage: true })
  await page.goto(base + '/admin/login')
  assert.equal(await page.getByRole('button', { name: 'Continue with Google', exact: true }).count(), 0)
  await page.locator('#auth-email-administrator').fill(fixture.adminEmail)
  await page.locator('#admin-password').fill(fixture.adminPassword); await submit(); await page.waitForURL(base + '/admin/dashboard')
  await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await page.waitForURL(base + '/admin/login')
  checks.push('Google session cannot authorize linking; logout invalidates access; administrator password login remains isolated')
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(dir, 'google-auth-browser-results.json'), JSON.stringify({ passed: true, synthetic: true,
    mockedResponses: false, googleGISAndKeysMocked: true, liveGoogleTested: false, checks, calls, errors }, null, 2))
  console.log(`PASS Google auth Chrome/Django: ${checks.length} groups, ${calls.length} actual API responses; Google GIS/keys synthetic, no live Google.`)
} catch (error) {
  await fs.writeFile(path.join(dir, 'google-auth-browser-failure.json'), JSON.stringify({ step, error: error.message, checks, calls }, null, 2))
  await page.screenshot({ path: path.join(dir, 'google-auth-failure.png'), fullPage: true }).catch(() => {})
  console.error(`FAIL Google auth browser at ${step}: ${error.message}`); process.exitCode = 1
} finally { await context.close(); await browser.close() }
