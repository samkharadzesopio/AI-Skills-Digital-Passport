
declare const __BTU_LOCAL_DEVELOPMENT__: boolean

export const demoMode =
  __BTU_LOCAL_DEVELOPMENT__ &&
  import.meta.env.VITE_ENABLE_DEMO === 'true'
