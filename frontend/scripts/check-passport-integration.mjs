import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { dashboard, passport, version } from './student-fixtures.mjs'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' },
  optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom' })
try {
  const { passportState } = await server.ssrLoadModule('/src/student/proof.ts')
  const { parsePassport } = await server.ssrLoadModule('/src/student/contracts.ts')
  const { parseVerification, registrySources } = await server.ssrLoadModule('/src/verification/adapters.ts')
  const { blockchainAvailability } = await server.ssrLoadModule('/src/verification/blockchain.ts')
  const proof = { status: 'CONFIRMED', source: 'POLYGON_PDF_COMMITMENT_V1', blockchain_verified: true,
    institutional_issuer_approved: true, issuer_key_authorized: true, passport_status: 'ACTIVE',
    onchain_status: 'ACTIVE', registry_status: 'VALID', credential_status: 'VALID',
    environment: 'LOCAL_ANVIL', chain_id: 31337, transaction_hash: '0x' + '1'.repeat(64),
    confirmations: 3, required_confirmations: 2, passport_reference: passport.public_reference,
    version_reference: version.public_reference }
  const current = { ...passport, status: 'BLOCKCHAIN_VERIFIED', lifecycle_status: 'ACTIVE', blockchain: proof }
  assert.equal(passportState(parsePassport(current)).currentValid, true)
  for (const [key, value] of [['blockchain_verified', false], ['institutional_issuer_approved', false],
    ['issuer_key_authorized', false], ['onchain_status', 'REVOKED'], ['registry_status', 'OUTDATED'],
    ['credential_status', 'REVOKED'], ['confirmations', 1], ['required_confirmations', 0],
    ['chain_id', 1], ['environment', 'POLYGON_AMOY'], ['transaction_hash', '0x12'],
    ['passport_reference', version.public_reference], ['version_reference', passport.public_reference]]) {
    assert.equal(passportState({ ...current, blockchain: { ...proof, [key]: value } }).currentValid, false, key)
  }
  for (const lifecycle of ['REVOKED', 'REPLACED', 'EXPIRED', 'INVALID']) {
    const state = passportState({ ...current, lifecycle_status: lifecycle })
    assert.equal(state.currentValid, false); assert.equal(state.retired, true)
  }
  for (const [status, expected] of [['PENDING_BLOCKCHAIN', 'pending'], ['FAILED', 'failed'],
    ['NOT_CONFIGURED', 'not_configured'], ['UNAVAILABLE', 'unavailable']]) {
    assert.equal(blockchainAvailability({ status }), expected)
    assert.equal(passportState({ ...current, blockchain: { status } }).currentValid, false)
  }
  const result = { status: 'VALID', authentic: true, is_latest: true, passport_version: 1, latest_version: 1,
    credential_status: 'VALID', credential_counts: { VALID: 1, REVOKED: 0, EXPIRED: 0, INVALID: 0 },
    source: registrySources.passport, blockchain: proof, student_email: 'MUST-NOT-ESCAPE', secret: 'MUST-NOT-ESCAPE' }
  const trusted = Object.values(registrySources)
  const parsed = parseVerification(result, 'passport', trusted, passport.public_reference)
  assert.equal(parsed.status, 'valid'); assert.equal(parsed.blockchain, 'verified')
  assert.ok(!JSON.stringify(parsed).includes('MUST-NOT-ESCAPE'))
  assert.equal(parseVerification(result, 'passport', trusted, version.public_reference).reason, 'contract')
  for (const [status, expected] of [['REPLACED', 'replaced'], ['PENDING_BLOCKCHAIN', 'pending'], ['REVOKED', 'revoked']]) {
    assert.equal(parseVerification({ ...result, status }, 'passport', trusted).status, expected)
  }
  const registryOnly = parseVerification({ ...result, blockchain: { status: 'FAILED' } }, 'passport', trusted)
  assert.equal(registryOnly.status, 'valid'); assert.equal(registryOnly.blockchain, 'failed')
  assert.equal(parseVerification({ ...result, status: 'REPLACED', is_latest: false }, 'passport', trusted).status, 'replaced')
  assert.equal(parseVerification({ ...result, status: 'NOT_ISSUED', authentic: false, is_latest: null,
    passport_version: null, latest_version: null, credential_status: 'UNVERIFIABLE', credential_counts: {},
    blockchain: undefined }, 'passport', trusted).status, 'not_issued')
  assert.equal(parsePassport({ ...current }).blockchain, proof)
  assert.equal(dashboard.profile.first_name.length > 0, true)
  console.log('PASS Passport integration contracts: bound current proof, confirmations, lifecycle precedence, pending/failed/unconfigured states, unissued identity, public privacy and private metadata preservation. Synthetic contracts; real browser/Django acceptance is separate.')
} finally { await server.close() }
