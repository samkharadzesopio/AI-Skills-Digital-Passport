import assert from 'node:assert/strict'
import fs from 'node:fs'
import crypto from 'node:crypto'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom' })
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173/' }), previous = new Map()
let root
try {
  for (const key of ['window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node']) { previous.set(key, Object.getOwnPropertyDescriptor(globalThis, key)); Object.defineProperty(globalThis, key, { configurable: true, writable: true, value: dom.window[key] }) }
  previous.set('IS_REACT_ACT_ENVIRONMENT', Object.getOwnPropertyDescriptor(globalThis, 'IS_REACT_ACT_ENVIRONMENT'))
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  previous.set('ResizeObserver', Object.getOwnPropertyDescriptor(globalThis, 'ResizeObserver'))
  let observed, disconnected = 0
  globalThis.ResizeObserver = class {
    constructor(callback) { this.callback = callback }
    observe(element) { observed = { element, callback: this.callback } }
    disconnect() { disconnected++ }
  }
  const React = await import('react'), { act } = React, { createRoot } = await import('react-dom/client'), { renderToString } = await import('react-dom/server')
  const { PassportCard } = await server.ssrLoadModule('/src/components/PassportCard.tsx')
  const { demonstrationPassport } = await server.ssrLoadModule('/src/data/passport-artwork-demo.ts')
  const { backendPassportCard } = await server.ssrLoadModule('/src/components/passport-card-data.ts')
  const markup = renderToString(React.createElement(PassportCard, { data: demonstrationPassport }))
  assert.doesNotMatch(markup, /<iframe|<object|<embed|Blockchain Verified|DEMO-PASSPORT/)
  assert.match(markup, /FICTIONAL STUDENT/)
  assert.match(markup, /NOT ISSUED/)
  assert.match(markup, /do not constitute a mandatory sequence/)
  const backend = backendPassportCard({ public_reference: 'public-ref', status: 'BLOCKCHAIN_VERIFIED', latest_version: { issued_at: '2026-10-20', skills: [{ skill_id: 'real-skill', skill_name: 'Authorized AI skill', stamp_type: 'FOCUSED', description: 'Actual description' }] } }, { first_name: 'Actual', last_name: 'Student', id: 'PRIVATE-STUDENT-ID' })
  assert.equal(backend.demonstration, false); assert.equal(backend.skills[0].earnedOn, null)
  assert.equal(backend.skills[0].experience, null, 'Do not invent a learning experience from snapshot metadata')
  assert.equal(backend.status, 'PROOF_NOT_CONFIRMED')
  const realMarkup = renderToString(React.createElement(PassportCard, { data: backend }))
  assert.equal(backend.skills[0].name, 'Authorized AI skill'); assert.doesNotMatch(realMarkup, /PRIVATE-STUDENT-ID|Fictional|Blockchain Verified/)
  const hash = path => crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex')
  for (const file of ['ai_skill.png', 'ai_applied.png', 'ai_advanced.png']) assert.equal(hash(`public/brand/${file}`), hash(`../backend/stamps/${file}`))
  for (const file of ['btu-logo.svg', 'passport-title.svg', 'passport-asterisk.svg', 'passport-seal.svg']) {
    const asset = fs.readFileSync(`public/brand/${file}`, 'utf8'); assert.match(asset, /<.*svg/); assert.doesNotMatch(asset, /<image|<script|foreignObject|https?:\/\/[^"\s]+\.(png|jpg)/)
  }
  root = createRoot(document.getElementById('root'))
  await act(async () => root.render(React.createElement(PassportCard, { data: demonstrationPassport })))
  const card = () => document.querySelector('.passport-carousel'), active = () => [...document.querySelectorAll('.passport-slide')].findIndex(slide => slide.getAttribute('aria-hidden') === 'false')
  const click = async label => { const button = document.querySelector(`button[aria-label="${label}"]`); assert.ok(button); await act(async () => button.click()) }
  const press = async key => { await act(async () => card().dispatchEvent(new window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))) }
  assert.equal(active(), 0); assert.equal(document.querySelectorAll('.passport-slide[inert]').length, 3)
  await click('Next passport view'); assert.equal(active(), 1)
  await press('ArrowRight'); assert.equal(active(), 2)
  await press('End'); assert.equal(active(), 3)
  assert.equal(document.querySelector('button[aria-label="Next passport view"]').disabled, true)
  await press('Home'); assert.equal(active(), 0)
  assert.equal(document.querySelector('button[aria-label="Previous passport view"]').disabled, true)
  await click('Verified AI Skillset'); assert.equal(active(), 2)
  async function pointer(target, type, x, y) {
    const event = new window.Event(type, { bubbles: true }); Object.assign(event, { clientX: x, clientY: y, pointerType: 'touch', pointerId: 1 })
    await act(async () => target.dispatchEvent(event))
  }
  const viewport = document.querySelector('.passport-viewport')
  for (const width of [1920,1366,1024,768,390,375]) {
    Object.defineProperty(viewport, 'clientWidth', { configurable: true, value: width })
    await act(async () => observed.callback([]))
    assert.equal(Number(card().style.getPropertyValue('--passport-scale')), width / 1000)
  }
  await pointer(viewport, 'pointerdown', 240, 200); await pointer(viewport, 'pointerup', 100, 205); assert.equal(active(), 3)
  await pointer(viewport, 'pointerdown', 100, 100); await pointer(viewport, 'pointerup', 105, 230); assert.equal(active(), 3, 'Vertical scroll must not change views')
  assert.equal(document.querySelector('.passport-table-wrap'), null, 'Supplement must not introduce an internal scroll region')
  await pointer(viewport, 'pointerdown', 100, 200); await pointer(viewport, 'pointerup', 240, 205); assert.equal(active(), 2)
  const { paginatePassport, wrapPassportText } = await server.ssrLoadModule('/src/components/passport-pagination.ts')
  const large = Array.from({ length: 31 }, (_, i) => ({ id: 'large-' + i, name: i === 0 ? 'Long name '.repeat(60) : 'Skill ' + i, description: i === 1 ? 'A full description without truncation. '.repeat(90) : 'Description ' + i, stampType: 'FOCUSED', experience: 'Learning experience ' + i, earnedOn: '2026-10-20' }))
  const pages = paginatePassport(large)
  assert.ok(pages.length > 4)
  assert.deepEqual(paginatePassport(large), pages, 'Pagination is deterministic')
  const unicode = 'Georgian: \u10e5\u10d0\u10e0\u10d7\u10e3\u10da\u10d8. Emoji: \u{1f469}\u200d\u{1f4bb}.\nNew line.'
  assert.equal(wrapPassportText(unicode, 7).join(''), unicode)
  for (const skill of large) {
    const rows = pages.flatMap(page => page.rows).filter(row => row.skill.id === skill.id)
    for (const [column, expected] of [[1,skill.name],[2,skill.description],[3,skill.experience],[4,skill.earnedOn]]) assert.equal(rows.flatMap(row => row.cells[column]).join(''), expected, 'Every source character is preserved')
    assert.equal(pages.flatMap(page => page.tiles).filter(tile => tile.skill.id === skill.id).flatMap(tile => tile.name).join(''), skill.name)
  }
  for (const page of pages) { assert.ok(page.tiles.length <= 6); assert.ok(page.rows.reduce((sum,row) => sum + row.height,0) <= 360) }
  const repeated = { ...large[0], learningExperiences: [{ title: 'First learning experience', earnedOn: '2026-10-20' }, { title: 'Second learning experience', earnedOn: '2026-10-21' }] }
  const repeatedRows = paginatePassport([repeated]).flatMap(page => page.rows)
  for (const [index, experience] of repeated.learningExperiences.entries()) {
    const selected = repeatedRows.filter(row => row.experienceIndex === index)
    assert.equal(selected.flatMap(row => row.cells[3]).join(''), experience.title)
    assert.equal(selected.flatMap(row => row.cells[4]).join(''), experience.earnedOn)
  }
  const css = fs.readFileSync('src/components/passport-card.css', 'utf8')
  assert.match(css, /prefers-reduced-motion:\s*reduce/); assert.match(css, /transition:\s*none/); assert.match(css, /aspect-ratio:var\(--passport-ratio\)/); assert.doesNotMatch(css, /overflow(?:-x|-y)?:\s*(?:auto|scroll)/)
  function luminance(hex) { return hex.match(/\w\w/g).map(channel => parseInt(channel,16)/255).map(n => n <= .04045 ? n/12.92 : ((n+.055)/1.055)**2.4).reduce((sum,n,i) => sum+n*[.2126,.7152,.0722][i],0) }
  for (const [foreground, background] of [['111111','ff6a00'],['111111','ffffff'],['a63f00','ffffff'],['dddddd','2d2d2d']]) {
    const values = [luminance(foreground),luminance(background)].sort((a,b) => b-a)
    assert.ok((values[0]+.05)/(values[1]+.05) >= 4.5, `${foreground}/${background} body contrast`)
  }
  await act(async () => root.unmount()); root = null
  assert.equal(disconnected, 1, 'ResizeObserver must disconnect on unmount')
  console.log('Passport card checks passed: section/page navigation, touch, Unicode-safe lossless pagination, all learning experiences, resize scaling/cleanup, accessibility, motion, stamp hashes and privacy. Use check:passport-layout for graphical viewport verification.')
} finally {
  if (root) await (await import('react')).act(async () => root.unmount())
  for (const [key, descriptor] of previous) { if (descriptor) Object.defineProperty(globalThis,key,descriptor); else delete globalThis[key] }
  dom.window.close(); await server.close()
}
