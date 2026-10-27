import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createServer } from 'vite'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom' })
try {
  const { parseVerification } = await server.ssrLoadModule('/src/verification/service.ts')
  const { blockchainAvailability } = await server.ssrLoadModule('/src/verification/blockchain.ts')
  const { passportPresentation } = await server.ssrLoadModule('/src/live/passport.ts')
  const { parsePreview } = await server.ssrLoadModule('/src/live/spreadsheet-contracts.ts')
  const fixture = JSON.parse(fs.readFileSync(new URL('./fixtures/backend-bec0d83.json', import.meta.url)))
  for (const { method, body } of fixture.responses) {
    const out = parseVerification(body, method, [body.source])
    assert.equal(out.kind, 'result', body.status)
    assert.equal(out.status, body.status.toLowerCase(), body.status)
    if (body.status === 'VALID') assert.equal(out.blockchain, 'verified')
    assert.ok(!JSON.stringify(out).includes('transaction_hash'), 'Public UI must not retain arbitrary proof data')
  }
  const body = fixture.responses.find(r => r.body.status === 'VALID').body
  const proof = body.blockchain
  const React = await import('react'), { renderToString } = await import('react-dom/server'), { MemoryRouter } = await import('react-router-dom')
  const { VerificationResultView } = await server.ssrLoadModule('/src/verification/pages.tsx')
  const render = value => renderToString(React.createElement(MemoryRouter, {}, React.createElement(VerificationResultView, { outcome: parseVerification(value, 'passport', [value.source]) })))
  assert.match(render(body), /Blockchain Verified/)
  assert.doesNotMatch(render({ ...body, blockchain: { status: 'CONFIRMED' } }), /Blockchain Verified|verify-valid/)
  assert.doesNotMatch(render({ ...body, status: 'REVOKED' }), /Blockchain Verified|verify-valid/)
  for (const field of ['blockchain_verified', 'institutional_issuer_approved', 'issuer_key_authorized']) {
    assert.notEqual(blockchainAvailability({ ...proof, [field]: false }), 'verified')
    assert.notEqual(blockchainAvailability({ ...proof, [field]: 'true' }), 'verified')
  }
  for (const [field, value] of [['source', 'SIMULATED'], ['onchain_status', 'REVOKED'], ['chain_id', 1], ['transaction_hash', 'invalid']]) assert.notEqual(blockchainAvailability({ ...proof, [field]: value }), 'verified')
  const current = { public_reference: proof.passport_reference, status: 'BLOCKCHAIN_VERIFIED', lifecycle_status: 'ACTIVE', latest_version: { status: 'ISSUED', public_reference: proof.version_reference }, blockchain: proof }
  assert.equal(passportPresentation(current, true).currentValid, true)
  assert.equal(passportPresentation(current, false).currentValid, false)
  assert.equal(passportPresentation({ ...current, public_reference: 'different-passport' }, true).currentValid, false)
  for (const state of ['REPLACED', 'REVOKED', 'EXPIRED', 'INVALID', 'NOT_ISSUED']) assert.equal(passportPresentation({ ...current, status: state }, true).currentValid, false)
  for (const [state, expected] of [['PENDING_BLOCKCHAIN', 'pending'], ['FAILED', 'failed'], ['UNAVAILABLE', 'unverifiable'], ['NOT_CONFIGURED', 'unverifiable'], ['UNVERIFIABLE', 'unverifiable']]) {
    const result = parseVerification({ ...body, status: state === 'PENDING_BLOCKCHAIN' ? state : 'UNVERIFIABLE', authentic: false, blockchain: { status: state } }, 'passport', [body.source])
    assert.equal(result.status, expected)
  }
  const preview = { id: '00000000-0000-0000-0000-000000000001', state: 'READY', snapshot_sha256: 'a'.repeat(64), expires_at: '2099-01-01T00:00:00Z', report: { valid_records: 1, duplicate_records: 1, invalid_records: 1, review_records: 1, rows: [] }, result: null }
  assert.equal(parsePreview(preview).state, 'READY')
  assert.throws(() => parsePreview({ ...preview, snapshot_sha256: 'changed' }))
  assert.throws(() => parsePreview({ ...preview, report: { ...preview.report, valid_records: -1 } }))
  console.log('Final integration contracts passed: recorded backend public responses, confirmed-proof gates, lifecycle precedence and spreadsheet preview validation. Fixture replay only; no live Django or blockchain call.')
} finally { await server.close() }
