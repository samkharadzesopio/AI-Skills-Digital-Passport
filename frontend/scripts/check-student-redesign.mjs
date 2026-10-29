// Synthetic browser UI coverage. Real Django/PDF acceptance runs separately.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { createServer } from 'vite'
import { dashboard, passport, version, pdf, id } from './student-fixtures.mjs'

if (!process.env.BTU_BROWSER_TOOLS || !process.env.BTU_TEST_ARTIFACTS) throw new Error('Provide isolated browser tools and a review artifact directory')
const { chromium } = await import(pathToFileURL(path.join(process.env.BTU_BROWSER_TOOLS, 'node_modules/playwright/index.mjs')).href)
const output = path.resolve(process.env.BTU_TEST_ARTIFACTS)
await fs.mkdir(output, { recursive: true })
const server = await createServer({ root: path.resolve(import.meta.dirname, '..'), cacheDir: path.join(output, 'vite-cache'),
  define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, server: { host: '127.0.0.1', port: 0, strictPort: true, hmr: false, watch: null } })
await server.listen()
const base = `http://127.0.0.1:${server.httpServer.address().port}`
const browser = await chromium.launch({ headless: true, executablePath: process.env.BTU_BROWSER_EXECUTABLE || undefined })
const latest = { ...version, id: id(35), public_reference: id(36), version_number: 3, issued_at: '2026-10-29T10:00:00Z' }
const middle = { ...version, id: id(25), public_reference: id(26), version_number: 2, issued_at: '2026-10-22T10:00:00Z' }
const currentPassport = { ...passport, latest_version: latest }
const requests = [], errors = [], results = []
try {
  for (const width of [390, 768, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: width === 768 ? 1024 : 900 }, reducedMotion: 'reduce' })
    const page = await context.newPage()
    let mode = 'issued'
    page.on('pageerror', e => errors.push(e.message))
    await page.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), resource = url.pathname.replace('/api/', '')
      requests.push({ width, mode, resource, method: request.method() })
      assert.equal(request.method(), 'GET', 'Visual journeys must never issue credentials')
      let body
      if (resource === 'accounts/me/') body = { email: dashboard.profile.email, role: 'STUDENT', email_verified: true, student_association: mode === 'unlinked' ? 'unlinked' : 'linked', capabilities: [] }
      else {
        assert.notEqual(mode, 'unlinked', 'Unlinked accounts must not reach any private Student API')
        if (resource === 'student/dashboard/') body = mode === 'blank' ? { ...dashboard, passport: null, recognized_skills: 0, verified_achievements: 0, credentials: { total: 0, valid: 0, expired: 0, revoked: 0, invalid: 0 }, recent_achievements: [], recent_credentials: [], skills_by_category: [], skills_by_subcategory: [] } : { ...dashboard, passport: currentPassport }
        else if (resource === 'student/passport/') body = mode === 'blank' ? { passport: null } : currentPassport
        else if (resource === 'student/passport/pdf/status/') {
          assert.notEqual(mode, 'blank')
          body = { ...pdf, passport_version_reference: latest.public_reference, status: 'ISSUED', available_for_download: true, document_reference: id(40), download_document_reference: id(40) }
        } else if (resource === 'student/passport/versions/') {
          const second = url.searchParams.get('page') === '2'
          body = mode === 'blank' ? { count: 0, results: [], next: null, previous: null } : { count: 3, results: second ? [version] : [latest, middle], next: second ? null : '?page=2', previous: second ? '?page=1' : null }
        } else if (resource === `student/passport/versions/${version.id}/`) body = version
        else if (resource === `student/passport/versions/${version.id}/pdf/status/`) body = pdf
        else throw new Error(`Unexpected test API: ${resource}`)
      }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    })
    async function capture(name) {
      await page.evaluate(() => document.fonts.ready)
      await page.locator('main img').evaluateAll(images => Promise.all(images.map(img => img.complete ? Promise.resolve() : new Promise(resolve => { img.onload = resolve; img.onerror = resolve }))))
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)
      assert.equal(overflow, false, `${name} ${width}: horizontal overflow`)
      await page.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: true })
    }
    await page.goto(base + '/student/dashboard')
    await page.getByRole('heading', { name: 'My Passport', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Download PDF', exact: true }).waitFor()
    assert.equal(await page.locator('.passport-slide').count(), 4)
    const top = await page.locator('.passport-viewport').boundingBox()
    assert.ok(top.y < 190, 'Passport must begin near the top of the workspace')
    await capture('passport')
    for (const title of ['About the Passport', 'Verified AI Skillset', 'AI Skill Supplement']) {
      await page.getByRole('button', { name: title, exact: true }).click()
      assert.ok((await page.locator('.passport-view-status').innerText()).startsWith(title))
      if (width === 1440) await capture(`passport-${title.toLowerCase().replaceAll(' ', '-')}`)
    }
    await page.locator('.passport-carousel').focus(); await page.keyboard.press('Home')
    assert.match(await page.locator('.passport-slide[aria-hidden=false]').getAttribute('aria-label'), /Cover/)
    await page.keyboard.press('ArrowRight')
    assert.match(await page.locator('.passport-slide[aria-hidden=false]').getAttribute('aria-label'), /About the Passport/)
    await page.goto(base + '/student/passport/versions')
    await page.getByText('Current version', { exact: true }).waitFor()
    assert.equal(await page.locator('.is-current .passport-version-title a').innerText(), 'Version 3')
    await capture('history')
    await page.getByRole('button', { name: 'Next', exact: true }).click()
    await page.getByRole('link', { name: 'Version 1', exact: true }).waitFor()
    assert.equal(await page.getByText('Current version', { exact: true }).count(), 0, 'Page two must not label its first row current')
    await page.getByRole('link', { name: 'Version 1', exact: true }).click()
    await page.getByRole('heading', { name: 'Issued Passport version', exact: true }).waitFor()
    await page.getByText('Historical version; a newer version is published', { exact: false }).waitFor()
    await page.goto(base + '/student/gap-analyzer')
    await page.getByRole('heading', { name: 'Coming Soon', exact: true }).waitFor()
    assert.equal(await page.locator('main input,main form,main select').count(), 0)
    await capture('gap-analyzer')
    if (width <= 768) {
      await page.getByRole('button', { name: 'Toggle navigation', exact: true }).click()
      assert.equal(await page.locator('.sidebar').evaluate(sidebar => sidebar.getBoundingClientRect().left), 0)
      await page.getByRole('navigation', { name: 'Student navigation' }).getByRole('link', { name: 'My Passport', exact: true }).click()
      assert.equal(await page.getByRole('button', { name: 'Toggle navigation', exact: true }).getAttribute('aria-expanded'), 'false')
    }
    mode = 'blank'; await page.goto(base + '/student/dashboard'); await page.reload()
    await page.getByRole('heading', { name: 'No academic records linked yet', exact: true }).waitFor()
    for (const label of ['Download PDF', 'Share Passport']) assert.equal(await page.getByRole('button', { name: label, exact: true }).isDisabled(), true)
    assert.equal(await page.locator('.passport-green-seal').count(), 0)
    assert.doesNotMatch(await page.locator('main').innerText(), /Blockchain verified|Persisted reasoning|00000000-/)
    await page.getByRole('button', { name: 'Verified AI Skillset', exact: true }).click()
    assert.equal(await page.locator('.passport-slide[aria-hidden=false] .passport-stamp-grid article').count(), 0)
    await page.getByRole('button', { name: 'AI Skill Supplement', exact: true }).click()
    assert.equal(await page.locator('.passport-slide[aria-hidden=false] tbody tr').count(), 0)
    await page.getByRole('button', { name: 'Cover', exact: true }).click()
    await capture('blank-passport')
    await page.getByRole('link', { name: 'View History', exact: true }).click()
    await page.getByRole('heading', { name: 'No passport history yet', exact: true }).waitFor()
    await capture('empty-history')
    mode = 'unlinked'; await page.goto(base + '/student/dashboard'); await page.reload()
    await page.getByRole('heading', { name: 'No academic records linked yet', exact: true }).waitFor()
    assert.doesNotMatch(await page.locator('main').innerText(), /Authenticated Student|unit.student@|Persisted reasoning|00000000-/)
    await capture('unlinked-passport')
    await page.getByRole('link', { name: 'View History', exact: true }).click()
    await page.getByRole('heading', { name: 'No passport history yet', exact: true }).waitFor()
    assert.ok(requests.filter(r => r.width === width && r.mode === 'unlinked').every(r => r.resource === 'accounts/me/'))
    results.push({ width, passed: true, checks: ['four passport sections', 'keyboard', 'history pagination and current version', 'version details', 'coming soon', 'blank linked and unlinked', 'empty history', 'no horizontal overflow'] })
    console.log(`PASS redesigned Student pages at ${width}px`)
    await context.close()
  }
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ synthetic: true, mockedResponses: true, results, errors, requests }, null, 2))
  console.log(`Synthetic UI screenshots and report: ${output}`)
} finally { await browser.close(); await server.close() }
