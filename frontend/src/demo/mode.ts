// Compile-time production guard: Vite production builds always evaluate this false.
// This is a presentation mode, never an authenticated identity or a backend grant.
declare const __BTU_LOCAL_DEVELOPMENT__: boolean
export const demoMode = __BTU_LOCAL_DEVELOPMENT__ && import.meta.env.DEV && !import.meta.env.PROD && import.meta.env.VITE_ENABLE_DEMO === 'true'
