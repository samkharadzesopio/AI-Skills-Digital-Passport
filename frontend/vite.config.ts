import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
export default defineConfig(({ command, isPreview }) => ({
  plugins: [react(), tailwindcss(), {
    name: 'btu-preview-status',
    configureServer(server) {
      const enabled = server.config.env.DEV && server.config.env.VITE_ENABLE_DEMO === 'true'
      server.config.logger.info(`[BTU] Demo Preview ${enabled ? 'ON — /student/dashboard, /admin/dashboard, /verify' : 'OFF — set VITE_ENABLE_DEMO=true in frontend/.env.local and restart Vite'}`)
    },
  }],
  define: { __BTU_LOCAL_DEVELOPMENT__: JSON.stringify(command === 'serve' && !isPreview) },
  server: {
    watch: {
      // Check scripts are not app inputs. OneDrive can lock them while syncing.
      ignored: [/[\\/]scripts(?:[\\/]|$)/],
      // Avoid native Windows watch handles on OneDrive-managed files.
      usePolling: process.platform === 'win32',
      interval: 300,
    },
  },
}))
