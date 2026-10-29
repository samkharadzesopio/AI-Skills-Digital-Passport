type GIS = { initialize(options: { client_id: string; nonce: string; hd: string; ux_mode: 'popup'; auto_select: false; use_fedcm_for_button?: boolean; callback(response: { credential?: string }): void }): void
  renderButton(element: HTMLElement, options: { type: string; text: string; theme: string; size: string }): void
  disableAutoSelect(): void }

declare global { interface Window { google?: { accounts: { id: GIS } } } }
let loading: Promise<GIS> | undefined
export function loadGoogle(): Promise<GIS> {
  if (window.google?.accounts.id) return Promise.resolve(window.google.accounts.id)
  if (loading) return loading
  loading = new Promise<GIS>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'; script.async = true; script.defer = true
    const timer = setTimeout(() => { script.remove(); loading = undefined; reject(new Error('Google unavailable')) }, 15000)
    script.onload = () => { clearTimeout(timer); const gis = window.google?.accounts.id; if (gis) resolve(gis); else { loading = undefined; reject(new Error('Google unavailable')) } }
    script.onerror = () => { clearTimeout(timer); script.remove(); loading = undefined; reject(new Error('Google unavailable')) }
    document.head.append(script)
  })
  return loading
}
