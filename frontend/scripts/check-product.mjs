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
  let dashboardPassport, user = student, passport = null, denied = false, malformed = false, ready = false, revoked = false, issueAttempts = 0, issueKey, historyRecords = []
  let profilesAvailable = false, confirmAttempts = 0
  const previewSnapshot = { id: uuid, snapshot_sha256: 'a'.repeat(64), state: 'READY', expires_at: '2099-01-01T00:00:00Z', report: { valid_records: 1, duplicate_records: 1, invalid_records: 1, review_records: 1, rows: [{ row: 2, status: 'REVIEW', code: 'INSTITUTIONAL_CONFIRMATION_REQUIRED' }] }, result: null }
  const calls = []
  api.defaults.adapter = async config => {
    const path = config.url, body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data ?? null
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
    if (path === 'student/dashboard/') return respond(malformed ? { profile: [] } : { passport: dashboardPassport, profile: { email: user.email, first_name: 'Synthetic' }, credentials: { total: 0 }, recognized_skills: 0, verified_achievements: 0, recent_achievements: [] })
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
    if (path === 'integrations/import/profiles/?page=1') return profilesAvailable ? respond({ count: 2, next: null, results: [{ id: uuid, key: 'synthetic-approved', version: 1, source: 'BTU_GOOGLE_SHEETS', kind: 'SKILL_AWARD' }, { id: historicalId, key: 'synthetic-excel', version: 1, source: 'BTU_EXCEL', kind: 'COURSE_COMPLETION' }] }) : respond({}, 404)
    if (path === 'integrations/import/excel/preview/') { assert.ok(body instanceof FormData); assert.equal(body.get('profile_id'), historicalId); assert.equal(body.get('file').name, 'synthetic.xlsx'); return respond(previewSnapshot) }
    if (path === 'integrations/import/google-sheets/preview/') { assert.deepEqual(body, { profile_id: uuid }); return respond(previewSnapshot) }
    if (path === 'integrations/import/previews/' + uuid + '/confirm/') { assert.deepEqual(body, { snapshot_sha256: 'a'.repeat(64), confirm: true }); confirmAttempts++; return respond({ ...previewSnapshot, state: 'COMPLETED', result: { processed: 1, issued: 1, failed: 0, skipped: 0, errors: [], import_id: 1 } }) }
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
  await click('Copy link'); await until(() => document.body.textContent.includes('Select and copy the link above.'))
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
  dashboardPassport = passport
  await mount('/student/dashboard'); await until(() => !!document.querySelector('.dashboard-passport-actions'))
  assert.equal(document.querySelectorAll('.stats,.dashboard-grid,.dashboard-greeting,.dashboard-recent').length, 0)
  await until(() => ![...document.querySelectorAll('button')].find(b => b.textContent === 'Download PDF').disabled)
  await click('Share Passport'); await until(() => document.body.textContent.includes('Select and copy the verification link below.'))
  assert.ok(document.querySelector('.dashboard-share-link input').value.includes('passport%3A'))
  dashboardPassport = null
  await mount('/student/dashboard'); await until(() => document.body.textContent.includes('No passport issued yet'))
  assert.ok([...document.querySelectorAll('button')].find(b => b.textContent === 'Download PDF').disabled)
  assert.ok([...document.querySelectorAll('button')].find(b => b.textContent === 'Share Passport').disabled)
  assert.ok(document.querySelector('a[href="/student/passport#passport-history"]'))
  const historicalId = '00000000-0000-0000-0000-000000000002'
  historyRecords = [{ id: historicalId, public_reference: historicalId, status: 'ISSUED', version_number: 1 }]
  await mount('/student/passport'); await until(() => document.body.textContent.includes('Historical version 1') && !!document.getElementById('passport-share'))
  assert.match(document.body.textContent, /not selected as the current passport/)
  assert.ok([...document.querySelectorAll('a')].some(anchor => anchor.href.includes(encodeURIComponent('passport-version:' + historicalId))))
  assert.equal(document.querySelectorAll('#passport-share').length, 1)
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
  assert.equal(accessDecision({ status: 'authenticated', user: parseAccountSummary({ ...admin, capabilities: ['invented-grant'] }) }, 'administrator'), 'permissions-missing')
  assert.deepEqual(parseAccountSummary({ ...admin, capabilities: [...admin.capabilities, 'manage_legal_identity', 'manage_passport_lifecycle'] }).capabilities, admin.capabilities)
  assert.throws(() => parseAccountSummary({ ...admin, capabilities: [42] }))
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
  await until(() => document.body.textContent.includes('Import is disabled until that backend workflow is integrated.')); assert.ok(!calls.some(call => call.path === 'integrations/import/google-sheets/' || call.path === 'integrations/import/excel/'))
  assert.doesNotMatch(document.body.textContent, /successfully imported|Credential issued/)
  assert.ok(calls.some(call => call.path.endsWith('/revoke/') && call.method === 'post'))
  profilesAvailable = true
  await mount('/admin/imports'); await until(() => !!document.getElementById('import-source'))
  await act(async () => { const select = document.getElementById('import-source'); select.value = 'BTU_GOOGLE_SHEETS'; select.dispatchEvent(new window.Event('change', { bubbles: true })) })
  await act(async () => { const select = document.getElementById('import-profile'); select.value = uuid; select.dispatchEvent(new window.Event('change', { bubbles: true })) })
  await click('Preview incoming records'); await until(() => document.body.textContent.includes('INSTITUTIONAL_CONFIRMATION_REQUIRED'))
  assert.equal(confirmAttempts, 0, 'Preview must not import')
  assert.ok([...document.querySelectorAll('button')].find(b => b.textContent === 'Confirm reviewed import').disabled)
  await until(() => !document.querySelector('input[type="checkbox"]').disabled)
  await act(async () => document.querySelector('input[type="checkbox"]').click())
  await click('Confirm reviewed import'); await until(() => document.body.textContent.includes('Persisted import result'))
  assert.equal(confirmAttempts, 1)
  assert.ok([...document.querySelectorAll('button')].find(b => b.textContent === 'Confirm reviewed import').disabled)
  await act(async () => { const select = document.getElementById('import-source'); select.value = 'BTU_EXCEL'; select.dispatchEvent(new window.Event('change', { bubbles: true })) })
  assert.ok(!document.body.textContent.includes('Review import preview'), 'Source changes must discard old review')
  await act(async () => { const select = document.getElementById('import-profile'); select.value = historicalId; select.dispatchEvent(new window.Event('change', { bubbles: true })); const input = document.getElementById('completion-file'); Object.defineProperty(input, 'files', { configurable: true, value: [new File(['synthetic fixture bytes'], 'synthetic.xlsx')] }); input.dispatchEvent(new window.Event('change', { bubbles: true })) })
  await click('Preview incoming records'); await until(() => document.body.textContent.includes('Review import preview'))
  assert.equal(confirmAttempts, 1, 'Excel preview must not issue')
  user = { ...admin, capabilities: ['view_student_records'] }
  await mount('/admin/credentials'); await until(() => document.body.textContent.includes('synthetic-credential'))
  assert.equal(document.querySelector('textarea'), null)
  const requestsBefore = calls.filter(call => call.path.startsWith('integrations/')).length
  await mount('/admin/imports'); await until(() => document.body.textContent.includes('does not have permission'))
  assert.equal(calls.filter(call => call.path.startsWith('integrations/')).length, requestsBefore)
  await mount('/admin/students/not-a-uuid'); await until(() => document.body.textContent.includes('Invalid student reference'))
  user = { ...student, email: 'second.synthetic@btu.edu.ge' }
  await mount('/student/profile'); await until(() => document.body.textContent.includes(user.email))
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
