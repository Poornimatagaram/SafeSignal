import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'

// Port 5175 is fixed (D-026) so the service's SENTINEL_ALLOWED_ORIGINS can list it.
// fs.allow lets the dev server read schema/ (terms, survey example) and packages/ (contract types).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    strictPort: true,
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../../schema', '../../packages'] },
  },
  preview: { port: 5175, strictPort: true },
})
