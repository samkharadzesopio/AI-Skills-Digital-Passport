// Native Chrome regression for the actual StrictMode React Dialog. No backend needed.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { createServer } from 'vite'

assert.ok(process.env.BTU_BROWSER_TOOLS && process.env.BTU_TEST_ARTIFACTS,
  'Provide BTU_BROWSER_TOOLS and a run-owned BTU_TEST_ARTIFACTS directory.')
const output = path.resolve(process.env.BTU_TEST_ARTIFACTS)
await fs.mkdir(output, { recursive: true })
// Any accidental API request fails closed at an unused loopback port.
process.env.BTU_DEV_API_TARGET = 'http://127.0.0.1:1'
const { chromium } = await import(pathToFileURL(path.join(process.env.BTU_BROWSER_TOOLS, 'node_modules/playwright/index.mjs')).href)
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': '"true"' },
  cacheDir: process.env.BTU_TEST_VITE_CACHE || path.join(output, 'vite-cache'),
  server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } })
let browser, context, page
const checks = [], apiRequests = [], pageErrors = []
const button = name => page.getByRole('button', { name, exact: true })
async function check(name, work) {
  await work()
  checks.push({ name, status: 'PASS' })
  console.log(`PASS ${name}`)
}
try {
  await server.listen()
  const base = `http://127.0.0.1:${server.httpServer.address().port}`
  browser = await chromium.launch({ headless: true, executablePath: process.env.BTU_BROWSER_EXECUTABLE || undefined })
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce', hasTouch: true })
  page = await context.newPage()
  page.setDefaultTimeout(6500)
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push({ method: request.method(), path: new URL(request.url()).pathname }) })
  page.on('pageerror', error => pageErrors.push({ name: error.name, message: error.message }))
  await page.goto(base + '/admin/skills')
  await button('Add category').waitFor()
  await page.evaluate(() => {
    window.__qaDialogs = []
    document.addEventListener('close', event => { if (event.target.tagName === 'DIALOG') window.__qaDialogs.push({ event: 'native-close', connected: event.target.isConnected, open: event.target.open }) }, true)
    new MutationObserver(changes => {
      for (const change of changes) for (const [nodes, event] of [[change.addedNodes, 'dialog-added'], [change.removedNodes, 'dialog-removed']]) {
        for (const node of nodes) if (node.nodeType === 1 && (node.tagName === 'DIALOG' || node.querySelector('dialog'))) window.__qaDialogs.push({ event })
      }
    }).observe(document.body, { childList: true, subtree: true })
  })
  await check('StrictMode keeps the reopened native modal mounted', async () => {
    await button('Add category').focus()
    await page.keyboard.press('Enter')
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    const state = { events: await page.evaluate(() => window.__qaDialogs), count: await page.locator('dialog').count(), open: await page.locator('dialog[open]').count() }
    await fs.writeFile(path.join(output, 'dialog-lifecycle.json'), JSON.stringify(state, null, 2))
    assert.equal(state.count, 1)
    assert.equal(state.open, 1)
    assert.ok(state.events.some(event => event.event === 'native-close' && event.open), 'StrictMode cleanup/reopen must actually occur')
  })
  await check('Tab and Shift+Tab exclude background controls', async () => {
    const focus = []
    for (const key of ['Tab', 'Shift+Tab']) for (let i = 0; i < 9; i++) {
      await page.keyboard.press(key)
      const state = await page.evaluate(() => ({ tag: document.activeElement?.tagName, id: document.activeElement?.id,
        modal: document.querySelector('dialog')?.matches(':modal'), inside: document.querySelector('dialog')?.contains(document.activeElement), browserChrome: document.activeElement === document.body }))
      focus.push({ key, ...state })
      assert.equal(state.modal, true)
      // Native Chrome can move focus into its own chrome, represented by body.
      assert.ok(state.inside || state.browserChrome)
    }
    await fs.writeFile(path.join(output, 'dialog-keyboard-focus.json'), JSON.stringify(focus, null, 2))
  })
  await check('Escape dismisses and restores the opening control', async () => {
    await page.locator('#catalog-name').focus()
    await page.keyboard.press('Escape')
    await page.locator('dialog').waitFor({ state: 'detached' })
    assert.equal(await button('Add category').evaluate(element => element === document.activeElement), true)
  })
  await check('A genuine native close event dismisses', async () => {
    await button('Add category').click()
    await page.locator('dialog[open]').waitFor()
    await page.locator('dialog').evaluate(dialog => dialog.close())
    await page.locator('dialog').waitFor({ state: 'detached' })
  })
  await check('Close icon dismisses without saving', async () => {
    await button('Add category').click()
    await page.locator('#catalog-name').fill('QA icon cancelled')
    await button('Close dialog').click()
    await page.locator('dialog').waitFor({ state: 'detached' })
    assert.equal(await page.getByText('QA icon cancelled', { exact: true }).count(), 0)
  })
  await check('Form Cancel does not save', async () => {
    await button('Add category').click()
    await page.locator('#catalog-name').fill('QA lifecycle cancelled')
    await button('Cancel').click()
    await page.locator('dialog').waitFor({ state: 'detached' })
    assert.equal(await page.getByText('QA lifecycle cancelled', { exact: true }).count(), 0)
  })
  await check('Form Save survives client navigation and Reset removes it', async () => {
    await button('Add category').click()
    await page.locator('#catalog-name').fill('QA lifecycle saved')
    await button('Save demo draft').click()
    await page.locator('dialog').waitFor({ state: 'detached' })
    await page.getByText('QA lifecycle saved', { exact: true }).waitFor()
    await page.locator('.sidebar nav a[href="/admin/dashboard"]').click()
    await page.waitForURL(base + '/admin/dashboard')
    await page.locator('.sidebar nav a[href="/admin/skills"]').click()
    await page.waitForURL(base + '/admin/skills')
    await page.getByText('QA lifecycle saved', { exact: true }).waitFor()
    await button('Reset demo drafts').click()
    await page.getByText('QA lifecycle saved', { exact: true }).waitFor({ state: 'hidden' })
  })
  assert.deepEqual(apiRequests, [])
  assert.deepEqual(pageErrors, [])
} catch (error) {
  checks.push({ name: 'Focused Dialog regression', status: 'FAIL', error: error.message })
  if (page) await page.screenshot({ path: path.join(output, 'dialog-failure.png'), fullPage: true }).catch(() => {})
  process.exitCode = 1
} finally {
  await context?.close()
  await browser?.close()
  await server.close()
  await fs.writeFile(path.join(output, 'dialog-results.json'), JSON.stringify({ syntheticDemo: true, mockedSuccessfulResponses: false, checks, apiRequests, pageErrors }, null, 2))
  console.log(JSON.stringify({ passed: checks.filter(check => check.status === 'PASS').length, failed: checks.filter(check => check.status === 'FAIL').length, apiRequests: apiRequests.length, pageErrors: pageErrors.length }))
}
