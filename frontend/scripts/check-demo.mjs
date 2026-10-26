import assert from 'node:assert/strict'
import { build, createServer } from 'vite'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': '"true"' }, server: { middlewareMode: true }, appType: 'custom' })
const storageDescriptor = Object.getOwnPropertyDescriptor(globalThis,'localStorage')
Object.defineProperty(globalThis,'localStorage',{ configurable:true,value:{getItem:()=>null} })
try {
  const React = await import('react'), { renderToString } = await import('react-dom/server'), { MemoryRouter } = await import('react-router-dom'), { QueryClient, QueryClientProvider } = await import('@tanstack/react-query')
  const { demoMode } = await server.ssrLoadModule('/src/demo/mode.ts')
  assert.equal(demoMode,true)
  const { AppRoutes } = await server.ssrLoadModule('/src/App.tsx')
  const { DemoBanner } = await server.ssrLoadModule('/src/demo/DemoBanner.tsx')
  const { demoStudent } = await server.ssrLoadModule('/src/data/mock.ts'), { adminFixture } = await server.ssrLoadModule('/src/admin/mock.ts')
  for (const path of ['/student/dashboard','/student/skills','/student/credentials','/student/passport','/student/profile','/student/gap-analyzer','/student/game','/admin/dashboard','/admin/passports/preview','/admin/students/DEMO-ST-001/passport','/admin/students','/admin/students/DEMO-ST-001','/admin/skills','/admin/course-mappings','/admin/credentials','/admin/credentials/DEMO-CR-1','/admin/classroom-sync','/admin/imports','/admin/audit-logs','/student/login','/admin/login','/verify','/verify/reference','/verify/upload']) {
    const client = new QueryClient()
    client.setQueryData(['demo-student'],demoStudent); client.setQueryData(['admin','demo'],structuredClone(adminFixture))
    const html = renderToString(React.createElement(QueryClientProvider,{client},React.createElement(MemoryRouter,{initialEntries:[path]},React.createElement(React.Fragment,{},React.createElement(DemoBanner),React.createElement(AppRoutes)))))
    assert.match(html,/Demo Mode/,path)
    assert.doesNotMatch(html,/Authentication integration pending/,path)
    assert.equal(client.getQueryState(['session']),undefined,'Demo must never query authentication')
    client.clear()
  }
  // Redirect effects are verified by check:preview.
  const { api } = await server.ssrLoadModule('/src/services/api.ts')
  await assert.rejects(api.get('/private-data'),/DEMO_MODE_PRIVATE_API_DISABLED/)
  const auth=await server.ssrLoadModule('/src/auth/service.ts')
  for(const operation of [()=>auth.requestStudentOtp('unit@btu.edu.ge'),()=>auth.verifyStudentOtp('unit@btu.edu.ge','123456'),()=>auth.loginAdministrator('unit@btu.edu.ge','unit password'),()=>auth.logoutAccount()])await assert.rejects(operation(),error=>error.code==='demoDisabled')
  const { requestAdminAction } = await server.ssrLoadModule('/src/admin/services.ts')
  for (const type of ['issue','revoke','commit-import','retry-sync','preview-sheet']) await assert.rejects(requestAdminAction({type}),/DEMO_MODE_OFFICIAL_ACTION_DISABLED/)
  const { verificationConfig,lookupReference,uploadPdf,parseVerification }=await server.ssrLoadModule('/src/verification/service.ts')
  verificationConfig.enabled=true;verificationConfig.trustedSources=['unit-registry']
  assert.equal((await lookupReference('unit-reference','credential',new AbortController().signal)).kind,'failure')
  assert.equal((await uploadPdf(new File(['unit'],'sample.pdf',{type:'application/pdf'}),new AbortController().signal,()=>{})).kind,'failure')
  assert.equal(parseVerification({status:'VALID',verified:true,source:'unit-registry',credential_id:'unit-reference'},'credential',['unit-registry'],'unit-reference').kind,'failure')
  await server.close()
  const oldNodeEnv=process.env.NODE_ENV
  try {
    process.env.NODE_ENV='development'
    const output=await build({logLevel:'silent',define:{'import.meta.env.VITE_ENABLE_DEMO':'"true"'},build:{ssr:'src/demo/mode.ts',write:false,minify:false,emptyOutDir:false}})
    const chunk=output.output.find(item=>item.type==='chunk'&&item.isEntry)
    const production=await import('data:text/javascript;base64,'+Buffer.from(chunk.code).toString('base64'))
    assert.equal(production.demoMode,false)
  } finally { if(oldNodeEnv===undefined)delete process.env.NODE_ENV;else process.env.NODE_ENV=oldNodeEnv }
  console.log('Demo checks passed: workspaces, no session queries, redirects, blocked APIs/actions/verification, and forced-off builds with the flag enabled.')
} finally {
  if(storageDescriptor)Object.defineProperty(globalThis,'localStorage',storageDescriptor);else delete globalThis.localStorage
  await server.close()
}
