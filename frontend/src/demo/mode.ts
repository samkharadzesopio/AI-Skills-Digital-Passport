
declare const __BTU_LOCAL_DEVELOPMENT__: boolean
declare const __BTU_HOSTED_DEMO__: boolean
declare const __BTU_DEMO_HOSTNAME__: string

export const demoMode =
  (__BTU_LOCAL_DEVELOPMENT__ || __BTU_HOSTED_DEMO__) &&
  import.meta.env.VITE_ENABLE_DEMO === 'true'

// Promoting or copying this artifact to a live hostname must fail closed.
export const demoHostAllowed = !__BTU_HOSTED_DEMO__ ||
  (typeof window !== 'undefined' && window.location.hostname === __BTU_DEMO_HOSTNAME__)
