import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import { JSDOM } from 'jsdom'
import { createServer } from 'vite'
import React from 'react'
import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const previous = Object.getOwnPropertyDescriptor(globalThis, 'window')
const previousStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
const dom = new JSDOM('', { url: 'https://frontend.example/verify' })
Object.defineProperty(globalThis, 'window', { configurable: true, value: dom.window })
Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: dom.window.localStorage })
const servers = []
async function runtime() {
  const server = await createServer({
    define: { 'import.meta.env.VITE_ENABLE_DEMO': '"true"', 'import.meta.env.VITE_GOOGLE_CLIENT_ID': '""' },
    server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom',
  })
  servers.push(server)
  return server
}
async function render(server, route) {
  const { AppRoutes } = await server.ssrLoadModule('/src/App.tsx')
  const { LocaleProvider } = await server.ssrLoadModule('/src/i18n.tsx')
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  try {
    return renderToString(React.createElement(QueryClientProvider, { client },
      React.createElement(LocaleProvider, null, React.createElement(MemoryRouter,
        { initialEntries: [route] }, React.createElement(AppRoutes)))))
  } finally { client.clear() }
}
try {
  const config = JSON.parse(await fs.readFile(new URL('../vercel.json', import.meta.url), 'utf8'))
  assert.deepEqual(config.rewrites, [
    { source: '/api:tail(/.*)?', destination: 'https://ai-skills-digital-passport.onrender.com/api:tail' },
    { source: '/((?!api(?:/|$)).*)', destination: '/index.html' },
  ], 'API requests must reach Render before the SPA fallback handles deep links')
  const fallback = new RegExp('^' + config.rewrites[1].source + '$')
  for (const route of ['/api', '/api/', '/api/accounts/csrf/', '/api/verification/passport/reference/']) {
    assert.equal(fallback.test(route), false, `${route} must never resolve to the React index`)
  }
  for (const route of ['/', '/verify', '/verify/reference', '/student/login', '/admin/login', '/api-guide']) {
    assert.equal(fallback.test(route), true, `${route} retains React deep-link fallback`)
  }
  const preview = await runtime()
  assert.equal((await preview.ssrLoadModule('/src/demo/mode.ts')).demoMode, true)
  const html = new JSDOM(await render(preview, '/verify'))
  const links = [...html.window.document.querySelectorAll('header .verify-sign-in-nav a')]
  assert.deepEqual(links.map(a => [a.textContent, a.getAttribute('href')]), [
    ['Student sign in', '/student/login?auth=live'],
    ['Administrator sign in', '/admin/login?auth=live'],
  ])
  assert.ok(html.window.document.querySelector('.verify-brand .official-btu-logo'))
  assert.equal(html.window.document.querySelector('header .verify-language').textContent, 'EN')
  assert.ok(html.window.document.querySelector('#verification-main'))
  dom.window.localStorage.setItem('btu-locale', 'ka')
  const translated = new JSDOM(await render(preview, '/verify'))
  assert.equal(translated.window.document.querySelector('header .verify-language').textContent, 'KA')
  assert.equal(translated.window.document.querySelectorAll('header .verify-sign-in-nav a').length, 2)
  dom.window.localStorage.clear()

  for (const [route, expected] of [['/student/login', 'Google sign-in is awaiting university configuration.'], ['/admin/login', 'admin-password']]) {
    dom.window.sessionStorage.clear()
    dom.reconfigure({ url: `https://frontend.example${route}?auth=live` })
    const live = await runtime()
    assert.equal((await live.ssrLoadModule('/src/demo/mode.ts')).demoMode, false,
      'Explicit sign-in must leave the demo before API clients initialize')
    const login = await render(live, `${route}?auth=live`)
    assert.ok(login.includes(expected), `${route} must render the actual authentication page`)
    assert.ok(!login.includes('Open demo workspace'))
    assert.ok(!login.includes('Demo Mode — no sign-in required'))
    dom.reconfigure({ url: `https://frontend.example${route.replace('/login', '/dashboard')}` })
    const refreshed = await runtime()
    assert.equal((await refreshed.ssrLoadModule('/src/demo/mode.ts')).demoMode, false,
      'A dashboard refresh after real sign-in must never re-enter a mock workspace')
    const { accessDecision } = await refreshed.ssrLoadModule('/src/auth/contracts.ts')
    const role = route.startsWith('/student') ? 'student' : 'administrator'
    assert.equal(accessDecision({ status: 'anonymous' }, role), 'login',
      'Selecting real authentication grants no access')
  }
  dom.window.sessionStorage.clear()
  dom.reconfigure({ url: 'https://frontend.example/verify?auth=live' })
  assert.equal((await (await runtime()).ssrLoadModule('/src/demo/mode.ts')).demoMode, true,
    'Only explicit login routes may select real authentication')
  console.log('Verification navigation passed: both localized header links, branding/language, real student/admin forms, refresh isolation, and anonymous access denial.')
} finally {
  await Promise.all(servers.map(server => server.close()))
  dom.window.close()
  if (previous) Object.defineProperty(globalThis, 'window', previous)
  else delete globalThis.window
  if (previousStorage) Object.defineProperty(globalThis, 'localStorage', previousStorage)
  else delete globalThis.localStorage
}
