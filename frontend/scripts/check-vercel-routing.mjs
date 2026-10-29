// Compile with Vercel's own routing-utils, then exercise a loopback proxy model.
// This does not certify Vercel's deployed edge, TLS, headers or cookie behavior.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs/promises'
import http from 'node:http'
import path from 'node:path'
import { createRequire } from 'node:module'

assert.ok(process.env.BTU_VERCEL_ROUTING_TOOLS, 'Provide an isolated @vercel/routing-utils installation')
const require = createRequire(path.join(process.env.BTU_VERCEL_ROUTING_TOOLS, 'package.json'))
const { convertRewrites, sourceToRegex, getTransformedRoutes } = require('@vercel/routing-utils')
const { version } = require('@vercel/routing-utils/package.json')
const config = JSON.parse(await fs.readFile(new URL('../vercel.json', import.meta.url), 'utf8'))
assert.equal(getTransformedRoutes(config).error, null, 'Vercel must accept the complete rewrite/header configuration')
const routes = convertRewrites(config.rewrites)
const backend = 'https://ai-skills-digital-passport.onrender.com'
function destination(value) {
  const input = new URL(value, 'https://frontend.synthetic.invalid')
  const route = routes.find(r => new RegExp(r.src).test(input.pathname))
  assert.ok(route)
  assert.equal(route.status, undefined, 'A rewrite must not redirect POST requests')
  assert.equal(route.methods, undefined, 'All methods must reach the backend')
  return input.pathname.replace(new RegExp(route.src), route.dest) + input.search
}
const apiPaths = ['/api', '/api/', '/api/accounts/csrf/', '/api/accounts/otp/request/',
  '/api/accounts/otp/verify/', '/api/accounts/login/', '/api/accounts/me/',
  '/api/verification/document/', '/api/verification/passport/00000000-0000-4000-8000-000000000000/',
  '/api/verification/credential%3Asynthetic/', '/api/accounts/csrf']
for (const pathname of apiPaths) {
  const query = '?kind=passport&tag=one&tag=two&value=%E1%83%90%2F%2B'
  assert.equal(destination(pathname + query), backend + pathname + query,
    'API paths, trailing slashes, escaping and repeated query fields must survive')
  const headers = config.headers.filter(h => new RegExp(sourceToRegex(h.source).src).test(pathname))
    .flatMap(h => h.headers)
  assert.ok(headers.some(h => h.key.toLowerCase() === 'x-vercel-enable-rewrite-caching' && h.value === '0'))
  assert.ok(headers.some(h => h.key.toLowerCase() === 'cache-control' && h.value.split(',').map(value => value.trim().toLowerCase()).includes('no-store')))
}
for (const pathname of ['/', '/api-guide', '/verify', '/verify/result', '/student/login', '/admin/login', '/student/dashboard']) {
  assert.equal(destination(pathname), '/index.html')
}
const old = convertRewrites([{ source: '/api/:path*', destination: backend + '/api/:path*' }])[0]
assert.equal(new RegExp(old.src).test('/api/accounts/csrf/'), false,
  'The previous wildcard drops trailing-slash API paths into the SPA fallback')

const hash = body => createHash('sha256').update(body).digest('hex')
const servers = []
async function listen(handler) {
  const server = http.createServer(handler)
  servers.push(server)
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
  return `http://127.0.0.1:${server.address().port}`
}
try {
  const upstream = await listen(async (request, response) => {
    const chunks = []
    for await (const chunk of request) chunks.push(chunk)
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store',
      'Set-Cookie': ['csrftoken=synthetic; Secure; HttpOnly; SameSite=Lax; Path=/',
        'sessionid=synthetic; Secure; HttpOnly; SameSite=Lax; Path=/'] })
    response.end(JSON.stringify({ method: request.method, url: request.url,
      contentType: request.headers['content-type'] || null, cookie: request.headers.cookie,
      csrf: request.headers['x-csrftoken'], bodyHash: hash(Buffer.concat(chunks)) }))
  })
  const proxy = await listen((request, response) => {
    const target = destination(request.url)
    if (target === '/index.html') { response.writeHead(200, { 'Content-Type': 'text/html' }); response.end('<div id="root"></div>'); return }
    assert.equal(new URL(target).origin, backend)
    const local = new URL(target.slice(backend.length), upstream)
    const child = http.request(local, { method: request.method, headers: { ...request.headers, host: local.host } }, result => {
      response.writeHead(result.statusCode, result.headers)
      result.pipe(response)
    })
    child.on('error', error => response.destroy(error))
    request.pipe(child)
  })
  const multipart = Buffer.concat([Buffer.from('--synthetic\r\nContent-Disposition: form-data; name="file"; filename="passport.pdf"\r\nContent-Type: application/pdf\r\n\r\n'),
    Buffer.from([37, 80, 68, 70, 0, 255, 10]), Buffer.from('\r\n--synthetic--\r\n')])
  for (const [method, pathname, body, contentType] of [
    ['GET', '/api/accounts/csrf/', undefined, undefined],
    ['POST', '/api/accounts/login/', Buffer.from('{"synthetic":true}'), 'application/json'],
    ['POST', '/api/verification/document/', multipart, 'multipart/form-data; boundary=synthetic'],
  ]) {
    const query = '?tag=one&tag=two&reference=a%2Fb'
    const headers = { Cookie: 'csrftoken=synthetic; sessionid=synthetic', 'X-CSRFToken': 'synthetic' }
    if (contentType) headers['Content-Type'] = contentType
    const response = await fetch(proxy + pathname + query, { method, body, headers, redirect: 'error' })
    assert.equal(response.status, 200)
    assert.equal(response.headers.get('cache-control'), 'no-store')
    assert.equal(response.headers.getSetCookie().length, 2)
    for (const cookie of response.headers.getSetCookie()) {
      assert.match(cookie, /Secure; HttpOnly; SameSite=Lax; Path=\//)
      assert.doesNotMatch(cookie, /Domain=/i)
    }
    assert.deepEqual(await response.json(), { method, url: pathname + query, contentType: contentType || null,
      cookie: headers.Cookie, csrf: 'synthetic', bodyHash: hash(body || Buffer.alloc(0)) })
  }
  assert.match(await (await fetch(proxy + '/verify')).text(), /id="root"/)
  console.log(`Routing passed: @vercel/routing-utils ${version}; exact API paths/slashes/query; SPA deep links; no API caching; loopback GET, JSON POST, multipart bytes and two cookies. Deployed edge remains untested.`)
} finally {
  await Promise.all(servers.map(server => new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))))
}
