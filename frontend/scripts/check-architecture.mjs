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
  const { adminFixture } = await server.ssrLoadModule('/src/admin/mock.ts')
  function render(path, session, student) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    if (session) client.setQueryData(['session'], session)
    if (student) client.setQueryData(['demo-student'], student)
    if (session?.status === 'authenticated' && session.roles.includes('administrator')) client.setQueryData(['admin', 'demo'], structuredClone(adminFixture))
    const markup = renderToString(React.createElement(QueryClientProvider, { client }, React.createElement(MemoryRouter, { initialEntries: [path] }, React.createElement(AppRoutes))))
    return { markup, client }
  }
  for (const path of ['/student/dashboard', '/student/passport', '/student/game', '/admin/dashboard']) {
    const { markup, client } = render(path, { status: 'unavailable' })
    assert.match(markup, /Authentication integration pending/)
    assert.doesNotMatch(markup, /Nino|Example AI skill|Recent credentials/)
    assert.equal(client.getQueryData(['demo-student']), undefined)
    assert.equal(client.getQueryData(['admin', 'demo']), undefined)
    client.clear()
  }
  const studentDenied = render('/student/dashboard', { status: 'anonymous' })
  assert.match(studentDenied.markup, /Access required/)
  studentDenied.client.clear()
  const adminDenied = render('/admin/dashboard', { status: 'authenticated', userId: 'test-only', roles: ['student'] })
  assert.match(adminDenied.markup, /Explicit administrator permission/)
  adminDenied.client.clear()
  const adminAllowed = render('/admin/dashboard', { status: 'authenticated', userId: 'test-only', roles: ['administrator'] })
  assert.match(adminAllowed.markup, /Course-to-skill mapping/)
  assert.doesNotMatch(adminAllowed.markup, /Nino|Student workspace/)
  adminAllowed.client.clear()
  for (const [path, expected] of [['/admin/students','Demo student 01'], ['/admin/students/DEMO-ST-001','student1@example.invalid'], ['/admin/skills','Data communication'], ['/admin/course-mappings','AI for business'], ['/admin/credentials','Request issuance'], ['/admin/credentials/DEMO-CR-1','Request revocation'], ['/admin/classroom-sync','Request retry'], ['/admin/imports','Validate local workbook'], ['/admin/audit-logs','Affected record']]) {
    const page = render(path, { status: 'authenticated', userId: 'test-only', roles: ['administrator'] })
    assert.ok(page.markup.includes(expected), path)
    assert.doesNotMatch(page.markup, /Student workspace/)
    page.client.clear()
  }
  // Synthetic sessions below exercise route behavior only; no application login state is created.
  for (const [path, expected] of [['/student/dashboard', 'Recent credentials'], ['/student/skills', 'Generative AI'], ['/student/credentials', 'Sample credentials only'], ['/student/passport', 'Inspect passport data and hierarchy'], ['/student/profile', 'Display name'], ['/student/gap-analyzer', 'Your career goal'], ['/student/game', 'AI playground coming soon']]) {
    const page = render(path, { status: 'authenticated', userId: 'test-only', roles: ['student'] }, demoStudent)
    assert.ok(page.markup.includes(expected), path)
    page.client.clear()
  }
  const publicPage = render('/verify')
  assert.match(publicPage.markup, /Verification service not connected/)
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
