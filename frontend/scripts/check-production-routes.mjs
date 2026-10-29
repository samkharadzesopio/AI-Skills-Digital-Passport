// Isolated browser acceptance of dist. All API responses below are test fixtures.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import http from 'node:http'
import path from 'node:path'
import os from 'node:os'
import { pathToFileURL } from 'node:url'
import { dashboard, pdf } from './student-fixtures.mjs'

const tools = process.env.BTU_BROWSER_TOOLS || path.join(os.tmpdir(), 'btu-passport-browser-tests')
const { chromium } = await import(pathToFileURL(path.join(tools, 'node_modules/playwright/index.mjs')))
const config = JSON.parse(await fs.readFile('vercel.json', 'utf8'))
const fallback = new RegExp(`^${config.rewrites.at(-1).source.replace(':path(', '(?:')}$`)
assert.equal(fallback.test('/student/dashboard'), true)
assert.equal(fallback.test('/admin/dashboard'), true)
assert.equal(fallback.test('/verify'), true)
assert.equal(fallback.test('/api'), false)
assert.equal(fallback.test('/api/accounts/me/'), false)
const dist = path.resolve('dist')
const server = http.createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname)
    let target = path.resolve(dist, '.' + pathname)
    if (!target.startsWith(dist + path.sep) && target !== dist) throw Error('path')
    try { if (!(await fs.stat(target)).isFile()) throw Error('directory') } catch {
      if (!fallback.test(pathname)) { res.writeHead(404); res.end(); return }
      target = path.join(dist, 'index.html')
    }
    const mime = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png' }
    res.setHeader('Content-Type', mime[path.extname(target)] || 'application/octet-stream')
    res.end(await fs.readFile(target))
  } catch { res.writeHead(404); res.end() }
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const base = `http://127.0.0.1:${server.address().port}`
const browser = await chromium.launch({ headless: true, ...(process.env.BTU_BROWSER_EXECUTABLE ? { executablePath: process.env.BTU_BROWSER_EXECUTABLE } : {}) })
const results = [], pageErrors = [], unexpected = []
try {
  assert.equal((await fetch(base + '/api/accounts/me/')).status, 404, 'API must never receive SPA HTML')
  for (const width of [390, 768, 1440]) {
    for (const state of ['anonymous', 'unavailable', 'authenticated', 'invalid-session']) {
      for (const role of ['student', 'admin']) {
        const context = await browser.newContext({ viewport: { width, height: 900 } })
        const page = await context.newPage()
        page.on('pageerror', error => pageErrors.push(error.message))
        const apiCalls = []
        await page.route('**/api/**', route => {
          const url = new URL(route.request().url()), endpoint = url.pathname
          apiCalls.push(endpoint)
          const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
          if (endpoint === '/api/accounts/me/') {
            if (state === 'anonymous') return json(403, { detail: 'Authentication credentials were not provided.' })
            if (state === 'unavailable') return json(503, { detail: 'Synthetic test outage' })
            if (state === 'invalid-session') return route.fulfill({ status: 200, contentType: 'text/html', body: '<html>Not an API response</html>' })
            return json(200, { email: `test.${role}@btu.edu.ge`, role: role === 'student' ? 'STUDENT' : 'ADMIN', email_verified: true, student_association: role === 'student' ? 'linked' : 'unlinked', capabilities: role === 'admin' ? ['view_student_records'] : [] })
          }
          if (state !== 'authenticated') { unexpected.push(endpoint); return json(403, {}) }
          if (endpoint === '/api/student/dashboard/') return json(200, dashboard)
          if (endpoint === '/api/student/passport/pdf/status/') return json(200, pdf)
          if (endpoint === '/api/admin/statistics/') return json(200, { students: 7, passports: 1, recognized_skills: 1, verified_achievements: 1, credentials: dashboard.credentials })
          unexpected.push(endpoint); return json(404, {})
        })
        const target = `/${role}/dashboard`
        for (const refresh of [false, true]) {
          if (refresh) await page.reload(); else await page.goto(base + target)
          await page.getByRole('navigation', { name: 'Passport workspaces' }).waitFor()
          const navigationLayout = await page.locator('.workspace-navigation').evaluate(nav => ({
            direction: getComputedStyle(nav).flexDirection,
            height: nav.getBoundingClientRect().height,
            linkTops: [...nav.querySelectorAll('a')].map(link => link.getBoundingClientRect().top),
          }))
          assert.equal(navigationLayout.direction, 'row', 'Header navigation must override global sidebar column styles')
          assert.ok(navigationLayout.height <= 60, `${width}: compact header navigation height`)
          assert.ok(Math.max(...navigationLayout.linkTops) - Math.min(...navigationLayout.linkTops) < 2, `${width}: all three links stay horizontal`)
          if (state === 'anonymous') {
            await page.waitForURL(base + `/${role}/login`)
            await page.getByRole('heading', { name: role === 'student' ? 'Student sign in' : 'Administrator sign in', exact: true }).waitFor()
          } else if (state === 'authenticated') {
            if (role === 'student') await page.getByRole('region', { name: 'Your Digital Passport', exact: true }).waitFor()
            else await page.getByRole('heading', { name: 'Total registered students' }).waitFor()
          } else {
            await page.getByText('Your session could not be checked.', { exact: false }).waitFor()
            assert.equal(await page.getByRole('region', { name: 'Your Digital Passport' }).count(), 0)
            assert.equal(await page.getByRole('heading', { name: 'Administration dashboard' }).count(), 0)
          }
          assert.equal(await page.getByRole('complementary', { name: 'Demo Mode' }).count(), 0)
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${width} ${state} ${role} horizontal overflow`)
        }
        if (state !== 'authenticated') assert.ok(apiCalls.every(p => p === '/api/accounts/me/'), 'No protected data request before session authorization')
        await page.getByRole('navigation', { name: 'Passport workspaces' }).getByRole('link', { name: 'Public Verification', exact: true }).click()
        await page.waitForURL(base + '/verify')
        await page.reload()
        const before = apiCalls.length
        await page.getByRole('navigation', { name: 'Passport workspaces' }).waitFor()
        assert.equal(await page.getByRole('navigation', { name: 'Passport workspaces' }).getByRole('link').count(), 3)
        await page.goto(base + '/')
        await page.waitForURL(base + '/verify')
        assert.equal(apiCalls.length, before, 'Public landing needs no private API')
        for (const [label, destination] of [['Student Dashboard', '/student/dashboard'], ['Admin Dashboard', '/admin/dashboard']]) {
          await page.getByRole('navigation', { name: 'Passport workspaces' }).getByRole('link', { name: label, exact: true }).click()
          await page.waitForURL(new RegExp(destination.replace('/dashboard', '/(dashboard|login)') + '$'))
          await page.goto(base + '/verify')
        }
        results.push({ width, state, role, direct: true, refresh: true, navigation: true, horizontalOverflow: false })
        await context.close()
      }
    }
  }
  assert.deepEqual(pageErrors, [])
  assert.deepEqual(unexpected, [])
  console.log(JSON.stringify({ artifact: 'production dist', fixtures: 'isolated Playwright API interception; no real Django or Vercel requests', cases: results.length, results, pageErrors, unexpected }, null, 2))
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)) }
