import assert from 'node:assert/strict'
import { createServer } from 'vite'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom' })
try {
  const { passportPresentation } = await server.ssrLoadModule('/src/live/passport.ts')
  const { parseVerification } = await server.ssrLoadModule('/src/verification/service.ts')
  const { parseProduct } = await server.ssrLoadModule('/src/services/product.ts')
  const current = { id: 'old-id', status: 'ISSUED', latest_version: { status: 'ISSUED', version_number: 2 } }
  assert.equal(passportPresentation(current, true).currentValid, true)
  assert.equal(passportPresentation(current, false).currentValid, false, 'History never promotes itself to current')
  for (const status of ['REVOKED', 'REPLACED', 'EXPIRED', 'INVALID']) {
    const retired = { ...current, status, lifecycle_status: status }
    assert.equal(passportPresentation(retired, true).currentValid, false)
    assert.equal(passportPresentation(retired, true).canPrepare, false)
    // Parent lifecycle overrides a stale nested ISSUED status.
    assert.equal(passportPresentation({ ...retired, status: 'ISSUED' }, true).canPrepare, false)
  }
  const replacement = { ...current, id: 'replacement-id', status: 'PENDING_BLOCKCHAIN', lifecycle_status: 'ACTIVE', blockchain: { status: 'PENDING_BLOCKCHAIN' } }
  assert.equal(passportPresentation(replacement, true).currentValid, false)
  assert.equal(passportPresentation(replacement, true).canPrepare, true, 'PDF preparation must not deadlock document anchoring')
  assert.equal(passportPresentation({ ...replacement, status: 'BLOCKCHAIN_VERIFIED', blockchain: undefined }, true).currentValid, false, 'A status label alone cannot prove blockchain validity')
  assert.equal(passportPresentation({ ...current, status: 'UNKNOWN' }, true).canPrepare, false)
  assert.throws(() => parseProduct({ passport: [] }))
  assert.throws(() => parseProduct({ result: [] }))
  assert.throws(() => parseProduct({ latest_version: [] }))
  const source = 'contract-unit-registry', trusted = [source]
  const registry = { status: 'VALID', authentic: true, is_latest: true, passport_version: 2, latest_version: 2, source }
  for (const [proof, expected] of [['PENDING_BLOCKCHAIN', 'pending'], ['FAILED', 'failed'], ['UNAVAILABLE', 'unverifiable'], ['NOT_CONFIGURED', 'unverifiable'], ['CONFIRMED', 'unverifiable']]) {
    const outcome = parseVerification({ ...registry, blockchain: { status: proof, blockchain_verified: true, private_student: 'SECRET' } }, 'passport', trusted)
    assert.equal(outcome.status, expected)
    assert.ok(!JSON.stringify(outcome).includes('SECRET'))
  }
  for (const status of ['REPLACED', 'REVOKED']) {
    const outcome = parseVerification({ ...registry, status, is_latest: false }, 'passport', trusted)
    assert.equal(outcome.status, status.toLowerCase(), 'An inactive latest snapshot is not an active passport')
  }
  assert.equal(parseVerification({ ...registry, status: 'PENDING_BLOCKCHAIN', blockchain: { status: 'FAILED' } }, 'passport', trusted).status, 'failed')
  assert.equal(parseVerification({ ...registry, blockchain: [] }, 'passport', trusted).status, 'unverifiable')
  assert.equal(parseVerification({ ...registry, blockchain: null }, 'passport', trusted).status, 'unverifiable')
  assert.equal(parseVerification({ ...registry, status: 'UNKNOWN' }, 'passport', trusted).reason, 'contract')
  const React = await import('react'), { renderToString } = await import('react-dom/server'), { MemoryRouter } = await import('react-router-dom')
  const { VerificationResultView } = await server.ssrLoadModule('/src/verification/pages.tsx')
  const render = outcome => renderToString(React.createElement(MemoryRouter, {}, React.createElement(VerificationResultView, { outcome })))
  for (const status of ['PENDING_BLOCKCHAIN', 'FAILED', 'UNAVAILABLE', 'CONFIRMED']) {
    const markup = render(parseVerification({ ...registry, blockchain: { status } }, 'passport', trusted))
    assert.doesNotMatch(markup, /verify-valid|Valid passport document|SECRET/)
  }
  assert.match(render(parseVerification({ ...registry, status: 'REPLACED', is_latest: false }, 'passport', trusted)), /Replaced passport/)
  console.log('Compatibility checks passed: current/history separation, parent lifecycle guards, replacement pending state, inactive latest snapshots, proof failure/privacy, malformed responses and no provisional blockchain success. Synthetic contracts only.')
} finally { await server.close() }
