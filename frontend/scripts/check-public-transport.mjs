import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import { once } from 'node:events'
import { createServer } from 'vite'

// Disposable HTTP fixture, not Django, a registry, or a blockchain provider.
const uuid = '00000000-0000-0000-0000-000000000001', source = 'contract-unit-registry'
let status = 'VALID', httpStatus = 200
const requests = [], failures = []
const fixture = createHttpServer(async (request, response) => {
  try {
    assert.equal(request.headers.cookie, undefined)
    assert.equal(request.headers.authorization, undefined)
    assert.equal(request.headers['x-csrftoken'], undefined)
    const chunks = []
    for await (const chunk of request) chunks.push(chunk)
    const body = Buffer.concat(chunks).toString()
    requests.push({ path: request.url, method: request.method })
    if (request.method === 'POST') {
      assert.equal(request.url, '/api/verification/document/')
      assert.match(request.headers['content-type'], /^multipart\/form-data;/)
      assert.match(body, /name="file"/)
    }
    response.writeHead(httpStatus, { 'Content-Type': 'application/json' })
    response.end(JSON.stringify({ source, status, authentic: true, passport_version: 1, latest_version: 1, is_latest: true, credential_status: status, credential_counts: { VALID: 1 }, message: 'Private message must not be exposed', student_email: 'private@example.invalid' }))
  } catch (error) { failures.push(error); response.writeHead(500); response.end('{}') }
})
fixture.listen(0, '127.0.0.1')
await once(fixture, 'listening')
const server = await createServer({
  define: {
    'import.meta.env.VITE_ENABLE_DEMO': 'false',
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify(`http://127.0.0.1:${fixture.address().port}/api/`),
    'import.meta.env.VITE_PUBLIC_VERIFICATION_ENABLED': '"true"',
    'import.meta.env.VITE_PUBLIC_VERIFICATION_SOURCES': JSON.stringify(source),
  },
  optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom',
})
try {
  const { lookupReference, uploadPdf, verificationConfig } = await server.ssrLoadModule('/src/verification/service.ts')
  assert.equal(verificationConfig.enabled, true)
  const signal = () => new AbortController().signal
  for (const reference of [`passport:${uuid}`, uuid]) {
    const result = await lookupReference(reference, 'passport', signal())
    assert.equal(result.status, 'valid')
    assert.equal(requests.at(-1).path, `/api/verification/passport/${uuid}/`)
    assert.ok(!JSON.stringify(result).includes('private@example.invalid'))
  }
  await lookupReference(`passport-version:${uuid}`, 'passport', signal())
  assert.equal(requests.at(-1).path, `/api/verification/passport-version/${uuid}/`)
  for (status of ['REVOKED', 'EXPIRED', 'UNVERIFIABLE']) {
    assert.equal((await lookupReference(uuid, 'passport', signal())).status, status.toLowerCase())
  }
  status = 'REVOKED'
  assert.equal((await uploadPdf(new File(['%PDF-synthetic'], 'passport.pdf', { type: 'application/pdf' }), signal(), () => {})).status, 'revoked')
  httpStatus = 503
  assert.equal((await lookupReference(uuid, 'passport', signal())).reason, 'server')
  assert.equal(failures.length, 0)
  console.log('Public transport checks passed against a disposable HTTP fixture: passport/version routing, anonymous requests, PDF multipart upload, revocation/expiry/unverifiable states and service failures. This was not real backend verification.')
} finally {
  await server.close()
  fixture.closeAllConnections()
  await new Promise(resolve => fixture.close(resolve))
}
