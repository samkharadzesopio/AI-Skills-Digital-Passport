// Actual Chrome/React/Django/PostgreSQL; only FedCM identities and provider keys are synthetic.
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
const calls = [], errors = [], checks = [], blocked = []
let step = 'initialize', lastChallenge, lastToken, changes = {}
await context.exposeFunction('syntheticWorkspaceCredential', options => {
  assert.equal(options.identity.mode, 'active'); assert.equal(options.mediation, 'required')
  const provider = options.identity.providers[0]
  assert.equal(provider.configURL, 'https://accounts.google.com/gsi/fedcm.json')
  assert.equal(provider.clientId, '123456789-synthetic.apps.googleusercontent.com')
  assert.equal(provider.domainHint, 'btu.edu.ge')
  assert.equal(provider.params.nonce, provider.nonce)
  assert.equal(provider.params.response_type, 'id_token', 'Google FedCM must request an ID token, not an authorization code')
  assert.equal(provider.params.scope, 'email profile openid')
  assert.equal(provider.params.ss_domain, base, 'Google must receive the actual frontend origin')
  const now = Math.floor(Date.now() / 1000)
  const claims = { iss: 'https://accounts.google.com', aud: provider.clientId, sub: 'synthetic-browser-new-subject',
    email: fixture.studentEmail, email_verified: true, hd: 'btu.edu.ge', nonce: provider.params.nonce, iat: now - 1, exp: now + 300, ...changes }
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'synthetic-key', typ: 'JWT' })).toString('base64url')
  const payload = header + '.' + Buffer.from(JSON.stringify(claims)).toString('base64url')
  lastToken = payload + '.' + crypto.sign('RSA-SHA256', Buffer.from(payload), key).toString('base64url')
  return { token: lastToken, type: 'identity' }
})
await context.addInitScript(() => {
  window.IdentityCredential = class IdentityCredential {}
  Object.defineProperty(navigator.credentials, 'get', { value: options => window.syntheticWorkspaceCredential(options) })
})
await context.route('**/*', route => {
  const url = new URL(route.request().url())
  if (url.origin === base) return route.continue()
  blocked.push(url.origin); return route.abort()
})
const page = await context.newPage()
page.on('pageerror', e => errors.push(e.name))
page.on('response', async r => {
  if (new URL(r.url()).pathname.startsWith('/api/')) calls.push({ path: new URL(r.url()).pathname, method: r.request().method(), status: r.status() })
  if (new URL(r.url()).pathname === '/api/accounts/google/challenge/' && r.status() === 200) lastChallenge = await r.json()
})
async function google(claims = {}) {
  changes = claims
  const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/accounts/google/authenticate/' && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  return { response: await response, token: lastToken, challenge: lastChallenge }
}
async function logout() {
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await page.waitForURL(base + '/student/login')
}
try {
  step = 'one pink sign-in control and exact Workspace rejection'
  await page.goto(base + '/student/login')
  await page.getByRole('heading', { name: 'Student sign in', exact: true }).waitFor()
  assert.equal(await page.locator('.auth-form-panel input').count(), 0)
  assert.equal(await page.locator('.auth-form-panel button').count(), 1)
  await page.getByRole('link', { name: 'Public verification', exact: true }).waitFor()
  const button = page.getByRole('button', { name: 'Sign in', exact: true })
  assert.match(await button.getAttribute('class'), /button primary auth-submit/)
  assert.equal(await button.evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(229, 0, 113)')
  let attempt = await google({ hd: 'other.edu.ge' })
  assert.equal(attempt.response.status(), 400)
  await page.getByRole('alert').getByText(/verified @btu.edu.ge/).waitFor()
  checks.push('Existing layout, one pink Sign in button, no OTP inputs; invalid hosted domain rejected by real backend')

  step = 'first login with historical email remains a separate empty portal'
  attempt = await google()
  assert.equal(attempt.response.status(), 200)
  await page.waitForURL(base + '/student/dashboard')
  await page.getByRole('heading', { name: 'No Passport records are linked yet' }).waitFor()
  assert.equal(await page.locator('.passport-carousel').count(), 0)
  const empty = await context.request.get(base + '/api/accounts/portal/')
  assert.deepEqual(await empty.json(), { email: fixture.studentEmail, records_linked: false, mapping_pending: true })
  for (const resource of ['dashboard', 'passport', 'credentials', 'skills']) {
    assert.equal((await context.request.get(base + '/api/student/' + resource + '/')).status(), 403)
  }
  assert.equal((await context.request.get(base + '/api/admin/students/')).status(), 403)
  await page.screenshot({ path: path.join(dir, 'google-empty-portal.png'), fullPage: true })
  checks.push('New subject gets own empty portal; matching historical email never grants private records or admin privileges')

  step = 'session restoration and nonce/CSRF protection'
  await page.reload(); await page.getByRole('heading', { name: 'No Passport records are linked yet' }).waitFor()
  const body = { challenge_id: attempt.challenge.challenge_id, credential: attempt.token }
  assert.equal((await context.request.post(base + '/api/accounts/google/authenticate/', { data: body })).status(), 403)
  const csrf = (await (await context.request.get(base + '/api/accounts/csrf/')).json()).csrfToken
  const replay = await context.request.post(base + '/api/accounts/google/authenticate/', { data: body, headers: { 'X-CSRFToken': csrf } })
  assert.equal(replay.status(), 400); assert.equal((await replay.json()).code, 'GOOGLE_INVALID_CHALLENGE')
  await logout()
  attempt = await google(); assert.equal(attempt.response.status(), 200)
  await page.waitForURL(base + '/student/dashboard'); await page.getByRole('heading', { name: 'No Passport records are linked yet' }).waitFor()
  checks.push('Same subject restores personal session; refresh, logout, CSRF and one-use nonce work')

  step = 'trusted existing identity restores real Passport'
  await logout()
  attempt = await google({ sub: 'synthetic-browser-linked-subject' })
  assert.equal(attempt.response.status(), 200)
  await page.waitForURL(base + '/student/dashboard'); await page.locator('.passport-carousel').waitFor()
  await page.reload(); await page.locator('.passport-carousel').waitFor()
  await page.screenshot({ path: path.join(dir, 'google-linked-passport.png'), fullPage: true })
  checks.push('Previously trusted subject restores linked Passport without OTP or email attachment')

  step = 'administrator password authentication unchanged and public verification available'
  await logout(); await page.goto(base + '/admin/login')
  await page.locator('#auth-email-administrator').fill(fixture.adminEmail)
  await page.locator('#admin-password').fill(fixture.adminPassword)
  await page.locator('form button:not([type="button"])').click(); await page.waitForURL(base + '/admin/dashboard')
  await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await page.waitForURL(base + '/admin/login')
  await page.goto(base + '/student/login'); await button.waitFor()
  await page.screenshot({ path: path.join(dir, 'google-student-login.png'), fullPage: true })
  await page.getByRole('link', { name: 'Public verification', exact: true }).click(); await page.waitForURL(base + '/verify')
  checks.push('Administrator password login and Public verification navigation remain available')
  assert.deepEqual(errors, []); assert.deepEqual(blocked, [])
  await fs.writeFile(path.join(dir, 'google-auth-browser-results.json'), JSON.stringify({ passed: true, synthetic: true,
    mockedResponses: false, fedcmAndKeysSynthetic: true, liveGoogleTested: false, checks, calls, errors }, null, 2))
  console.log(`PASS Workspace portal Chrome/Django: ${checks.length} groups, ${calls.length} actual API responses; FedCM/keys synthetic, no live Google.`)
} catch (error) {
  await fs.writeFile(path.join(dir, 'google-auth-browser-failure.json'), JSON.stringify({ step, error: error.message, checks, calls }, null, 2))
  await page.screenshot({ path: path.join(dir, 'google-auth-failure.png'), fullPage: true }).catch(() => {})
  console.error(`FAIL Workspace portal browser at ${step}: ${error.message}`); process.exitCode = 1
} finally { await context.close(); await browser.close() }
