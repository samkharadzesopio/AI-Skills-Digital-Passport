// Synthetic contract transport tests. Real Chrome/Django/Anvil acceptance is separate.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { AxiosError, AxiosHeaders } from 'axios'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom' })
try {
  const dto = await server.ssrLoadModule('/src/admin/live/spreadsheet-contracts.ts'), service = await server.ssrLoadModule('/src/admin/live/spreadsheet-service.ts'), history = await server.ssrLoadModule('/src/admin/live/contracts.ts'), { api } = await server.ssrLoadModule('/src/services/api.ts')
  const id = '11111111-1111-4111-8111-111111111111', hash = 'a'.repeat(64), profile = { id, key: 'synthetic-reviewed', version: 1, source: 'BTU_GOOGLE_SHEETS', kind: 'SKILL_AWARD' }
  const preview = { id, snapshot_sha256: hash, state: 'READY', expires_at: new Date(Date.now()+3600000).toISOString(), result: null, report: { profile_id: id, profile_key: profile.key, profile_version: 1, source: profile.source, kind: profile.kind, header_row: 4, columns: { external_student_id: 5 }, total_rows: 1, valid_records: 1, duplicate_records: 0, invalid_records: 0, review_records: 0, rows: [{ row: 5, status: 'VALID', code: 'ELIGIBLE', message: 'Synthetic allowed validator text.' }] } }
  assert.equal(dto.parsePreview(preview).report.header_row,4)
  for (const mutate of [v=>v.snapshot_sha256='bad',v=>v.expires_at='invalid',v=>v.report.valid_records=2,v=>v.report.columns.password=1,v=>v.report.columns.external_student_id=27,v=>v.report.rows[0].status='CONFIRMED',v=>v.state='COMPLETED',v=>v.report.rows[0].row=0]) { const value=structuredClone(preview); mutate(value); assert.throws(()=>dto.parsePreview(value)) }
  const privateData={...preview,private:'must not project',report:{...preview.report,private:'must not project'}}; assert.ok(!JSON.stringify(dto.parsePreview(privateData)).includes('must not project'))
  assert.deepEqual(history.summary({ errors: [{row:5,type:'LegacyError'},{row:6,code:'PROCESSING_FAILED'}] }).errors,[{row:5,code:'LegacyError'},{row:6,code:'PROCESSING_FAILED'}])
  let code='', status=200; const calls=[]
  api.defaults.adapter=async config=>{const body=typeof config.data==='string'?JSON.parse(config.data):config.data;calls.push({path:config.url,method:config.method,body});const response={status:config.url==='accounts/csrf/'?200:status,data:config.url==='accounts/csrf/'?{csrfToken:'A'.repeat(64)}:status>=400?{code,detail:'private provider secret'}:config.url.startsWith('integrations/import/profiles/')?{count:1,next:null,previous:null,results:[profile]}:preview,headers:new AxiosHeaders(),config};if(response.status>=400)throw new AxiosError('private transport secret','ERR_BAD_RESPONSE',config,undefined,response);return response}
  const profiles=await service.getProfiles(1); assert.equal(profiles.results[0].id,id); assert.throws(()=>service.getProfiles(0)); await service.previewImport(profile,null); assert.deepEqual(calls.at(-1).body,{profile_id:id})
  await service.confirmPreview(preview); assert.deepEqual(calls.at(-1).body,{confirm:true,snapshot_sha256:hash}); assert.match(calls.at(-1).path,new RegExp(`${id}/confirm/$`))
  for(const value of [{...preview,state:'COMPLETED'},{...preview,expires_at:'2000-01-01'},{...preview,snapshot_sha256:'bad'},{...preview,report:{...preview.report,valid_records:0}}])assert.throws(()=>service.confirmPreview(value))
  status=409;code='PREVIEW_DIGEST_MISMATCH';const before=calls.length;await assert.rejects(service.confirmPreview(preview),e=>e.status===409&&e.message.includes('new preview')&&!/secret/.test(e.message));assert.equal(calls.length,before+1,'Confirmation is not automatically retried')
  status=503;code='GOOGLE_SOURCE_UNAVAILABLE';await assert.rejects(service.previewImport(profile,null),e=>e.message.includes('read-only provider credentials')&&!/secret/.test(e.message))
  status=500;code='private provider secret';await assert.rejects(service.refreshPreview(id),e=>!(/secret/.test(e.message))&&e.status===500)
  assert.ok(calls.every(c=>!c.path.startsWith('http')))
  console.log('PASS spreadsheet contracts/services: immutable exact digest, explicit replay only, malformed/count/mapping rejection, private projection, old/new history errors, safe Google/conflict/backend failures. Synthetic transport fixtures; no live Google claim.')
}finally{await server.close()}
