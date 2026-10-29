// Actual Chrome/React/Django/PostgreSQL; only the documented GIS SDK callback and provider keys are synthetic.
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
let step = 'initialize', lastChallenge, lastToken, changes = {}, credentialMode = 'jwt', sdkLoads = 0
await context.exposeFunction('syntheticWorkspaceCredential', options => {
  assert.equal(options.client_id, '123456789-synthetic.apps.googleusercontent.com')
  assert.equal(options.hd, 'btu.edu.ge')
  assert.equal(options.ux_mode, 'popup')
  assert.equal(options.auto_select, false)
  assert.equal(options.use_fedcm_for_button, true)
  assert.equal(options.nonce, lastChallenge.nonce, 'GIS must receive the server challenge nonce unchanged')
  assert.equal(Object.hasOwn(options, 'response_type'), false, 'GIS handles the ID-token protocol')
  const now = Math.floor(Date.now() / 1000)
  const claims = { iss: 'https://accounts.google.com', aud: options.client_id, sub: 'synthetic-browser-new-subject',
    email: fixture.studentEmail, email_verified: true, hd: 'btu.edu.ge', nonce: options.nonce, iat: now - 1, exp: now + 300, ...changes }
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'synthetic-key', typ: 'JWT' })).toString('base64url')
  const payload = header + '.' + Buffer.from(JSON.stringify(claims)).toString('base64url')
  lastToken = payload + '.' + crypto.sign('RSA-SHA256', Buffer.from(payload), key).toString('base64url')
  if (credentialMode === 'native') return { token: lastToken }
  if (credentialMode === 'object') return { credential: { id_token: lastToken } }
  if (credentialMode === 'access') return { credential: 'synthetic-opaque-access-token' }
  if (credentialMode === 'wrapped') return { credential: JSON.stringify({ id_token: lastToken }) }
  return { credential: lastToken, token: 'synthetic-opaque-native-token', select_by: 'btn' }
})
await context.addInitScript(() => {
  Object.defineProperty(navigator, 'credentials', { value: { get() { throw new Error('Hand-written native FedCM must not be called') } } })
})
const syntheticSdk = `(() => {
  let configuration;
  window.google = { accounts: { id: {
    initialize(options) { configuration = options },
    renderButton(element, options) {
      if (options.type !== 'standard' || options.text !== 'signin_with') throw new Error('Use the supported GIS button');
      const { callback, ...settings } = configuration;
      const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Sign in with Google';
      button.onclick = async () => {
        const response = await window.syntheticWorkspaceCredential(settings);
        callback(response); callback(response);
      };
      element.replaceChildren(button);
    },
    disableAutoSelect() {}
  } } };
})()`
await context.route('**/*', route => {
  const url = new URL(route.request().url())
  if (url.origin === base) return route.continue()
  if (url.href === 'https://accounts.google.com/gsi/client') {
    sdkLoads++
    return route.fulfill({ status: 200, contentType: 'text/javascript', body: syntheticSdk })
  }
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
  await page.getByRole('button', { name: 'Sign in with Google', exact: true }).click()
  return { response: await response, token: lastToken, challenge: lastChallenge }
}
async function logout() {
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await page.waitForURL(base + '/student/login')
}
try {
  step = 'supported GIS button and strict ID-token credential transport'
  await page.goto(base + '/student/login')
  await page.getByRole('heading', { name: 'Student sign in', exact: true }).waitFor()
  assert.equal(await page.locator('.auth-form-panel input').count(), 0)
  const button = page.getByRole('button', { name: 'Sign in with Google', exact: true })
  await button.waitFor()
  assert.equal(await page.locator('.auth-form-panel button').count(), 1)
  await page.getByRole('link', { name: 'Public verification', exact: true }).waitFor()
  for (const mode of ['native', 'object', 'access', 'wrapped']) {
    credentialMode = mode
    const before = calls.filter(call => call.path === '/api/accounts/google/authenticate/').length
    const challengeId = lastChallenge.challenge_id
    await button.click()
    await page.getByRole('alert').getByText(/could not be completed/).waitFor()
    await button.waitFor()
    assert.notEqual(lastChallenge.challenge_id, challengeId, 'Invalid SDK output must get a new challenge')
    assert.equal(calls.filter(call => call.path === '/api/accounts/google/authenticate/').length, before, 'Non-JWT SDK output must never reach Django')
  }
  credentialMode = 'jwt'
  checks.push('GIS loader/button and nonce; native token, object, access token and wrapped output blocked without posting credentials')

  step = 'exact Workspace rejection through GIS credential callback'
  let attempt = await google({ hd: 'other.edu.ge' })
  assert.equal(attempt.response.status(), 400)
  await page.getByRole('alert').getByText(/verified @btu.edu.ge/).waitFor()
  checks.push('One supported Google button, no OTP inputs; invalid hosted domain rejected by real backend')

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
  assert.equal(calls.filter(call => call.path === '/api/accounts/google/authenticate/').length, 4, 'Each GIS callback is consumed once even when delivered twice')
  assert.ok(sdkLoads >= 1)
  assert.deepEqual(errors, []); assert.deepEqual(blocked, [])
  await fs.writeFile(path.join(dir, 'google-auth-browser-results.json'), JSON.stringify({ passed: true, synthetic: true,
    mockedResponses: false, gisAndKeysSynthetic: true, liveGoogleTested: false, checks, calls, errors }, null, 2))
  console.log(`PASS Workspace portal Chrome/Django: ${checks.length} groups, ${calls.length} actual API responses; GIS/keys synthetic, no live Google.`)
} catch (error) {
  await fs.writeFile(path.join(dir, 'google-auth-browser-failure.json'), JSON.stringify({ step, error: error.message, checks, calls, errors, blocked }, null, 2))
  await page.screenshot({ path: path.join(dir, 'google-auth-failure.png'), fullPage: true }).catch(() => {})
  console.error(`FAIL Workspace portal browser at ${step}: ${error.message}`); process.exitCode = 1
} finally { await context.close(); await browser.close() }
