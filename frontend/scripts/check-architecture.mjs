import assert from 'node:assert/strict'
import { createServer } from 'vite'
const server = await createServer({ define: { 'import.meta.env.VITE_ENABLE_DEMO': 'false' }, server: { middlewareMode: true }, appType: 'custom' })
const storageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
// Browser preference storage stub for server-rendered UI checks, not authentication.
Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: { getItem: () => null } })
try {
  const React = await import('react')
  const { renderToString } = await import('react-dom/server')
  const { MemoryRouter } = await import('react-router-dom')
  const { QueryClient, QueryClientProvider } = await import('@tanstack/react-query')
  const { AppRoutes } = await server.ssrLoadModule('/src/App.tsx')
  const { PassportPreview } = await server.ssrLoadModule('/src/components/PassportPreview.tsx')
  const { demoPassport } = await server.ssrLoadModule('/src/data/passport.ts')
  const { demoStudent } = await server.ssrLoadModule('/src/data/mock.ts')

  function render(path, session, student) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    if (session) client.setQueryData(['session'], session)
    if (student) client.setQueryData(['demo-student'], student)

    const markup = renderToString(React.createElement(QueryClientProvider, { client }, React.createElement(MemoryRouter, { initialEntries: [path] }, React.createElement(AppRoutes))))
    return { markup, client }
  }
  const studentSession={status:'authenticated',user:{email:'unit@btu.edu.ge',role:'STUDENT',email_verified:true,student_association:'linked'}}
  const adminSession={status:'authenticated',user:{email:'unit-admin@btu.edu.ge',role:'ADMIN',email_verified:true,student_association:'unlinked'}}
  for(const path of ['/student/dashboard','/student/passport','/student/game','/admin/dashboard']){
    const page=render(path)
    assert.doesNotMatch(page.markup,/Nino|Example AI skill|Recent credentials/)
    assert.equal(page.client.getQueryData(['demo-student']),undefined)
    assert.equal(page.client.getQueryData(['admin','demo']),undefined)
    page.client.clear()
  }
  for(const path of ['/student/dashboard','/student/skills','/student/credentials','/student/passport','/student/profile']){
    const page=render(path,studentSession)
    assert.match(page.markup,/Loading your passport/)
    assert.doesNotMatch(page.markup,/Nino|DEMO-PASSPORT|Recent credentials/)
    assert.equal(page.client.getQueryData(['demo-student']),undefined)
    page.client.clear()
  }
  const denied=render('/admin/dashboard',studentSession)
  assert.match(denied.markup,/different workspace/);denied.client.clear()
  const missing=render('/admin/dashboard',adminSession)
  assert.match(missing.markup,/Administrator permissions are not available/)
  assert.equal(missing.client.getQueryData(['admin','demo']),undefined);missing.client.clear()
  const publicPage = render('/verify')
  assert.match(publicPage.markup, /No login required/)
  assert.doesNotMatch(publicPage.markup, /Nino|Student workspace|Authentication integration pending/)
  assert.equal(publicPage.client.getQueryData(['session']), undefined)
  assert.equal(publicPage.client.getQueryData(['demo-student']), undefined)
  assert.equal(publicPage.client.getQueryData(['admin', 'demo']), undefined)
  publicPage.client.clear()
  for (const [path,expected] of [['/verify/reference','Verification reference'],['/verify/upload','Drop a PDF here'],['/verify/result?status=VALID','No verification has been performed'],['/verify/qr','This QR link does not contain'],['/verify/qr/passport-version:00000000-0000-0000-0000-000000000001','Verify a scanned reference']]) {
    const page = render(path)
    assert.ok(page.markup.includes(expected), path)
    assert.doesNotMatch(page.markup, /Student workspace|Authentication integration pending/)
    assert.equal(page.client.getQueryData(['session']),undefined)
    assert.equal(page.client.getQueryData(['admin','demo']),undefined)
    assert.equal(page.client.getQueryData(['demo-student']),undefined)
    page.client.clear()
  }

  const preview = renderToString(React.createElement(PassportPreview, { passport: demoPassport }))
  for (const text of ['Example competency category', 'Example subcategory', 'Example nested subcategory', 'Example AI skill', 'Example proficiency level', 'Example supporting credential', 'Example assessment evidence', 'DEMO-VERSION-001', 'unverified (demo)']) assert.ok(preview.includes(text), text)
  const misleadingDemo = structuredClone(demoPassport)
  misleadingDemo.verification.status = 'verified'
  assert.match(renderToString(React.createElement(PassportPreview, { passport: misleadingDemo })), /unverified \(demo\)/)
  // The original dashboard fixture remains independent of the proposed passport contract.
  assert.equal(demoStudent.credentials.length, 3)
  console.log('Architecture checks passed: access boundaries, role isolation, public independence, recursive passport data, demo verification labeling.')
} finally {
  if (storageDescriptor) Object.defineProperty(globalThis, 'localStorage', storageDescriptor)
  else delete globalThis.localStorage
  await server.close()
}
