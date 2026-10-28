import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import { AxiosError } from 'axios'

const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom' })
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173/' })
const originals = new Map(), timers = new Set()
function expose(key, value) { originals.set(key, Object.getOwnPropertyDescriptor(globalThis, key)); Object.defineProperty(globalThis, key, { configurable: true, writable: true, value }) }
let root
try {
  for (const key of ['window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'MutationObserver', 'localStorage']) expose(key, dom.window[key])
  expose('IS_REACT_ACT_ENVIRONMENT', true)
  const React = await import('react'), { act } = React, { createRoot } = await import('react-dom/client')
  const { timeoutManager } = await import('@tanstack/react-query')
  timeoutManager.setTimeoutProvider({ setTimeout: (fn, ms) => { const id = setTimeout(fn, ms); timers.add(id); return id }, clearTimeout: id => { timers.delete(id); clearTimeout(id) }, setInterval: (fn, ms) => { const id = setInterval(fn, ms); timers.add(id); return id }, clearInterval: id => { timers.delete(id); clearInterval(id) } })
  const { api } = await server.ssrLoadModule('/src/services/api.ts')
  const { parseAccountSummary, accessDecision } = await server.ssrLoadModule('/src/auth/contracts.ts')
  const { getProduct, downloadPassport } = await server.ssrLoadModule('/src/services/product.ts')
  const { normalizePassportReference } = await server.ssrLoadModule('/src/verification/validation.ts')
  const { default: App } = await server.ssrLoadModule('/src/App.tsx')
  const uuid = '00000000-0000-0000-0000-000000000001'
  const student = { email: 'synthetic@btu.edu.ge', role: 'STUDENT', email_verified: true, student_association: 'linked', capabilities: [] }
  const admin = { email: 'synthetic-admin@btu.edu.ge', role: 'ADMIN', email_verified: true, student_association: 'unlinked', capabilities: ['view_student_records', 'manage_credentials', 'revoke_credentials', 'import_completions'] }
  let user = student, passport = null, denied = false, malformed = false, ready = false, revoked = false, issueAttempts = 0, issueKey, historyRecords = []
  const calls = []
  api.defaults.adapter = async config => {
    const path = config.url, body = config.data ? JSON.parse(config.data) : null
    calls.push({ path, method: config.method, body })
    const respond = (data, status = 200, headers = {}) => {
      const response = { data, status, headers, config, statusText: 'Synthetic response' }
      if (status >= 400) throw new AxiosError('Private service failure', 'ERR_BAD_RESPONSE', config, undefined, response)
      return response
    }
    if (path === 'accounts/me/') return respond(user)
    if (path === 'accounts/csrf/') return respond({ csrfToken: 'A'.repeat(64) })
    if (path.startsWith('student/passport/versions/?')) return respond({ count: historyRecords.length, next: null, results: historyRecords })
    if (path.startsWith('student/passport/versions/') && path.endsWith('/pdf/status/')) return respond({ status: 'ISSUED', available_for_download: true })
    if (path === 'student/passport/') return denied ? respond({}, 403) : respond(passport ?? { passport: null })
    if (path === 'student/dashboard/') return respond(malformed ? { profile: [] } : { profile: { email: user.email, first_name: 'Synthetic' }, credentials: { total: 0 }, recognized_skills: 0, verified_achievements: 0, recent_achievements: [] })
    if (path === 'student/passport/pdf/status/') return respond({ status: ready ? 'ISSUED' : 'NOT_REQUESTED', available_for_download: ready })
    if (path === 'student/passport/pdf/') { assert.equal(config.headers.get('X-CSRFToken'), 'A'.repeat(64)); assert.deepEqual(body, {}); ready = true; return respond({ status: 'ISSUED' }) }
    if (path === 'student/passport/pdf/download/') return respond(new Blob(['%PDF-synthetic'], { type: 'application/pdf' }), 200, { 'content-type': 'application/pdf' })
    if (path.startsWith('admin/credentials/?')) return respond({ count: 1, next: null, results: [{ id: uuid, public_reference: 'synthetic-credential', validity_status: revoked ? 'REVOKED' : 'VALID', achievements: [] }] })
    if (path === `admin/credentials/${uuid}/revoke/`) { assert.deepEqual(body, { reason: 'Synthetic revocation' }); revoked = true; return respond({ id: uuid, validity_status: 'REVOKED' }) }
    if (path === `admin/students/${uuid}/`) return respond({ profile: { email: student.email }, credentials: { total: 0 }, recent_achievements: [] })
    if (path.startsWith('admin/passports/?')) return respond({ count: 0, next: null, results: [] })
    if (path.startsWith(`admin/students/${uuid}/achievements/`)) return respond({ count: 1, next: null, results: [{ id: uuid, skill: { skill_name: 'Synthetic recognized skill' }, verification_status: 'VERIFIED' }] })
    if (path === 'admin/credentials/issue/') {
      assert.deepEqual(body.achievement_ids, [uuid])
      if (issueAttempts++ === 0) { issueKey = body.idempotency_key; throw new AxiosError('Unknown issuance outcome', 'ERR_NETWORK', config) }
      assert.equal(body.idempotency_key, issueKey, 'Retry must preserve the original idempotency key')
      return respond({ id: uuid, validity_status: 'VALID' })
    }
    if (path === 'integrations/imports/') return respond({ results: [], next: null })
    if (path === 'integrations/import/google-sheets/') return respond({}, 503)
    throw new Error(`Unexpected synthetic API request: ${path}`)
  }
  async function until(check) { const end = Date.now() + 5000; while (!check()) { if (Date.now() > end) throw new Error(`Timed out: ${document.body.textContent}`); await act(async () => { await new Promise(resolve => setTimeout(resolve, 15)) }) } }
  async function mount(path) { if (root) await act(async () => root.unmount()); window.history.replaceState({}, '', path); root = createRoot(document.getElementById('root')); await act(async () => root.render(React.createElement(App))) }
  async function click(label) { const button = [...document.querySelectorAll('button')].find(item => item.textContent === label); assert.ok(button, label); await act(async () => button.click()) }
  await mount('/student/passport'); await until(() => document.body.textContent.includes('No passport issued yet'))
  assert.doesNotMatch(document.body.textContent, /Nino|DEMO-PASSPORT/)
  passport = { id: uuid, public_reference: uuid, status: 'ISSUED', latest_version: { status: 'ISSUED', version_number: 1, skills: [] } }
  await mount('/student/passport'); await until(() => document.body.textContent.includes('NOT_REQUESTED'))
  const link = document.getElementById('passport-share').value
  assert.equal(new URL(link).searchParams.get('reference'), `passport:${uuid}`)
  await click('Share Passport'); await until(() => document.body.textContent.includes('Select and copy the link above.'))
  assert.equal(normalizePassportReference(link), `passport:${uuid}`)
  assert.equal(normalizePassportReference(link.replace('localhost:5173', 'untrusted.invalid')), null)
  assert.equal(normalizePassportReference(`${link}&reference=another`), null)
  assert.ok([...document.querySelectorAll('button')].find(button => button.textContent === 'Download PDF').disabled)
  await click('Prepare PDF'); await until(() => ![...document.querySelectorAll('button')].find(button => button.textContent === 'Download PDF').disabled)
  // Check binary retrieval directly; jsdom cannot navigate a download anchor.
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL, originalClick = dom.window.HTMLAnchorElement.prototype.click
  let downloaded = false
  URL.createObjectURL = blob => { assert.equal(blob.type, 'application/pdf'); return 'blob:synthetic' }
  URL.revokeObjectURL = () => {}
  dom.window.HTMLAnchorElement.prototype.click = function () { downloaded = this.download.endsWith('.pdf') }
  try { await downloadPassport('student/passport/'); assert.equal(downloaded, true) } finally { URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; dom.window.HTMLAnchorElement.prototype.click = originalClick }
  const historicalId = '00000000-0000-0000-0000-000000000002'
  historyRecords = [{ id: historicalId, public_reference: historicalId, status: 'ISSUED', version_number: 1 }]
  await mount('/student/history'); await until(() => document.body.textContent.includes('Historical version 1'))
  assert.match(document.body.textContent, /not selected as the current passport/)
  assert.ok([...document.querySelectorAll('a')].some(anchor => anchor.href.includes(encodeURIComponent('passport-version:' + historicalId))))
  assert.equal(document.querySelectorAll('#passport-share').length, 0)
  assert.ok(calls.some(call => call.path === 'student/passport/versions/' + historicalId + '/pdf/status/'))
  passport = { ...passport, status: 'REPLACED', lifecycle_status: 'REPLACED' }
  await mount('/student/passport'); await until(() => document.body.textContent.includes('Inactive passport record'))
  assert.equal(document.getElementById('passport-share'), null)
  assert.ok(![...document.querySelectorAll('button')].some(button => button.textContent === 'Prepare PDF'))
  passport = { ...passport, status: 'PENDING_BLOCKCHAIN', lifecycle_status: 'ACTIVE', blockchain: { status: 'FAILED' } }
  await mount('/student/passport'); await until(() => document.body.textContent.includes('Blockchain proof processing failed.'))
  assert.equal(document.getElementById('passport-share'), null)
  assert.doesNotMatch(document.body.textContent, /Current passport/)
  passport = { id: uuid, public_reference: uuid, status: 'ISSUED', latest_version: { status: 'ISSUED', version_number: 2, skills: [] } }
  await mount('/student/passport'); await until(() => !!document.getElementById('passport-share'))
  assert.match(document.body.textContent, /Current passport/)
  denied = true; await mount('/student/passport'); await until(() => document.body.textContent.includes('session or permissions'))
  denied = false; malformed = true
  await assert.rejects(getProduct('student/dashboard/'))
  malformed = false
  assert.equal(accessDecision({ status: 'authenticated', user: parseAccountSummary(admin) }, 'administrator'), 'allow')
  assert.equal(accessDecision({ status: 'authenticated', user: { ...admin, capabilities: [] } }, 'administrator'), 'permissions-missing')
  assert.throws(() => parseAccountSummary({ ...admin, capabilities: ['invented-grant'] }))
  user = admin
  await mount(`/admin/students/${uuid}`); await until(() => document.body.textContent.includes('Synthetic recognized skill'))
  await act(async () => document.querySelector('input[type="checkbox"]').click())
  await click('Issue credential for 1 achievements'); await until(() => document.body.textContent.includes('could not complete the request'))
  assert.equal(issueAttempts, 1, 'No automatic retry of an unknown issuance outcome')
  await click('Issue credential for 1 achievements'); await until(() => document.body.textContent.includes('Credential issued.'))
  assert.equal(issueAttempts, 2)
  await mount('/admin/credentials'); await until(() => document.body.textContent.includes('synthetic-credential'))
  await act(async () => { const input = document.getElementById('revoke-reason-' + uuid); Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(input, 'Synthetic revocation'); input.dispatchEvent(new window.Event('input', { bubbles: true })) })
  await act(async () => document.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
  await until(() => document.body.textContent.includes('REVOKED'))
  assert.equal(document.getElementById('revoke-reason-' + uuid), null)
  await mount('/admin/imports'); await until(() => document.body.textContent.includes('No records available.'))
  await click('Import configured Google Sheet'); await until(() => document.body.textContent.includes('could not complete the request'))
  assert.doesNotMatch(document.body.textContent, /successfully imported|Credential issued/)
  assert.ok(calls.some(call => call.path.endsWith('/revoke/') && call.method === 'post'))
  user = { ...admin, capabilities: ['view_student_records'] }
  await mount('/admin/credentials'); await until(() => document.body.textContent.includes('synthetic-credential'))
  assert.equal(document.querySelector('textarea'), null)
  const requestsBefore = calls.filter(call => call.path.startsWith('integrations/')).length
  await mount('/admin/imports'); await until(() => document.body.textContent.includes('does not have permission'))
  assert.equal(calls.filter(call => call.path.startsWith('integrations/')).length, requestsBefore)
  await mount('/admin/students/not-a-uuid'); await until(() => document.body.textContent.includes('Invalid student reference'))
  user = { ...student, email: 'second.synthetic@btu.edu.ge' }
  await mount('/student/dashboard'); await until(() => !!document.getElementById('passport-share'))
  assert.ok(document.querySelector('a[href="/student/history"]'))
  assert.ok(!document.querySelector('nav a[href="/student/credentials"]'))
  await mount('/student/gap-analyzer'); await until(() => document.body.textContent.includes('Coming Soon'))
  assert.equal(document.querySelector('select'), null)
  assert.ok(!document.body.textContent.includes(admin.email))
  for (const key of Object.keys(localStorage)) assert.equal(key, 'btu-locale')
  console.log('Synthetic product integration passed: no-passport state, sharing, PDF preparation/download, denied access, malformed responses, admin capability guards, issuance retry idempotency, revocation and import failure. No real services or blockchain were tested.')
} finally {
  if (root) await (await import('react')).act(async () => root.unmount())
  for (const timer of timers) { clearTimeout(timer); clearInterval(timer) }
  dom.window.close()
  for (const [key, original] of originals) { if (original) Object.defineProperty(globalThis, key, original); else delete globalThis[key] }
  await server.close()
}
