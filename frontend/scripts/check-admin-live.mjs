// Explicit contract/DOM fixtures; real Django acceptance is a separate driver.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { JSDOM } from 'jsdom'
import { AxiosError, AxiosHeaders } from 'axios'
import { id, dashboard, credential, achievement, skill, version, passport, pdf } from './student-fixtures.mjs'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, server: { middlewareMode: true }, appType: 'custom' })
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173/admin/dashboard', pretendToBeVisual: true }), saved = new Map(), timers = new Set(), calls = []
let root, client
function expose(k, v) { saved.set(k, Object.getOwnPropertyDescriptor(globalThis, k)); Object.defineProperty(globalThis, k, { configurable: true, writable: true, value: v }) }
try {
  for (const k of ['window','document','navigator','HTMLElement','Element','Node','MutationObserver','localStorage']) expose(k, dom.window[k])
  expose('IS_REACT_ACT_ENVIRONMENT', true)
  const React = await import('react'), { act } = React, { createRoot } = await import('react-dom/client'), { QueryClient, QueryClientProvider, timeoutManager } = await import('@tanstack/react-query'), { BrowserRouter } = await import('react-router-dom')
  timeoutManager.setTimeoutProvider({ setTimeout: (f, ms) => { const t = setTimeout(f, ms); timers.add(t); return t }, clearTimeout: t => { clearTimeout(t); timers.delete(t) }, setInterval: (f, ms) => { const t = setInterval(f, ms); timers.add(t); return t }, clearInterval: t => { clearInterval(t); timers.delete(t) } })
  const { api, resetCsrfToken } = await server.ssrLoadModule('/src/services/api.ts'), service = await server.ssrLoadModule('/src/admin/live/service.ts'), dto = await server.ssrLoadModule('/src/admin/live/contracts.ts'), { AppRoutes } = await server.ssrLoadModule('/src/App.tsx'), { LocaleProvider } = await server.ssrLoadModule('/src/i18n.tsx')
  const admin = { email: 'unit.admin@btu.edu.ge', role: 'ADMIN', email_verified: true, student_association: 'unlinked', capabilities: ['view_student_records','manage_student_accounts','manage_credentials','revoke_credentials','sync_classroom','import_completions'] }
  let current = structuredClone(admin), malformed = false, offline = false, empty = false, paginate = false, limited = false, sheetCredentialsMissing = false, issueFailure = false, csrfFailure = false, c = { ...credential, student_id: dashboard.profile.id }, event = { id: id(40), source: 'BTU_CLASSROOM', source_event_id: 'TEST-SYNC', state: 'FAILED', attempts: 1, retryable: true, next_retry_at: null, error_code: 'TemporaryFailure', credential_id: null }
  const page = results => ({ count: results.length, next: null, previous: null, results }), cursor = results => ({ next: null, previous: null, results })
  api.defaults.adapter = async config => {
    const path = config.url, method = config.method, body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    calls.push({ path, method, body, csrf: config.headers.get('X-CSRFToken') }); assert.equal(config.withCredentials, true); assert.equal(config.baseURL, '/api/')
    const response = (status, data, headers = {}) => { const r = { status, data, headers: new AxiosHeaders(headers), config }; if (status >= 400) throw new AxiosError('Secret unsafe backend text', 'ERR_BAD_RESPONSE', config, undefined, r); return r }
    if (path === 'accounts/csrf/') return response(200, { csrfToken: 'A'.repeat(64) })
    if (path === 'accounts/me/') return current ? response(200, current) : response(403, {})
    if (!current) return response(403, {})
    if (offline) throw new AxiosError('Secret transport text', 'ERR_NETWORK', config)
    if (method !== 'get') { assert.equal(config.headers.get('X-CSRFToken'), 'A'.repeat(64)); if (csrfFailure) { csrfFailure = false; return response(403, 'Private CSRF diagnostics') } }
    if (path === 'admin/statistics/') return response(200, malformed ? { students: 'malformed' } : { students: 1, passports: 1, recognized_skills: 1, verified_achievements: 1, credentials: dashboard.credentials })
    if (path.startsWith('admin/students/?')) { const p = page(empty ? [] : [dashboard.profile]); if (paginate) { p.count = 26; p.next = path.includes('page=1') ? 'https://evil.invalid/steal-private-session' : null; p.previous = path.includes('page=2') ? 'https://evil.invalid/other-page' : null } return response(200, p) }
    if (path === `admin/students/${dashboard.profile.id}/`) return response(200, dashboard)
    if (path.includes('/achievements/')) return response(200, page([{ ...achievement, credential_count: 0 }]))
    if (path.startsWith('admin/credentials/?')) return response(200, page([c]))
    if (path === `admin/credentials/${c.id}/`) return response(200, c)
    if (path.includes('/history/')) return response(200, page([{ id: id(30), event_type: 'ISSUED', occurred_at: c.issued_at }]))
    if (path === 'admin/credentials/issue/') { if (issueFailure) { issueFailure = false; return response(503, {}) } return response(200, c) }
    if (path.endsWith('/revoke/')) { c = { ...c, status: 'REVOKED', validity_status: 'REVOKED', revoked_at: '2026-10-26T10:00:00Z' }; return response(200, c) }
    if (path.startsWith('admin/catalog/')) return response(200, page([skill]))
    if (path === 'admin/course-mappings/') return response(200, { source: 'BACKEND_CONTROLLED_COURSE_MAPPINGS', results: [{ course_id: 'AI-101', course_name: 'Approved test course', minimum_grade: 51, skill_codes: ['AI_LITERACY'], enabled: true }] })
    if (path.startsWith('admin/passports/?')) return response(200, page([passport]))
    if (path.includes('/versions/?')) return response(200, page([version]))
    if (path.includes('/pdf/status/')) return response(200, pdf)
    if (path === 'integrations/classroom/completions/') return response(200, { source: 'SIMULATED_BTU_CLASSROOM', count: 0, results: [] })
    if (path === 'integrations/classroom/sync/') return limited ? response(429, {}, { 'retry-after': '1' }) : response(200, { source: 'SIMULATED_BTU_CLASSROOM', status: body.dry_run ? 'preview' : 'completed', processed: 1, issued: 0, skipped: 0, failed: 0, would_issue: 1, eligible_count: 1, errors: [] })
    if (path.startsWith('integrations/classroom/events/')) return response(200, cursor([event]))
    if (path.endsWith('/retry/')) return response(200, { result: 'issued', state: 'CREDENTIAL_ISSUED', error_code: '' })
    if (path.startsWith('integrations/import/profiles/?')) return response(200, page([]))
    if (path === 'integrations/imports/') return response(200, cursor([{ id: 1, source: 'BTU_EXCEL', state: 'PARTIAL', summary: { processed: 1, issued: 1, failed: 0, errors: [] }, validation_errors: [{ row: 3, code: 'INVALID_ROW' }] }]))
    if (path === 'integrations/imports/1/events/') return response(200, cursor([{ ...event, source: 'BTU_EXCEL' }]))
    if (path === 'integrations/import/google-sheets/') return response(sheetCredentialsMissing ? 400 : 503, { error: sheetCredentialsMissing ? 'Google Sheets credentials not configured' : 'Private provider details' })
    throw new Error(`Unexpected test endpoint ${method} ${path}`)
  }
  const text = () => document.body.textContent
  async function until(check, label) { const end = Date.now() + 6000; while (!check()) { if (Date.now() > end) throw new Error(`Timeout ${label}: ${text()}`); await act(async () => new Promise(r => setTimeout(r, 20))) } }
  async function mount(path) { if (root) await act(async () => root.unmount()); client?.clear(); client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); window.history.replaceState({}, '', path); root = createRoot(document.getElementById('root')); await act(async () => root.render(React.createElement(QueryClientProvider, { client }, React.createElement(LocaleProvider, null, React.createElement(BrowserRouter, null, React.createElement(AppRoutes)))))) }
  async function click(label) { await until(() => [...document.querySelectorAll('button')].some(b => b.textContent === label && !b.disabled), label); const b = [...document.querySelectorAll('button')].find(b => b.textContent === label); await act(async () => b.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))) }
  async function input(id, value) { await act(async () => { const el = document.getElementById(id), proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value); el.dispatchEvent(new window.Event('input', { bubbles: true })) }) }
  await mount('/admin/dashboard'); await until(() => text().includes('Administration dashboard') && text().includes('Total issued credentials'), 'real dashboard adapter')
  assert.match(text(), /no review-queue count/)
  assert.match(text(), /Global count unavailable/)
  assert.ok(document.querySelector('section[aria-label="Learning Data"]'))
  await mount('/admin/skills'); await until(() => text().includes('Learning format: APPLIED'), 'catalog loaded'); await input('catalog-search','missing synthetic skill'); await until(() => text().includes('No matching skills on this page'), 'catalog search empty'); await input('catalog-search','');
  await mount('/admin/course-mappings'); await until(() => text().includes('Activity-to-Skill Mapping'), 'mapping title'); assert.match(text(), /supports course mappings only/)
  assert.match(text(), /LIVE/); assert.doesNotMatch(text(), /Nino|DEMO-|trend chart/); assert.equal(client.getQueryData(['admin','demo']), undefined)
  current = { ...admin, capabilities: ['view_student_records'] }
  await mount(`/admin/students/${dashboard.profile.id}`); await until(() => text().includes('Persisted reasoning'), 'read-only achievements'); assert.ok(!text().includes('Issue credential')); assert.ok(!text().includes('Edit academic profile'))
  const before = calls.length; await mount('/admin/imports'); await until(() => text().includes('Permission required'), 'import gate'); assert.ok(!calls.slice(before).some(c => c.path.startsWith('integrations/')))
  current = { ...admin, capabilities: ['sync_classroom'] }; await mount('/admin/classroom-sync'); await until(() => text().includes('TEST-SYNC'), 'sync-only grant'); assert.ok(!document.querySelector('a[href="/admin/students"]'))
  await mount('/admin/dashboard'); await until(() => text().includes('Permission required'), 'sync grant does not imply records access')
  current = structuredClone(admin)
  await mount(`/admin/students/${dashboard.profile.id}`); await until(() => !!document.querySelector('input[type=checkbox]'), 'evidence selection')
  await act(async () => document.querySelector('input[type=checkbox]').click()); issueFailure = true
  await click('Issue credential'); await click('Confirm Issue credential'); await until(() => text().includes('unavailable. Contact'), 'safe issuance failure')
  const first = calls.filter(c => c.path === 'admin/credentials/issue/').at(-1).body
  assert.deepEqual(first.achievement_ids, [achievement.id]); assert.ok(first.idempotency_key); assert.equal(first.expires_at, null); assert.deepEqual(Object.keys(first).sort(), ['achievement_ids','expires_at','idempotency_key'])
  await click('Confirm Issue credential'); await until(() => text().includes('Credential issued:'), 'issuance success'); assert.deepEqual(calls.filter(c => c.path === 'admin/credentials/issue/').at(-1).body, first)
  await mount(`/admin/credentials/${c.id}`); await until(() => !!document.getElementById('revocation-reason'), 'revocation form'); await input('revocation-reason', 'Synthetic authorized reason'); await click('Revoke credential'); await click('Confirm Revoke credential'); await until(() => text().includes('REVOKED'), 'revocation state'); assert.deepEqual(calls.find(c => c.path.endsWith('/revoke/')).body, { reason: 'Synthetic authorized reason' })
  for (const [path, expected] of [['skills','Learning format: APPLIED'], ['course-mappings','AI_LITERACY'], ['students','University Student records'], ['passports/preview','Open Passport'], ['audit-logs','General security-audit reading']]) { await mount('/admin/' + path); await until(() => text().includes(expected), path); assert.equal(client.getQueryData(['admin','demo']), undefined) }
  await mount('/admin/classroom-sync'); await until(() => text().includes('TEST-SYNC'), 'persisted sync history'); await click('Preview sync (dry run)'); await until(() => text().includes('Sync preview'), 'dry run result'); assert.deepEqual(calls.find(c => c.path.endsWith('/sync/')).body, { dry_run: true }); await click('Synchronize simulated completions'); await click('Confirm Synchronize simulated completions'); await until(() => text().includes('Sync completed'), 'sync result'); await click('Retry event TEST-SYNC'); await click('Confirm Retry event TEST-SYNC'); assert.deepEqual(calls.filter(c => c.path.endsWith('/retry/')).at(-1).body, {})
  await mount('/admin/imports'); await until(() => text().includes('Row 3: INVALID_ROW'), 'persisted import errors'); await until(() => !!document.getElementById('import-profile'), 'reviewed profile workflow preserved'); assert.ok(document.getElementById('import-source')); assert.match(text(), /Preview does not issue credentials/); assert.ok([...document.querySelectorAll('button')].find(b => b.textContent === 'Preview incoming records')?.disabled); assert.equal(document.querySelector('input[type=url]'), null); await click('Inspect import 1 events'); await until(() => text().includes('TEST-SYNC'), 'import event history'); await click('Configured Google Sheets'); await click('Import configured Google Sheet'); await click('Confirm Import configured Google Sheet'); await until(() => text().includes('unavailable. Contact'), 'configured sheet unavailable'); assert.doesNotMatch(text(), /Private provider details|Secret/)
  sheetCredentialsMissing = true; await assert.rejects(service.importSheet(), e => e.status === 400 && e.message.includes('Google Sheets configuration')); sheetCredentialsMissing = false
  malformed = true; await mount('/admin/dashboard'); await until(() => text().includes('Records unavailable'), 'malformed response'); assert.doesNotMatch(text(), /Nino|Total students/); malformed = false; offline = true; await mount('/admin/dashboard'); await until(() => text().includes('Records unavailable'), 'network failure'); offline = false
  empty = true; await mount('/admin/students'); await until(() => text().includes('No matching Students'), 'real empty state'); empty = false
  paginate = true; await mount('/admin/students'); await until(() => text().includes('26 records'), 'server pagination'); await click('Next'); await until(() => text().includes('Page 2'), 'second server page'); assert.ok(calls.some(c => c.path === 'admin/students/?page=2')); assert.ok(!calls.some(c => c.path.startsWith('http'))); paginate = false
  limited = true; await mount('/admin/classroom-sync'); await until(() => text().includes('TEST-SYNC'), 'rate-limit page'); await click('Preview sync (dry run)'); await until(() => text().includes('Too many requests'), 'rate-limit result'); assert.ok([...document.querySelectorAll('button')].find(b => b.textContent === 'Preview sync (dry run)').disabled); limited = false
  csrfFailure = true; resetCsrfToken(); await assert.rejects(service.syncClassroom(false), e => e.status === 403 && !('config' in e)); await service.syncClassroom(true); assert.equal(calls.at(-2).path, 'accounts/csrf/')
  assert.throws(() => dto.credential({ ...credential, student_id: 'bad' })); assert.throws(() => dto.achievement({ ...achievement, credential_count: 0, verification_status: 'PENDING' })); assert.deepEqual(dto.summary({ processed: 1, payload: 'private' }), { counts: { processed: 1 }, errors: [] }); assert.equal(dto.cursorPage({ next: 'https://evil.invalid/path?cursor=abc%3D', previous: null, results: [] }, dto.event).next, 'abc='); await service.getSyncEvents('abc='); assert.equal(calls.at(-1).path, 'integrations/classroom/events/?cursor=abc%3D')
  await mount('/admin/dashboard'); await until(() => text().includes('Current credential validity'), 'live session before expiry'); current = null; await click('Refresh dashboard'); await until(() => window.location.pathname === '/admin/login', 'mid-page expired session'); assert.doesNotMatch(text(), /Persisted reasoning|Authenticated Student/)
  for (const key of Object.keys(localStorage)) assert.equal(key, 'btu-locale')
  console.log('PASS Admin DOM/contracts: grant combinations, real-shaped records, no live demo provider, evidence-only issuance and stable retry key, revocation, sync controls/history/retry, import errors/configured Sheet, malformed/offline responses, CSRF rebootstrap and session expiry. Fixture transport only; use Admin HTTP harness for real Django acceptance.')
} finally {
  if (root) await (await import('react')).act(async () => root.unmount()); client?.clear(); for (const t of timers) { clearTimeout(t); clearInterval(t) } dom.window.close(); for (const [k, v] of saved) { if (v) Object.defineProperty(globalThis, k, v); else delete globalThis[k] } await server.close()
}
