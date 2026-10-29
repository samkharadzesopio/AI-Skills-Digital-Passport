import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
export default defineConfig(({ command, isPreview, mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }
  const hostedDemo = env.BTU_HOSTED_DEMO === 'true'
  if (hostedDemo && (env.VITE_ENABLE_DEMO !== 'true' || env.VERCEL !== '1' ||
      !env.BTU_DEMO_PROJECT_ID || env.VERCEL_PROJECT_ID !== env.BTU_DEMO_PROJECT_ID ||
      env.VERCEL_GIT_COMMIT_REF !== 'demo/hosted-passport' ||
      !/^[a-z0-9-]+\.vercel\.app$/.test(env.BTU_DEMO_HOSTNAME || '') ||
      env.VITE_API_BASE_URL || env.VITE_GOOGLE_CLIENT_ID)) {
    throw new Error('Hosted demo requires its dedicated Vercel project, demo/hosted-passport branch, vercel.app hostname, and no backend or Google configuration.')
  }
  return ({
  plugins: [react(), tailwindcss(), {
    name: 'btu-preview-status',
    transformIndexHtml() {
      return hostedDemo ? [{ tag: 'meta', injectTo: 'head-prepend', attrs: {
        'http-equiv': 'Content-Security-Policy',
        content: "connect-src 'none'; form-action 'none'; frame-src 'none'; object-src 'none'; base-uri 'self'",
      } }] : []
    },
    configureServer(server) {
      const enabled = server.config.env.DEV && server.config.env.VITE_ENABLE_DEMO === 'true'
      server.config.logger.info(`[BTU] Demo Preview ${enabled ? 'ON — /student/dashboard, /admin/dashboard, /verify' : 'OFF — set VITE_ENABLE_DEMO=true in frontend/.env.local and restart Vite'}`)
    },
  }],
  define: {
    __BTU_LOCAL_DEVELOPMENT__: JSON.stringify(command === 'serve' && !isPreview),
    __BTU_HOSTED_DEMO__: JSON.stringify(hostedDemo),
    __BTU_DEMO_HOSTNAME__: JSON.stringify(hostedDemo ? env.BTU_DEMO_HOSTNAME : ''),
  },
  server: {
    // Keep browser cookies and CSRF checks same-origin; preserve Host/Origin for Django.
    proxy: { '/api': { target: process.env.BTU_DEV_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: false } },
    watch: {
      // Check scripts are not app inputs. OneDrive can lock them while syncing.
      ignored: [/[\\/]scripts(?:[\\/]|$)/],
      // Avoid native Windows watch handles on OneDrive-managed files.
      usePolling: process.platform === 'win32',
      interval: 300,
    },
  },
})
})
