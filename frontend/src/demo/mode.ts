
declare const __BTU_LOCAL_DEVELOPMENT__: boolean

// Explicit sign-in leaves the preview for this tab. This selects real API clients;
// it grants no identity, session, role, or permission. Django still authenticates.
function realAuthenticationRequested(): boolean {
  if (typeof window === 'undefined') return false
  const login = ['/student/login', '/admin/login'].includes(window.location.pathname)
  const requested = login && new URLSearchParams(window.location.search).get('auth') === 'live'
  try {
    if (requested) window.sessionStorage.setItem('btu-real-authentication', 'true')
    return requested || window.sessionStorage.getItem('btu-real-authentication') === 'true'
  } catch {
    return requested
  }
}

export const demoMode =
  __BTU_LOCAL_DEVELOPMENT__ &&
  import.meta.env.VITE_ENABLE_DEMO === 'true' &&
  !realAuthenticationRequested()
