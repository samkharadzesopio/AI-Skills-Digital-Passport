import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { AxiosError } from 'axios'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, server: { middlewareMode: true }, appType: 'custom' })
try {
  const { validateReference, validatePdf, MAX_PDF_BYTES, retryDeadline, isPublicApiBaseSafe } = await server.ssrLoadModule('/src/verification/validation.ts')
  const { parseVerification, mapVerificationError, lookupReference, uploadPdf, verificationConfig } = await server.ssrLoadModule('/src/verification/service.ts')
  // Synthetic contract inputs are test-only and are never imported by the application.
  const source = 'contract-unit-registry', trusted = [source], reference = 'unit-reference'
  const credential = status => ({ credential_id: reference, status, verified: status === 'VALID', source, private_student_email: 'private@example.invalid' })
  const document = (status, passport_version = null, latest_version = null) => ({ status, authentic: status === 'VALID' || status === 'OUTDATED', is_latest: status === 'VALID' ? true : status === 'OUTDATED' ? false : null, passport_version, latest_version, message: 'Private arbitrary text must not be displayed', source, private_record: { name: 'PRIVATE NAME' } })
  const uuid = '00000000-0000-0000-0000-000000000001'
  assert.equal(validateReference(`passport-version:${uuid}`, 'passport'), null)
  assert.equal(validateReference(`passport:${uuid}`, 'passport'), null)
  assert.equal(validateReference('student-id', 'passport'), 'passportFormat')
  assert.equal(validateReference('', 'passport'), 'referenceRequired')
  for (const value of ['../secret','/students/1','a\\b','a\u0000b','.', '..',`passport:${uuid}`]) assert.equal(validateReference(value,'credential'), 'credentialFormat')
  assert.equal(validateReference(reference,'credential'), null)
  assert.equal(validatePdf({ name: 'passport.pdf', type: 'application/pdf', size: MAX_PDF_BYTES }), null)
  assert.equal(validatePdf({ name: 'passport.PDF', type: '', size: 100 }), null)
  assert.equal(validatePdf({ name: 'passport.pdf', type: 'application/pdf', size: MAX_PDF_BYTES + 1 }), 'pdfSize')
  assert.equal(validatePdf({ name: 'passport.pdf', type: 'application/pdf', size: 0 }), 'pdfSize')
  assert.equal(validatePdf({ name: 'passport.pdf', type: 'text/html', size: 100 }), 'pdfType')
  assert.equal(validatePdf({ name: 'passport.exe', type: 'application/pdf', size: 100 }), 'pdfType')
  for (const [status, expected] of [['VALID','valid'],['REVOKED','revoked'],['EXPIRED','expired'],['INVALID','invalid'],['NOT_FOUND','not_found']]) {
    const result = parseVerification(credential(status),'credential',trusted,reference)
    assert.equal(result.kind,'result'); assert.equal(result.status,expected)
    assert.deepEqual(Object.keys(result.publicInfo),['credentialId'])
    assert.ok(!JSON.stringify(result).includes('private@example.invalid'))
  }
  for (const [input,status] of [[document('VALID',2,2),'valid'],[document('OUTDATED',1,2),'outdated'],[document('INVALID'),'invalid'],[document('UNVERIFIABLE'),'unverifiable']]) {
    const result = parseVerification(input,'document',trusted)
    assert.equal(result.kind,'result'); assert.equal(result.status,status)
    assert.ok(!JSON.stringify(result).includes('PRIVATE NAME'))
    assert.ok(!JSON.stringify(result).includes('Private arbitrary text'))
  }
  for (const source of ['SIMULATED_CREDENTIAL_REGISTRY','SIMULATED_DOCUMENT_REGISTRY','MOCK_REGISTRY']) assert.equal(parseVerification({ ...credential('VALID'),source },'credential',[source],reference).reason,'simulated')
  assert.equal(parseVerification(credential('VALID'),'credential',[],reference).reason,'untrusted')
  assert.equal(parseVerification(credential('VALID'),'credential',trusted,'different').reason,'contract')
  assert.equal(parseVerification({ ...credential('VALID'),verified:false },'credential',trusted,reference).reason,'contract')
  assert.equal(parseVerification(credential('NEW_UNKNOWN_STATUS'),'credential',trusted,reference).reason,'contract')
  for (const input of [null,[],{}, { status: 'VALID' }, { ...document('VALID',1,2) }, { ...document('OUTDATED',2,2) }, { ...document('INVALID'),is_latest:true }]) assert.equal(parseVerification(input,'document',trusted).kind,'failure')
  assert.equal(isPublicApiBaseSafe('/api/',false),true)
  assert.equal(isPublicApiBaseSafe('https://example.invalid/api/',false),true)
  assert.equal(isPublicApiBaseSafe('http://localhost:8000/api/',true),true)
  for (const url of ['http://example.invalid/api/','//example.invalid/api/','https://user:pass@example.invalid/api/']) assert.equal(isPublicApiBaseSafe(url,false),false)
  const now = Date.UTC(2026,9,25,10)
  assert.equal(retryDeadline('120',now),now + 120000)
  assert.equal(retryDeadline(new Date(now+120000).toUTCString(),now),now + 120000)
  assert.equal(retryDeadline('bad',now),now + 60000)
  const error = (status,headers={}) => new AxiosError('Do not render raw error messages', 'ERR_BAD_RESPONSE', undefined, undefined, { status, headers, data: { private: 'not public' }, config: {}, statusText: 'Error' })
  assert.equal(mapVerificationError(error(429, { 'retry-after':'120' }),now).retryAt, now+120000)
  for (const status of [404,500,502]) assert.equal(mapVerificationError(error(status)).reason,'server')
  for (const status of [400,413,415,422]) assert.equal(mapVerificationError(error(status)).reason,'rejected')
  for (const status of [401,403]) assert.equal(mapVerificationError(error(status)).reason,'auth')
  assert.equal(mapVerificationError(new AxiosError('timeout','ETIMEDOUT')).reason,'timeout')
  assert.equal(mapVerificationError(new AxiosError('network','ERR_NETWORK')).reason,'network')
  // Disabled integration must not send a request, including for a locally valid PDF.
  const previous = verificationConfig.enabled; verificationConfig.enabled = false
  assert.equal((await lookupReference(`passport:${uuid}`,'passport',new AbortController().signal)).reason,'passport_endpoint_missing')
  assert.equal((await lookupReference(reference,'credential',new AbortController().signal)).reason,'disconnected')
  assert.equal((await uploadPdf(new File(['not inspected client-side'],'passport.pdf',{ type:'application/pdf' }),new AbortController().signal,()=>{})).reason,'disconnected')
  verificationConfig.enabled = previous
  const React = await import('react'), { renderToString } = await import('react-dom/server'), { MemoryRouter } = await import('react-router-dom')
  const { VerificationResultView } = await server.ssrLoadModule('/src/verification/pages.tsx')
  const render = outcome => renderToString(React.createElement(MemoryRouter,{},React.createElement(VerificationResultView,{outcome})))
  assert.match(render(null), /No verification has been performed/)
  assert.match(render(mapVerificationError(error(500))), /Verification service unavailable/)
  assert.match(render(parseVerification(credential('REVOKED'),'credential',trusted,reference)), /Revoked credential/)
  assert.match(render(parseVerification(credential('EXPIRED'),'credential',trusted,reference)), /Expired credential/)
  assert.doesNotMatch(render(parseVerification(document('VALID',1,1),'document',trusted)), /PRIVATE NAME|Private arbitrary text/)
  console.log('Verification checks passed: input/file validation, authoritative status contracts, simulated-source rejection, public-field allowlist, technical failures, rate limits, disabled requests and result rendering.')
} finally { await server.close() }
