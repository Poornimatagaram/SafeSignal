/// <reference types="vitest/config" />
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { resolveRuntimeUrl } from './src/runtimeUrl.ts'

// Built pages carry a Content-Security-Policy that lets the browser connect only to this page's own origin
// and the patient runtime: no CDN, analytics or other host can be reached even by mistake.
// (Dev mode skips it because Vite's hot reload injects an inline script.)
function contentSecurityPolicy(runtimeOrigin: string): Plugin {
  const policy = [
    "default-src 'none'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    'media-src blob:',
    `connect-src 'self' ${runtimeOrigin}`,
    // The install manifest and the offline-shell worker (public/sw.js) come from this page's own origin only.
    "manifest-src 'self'",
    "worker-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
    "object-src 'none'",
  ].join('; ')
  return {
    name: 'patient-web-csp',
    apply: 'build',
    transformIndexHtml: () => [
      { tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: policy }, injectTo: 'head-prepend' },
    ],
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_PATIENT_')
  const runtimeOrigin = resolveRuntimeUrl(env.VITE_PATIENT_RUNTIME_URL)
  return {
    plugins: [react(), contentSecurityPolicy(runtimeOrigin)],
    // Port 5173 is fixed: the runtime's CORS allows only http://127.0.0.1:5173 and http://localhost:5173.
    server: { host: '127.0.0.1', port: 5173, strictPort: true },
    preview: { host: '127.0.0.1', port: 5173, strictPort: true },
    test: { include: ['tests/**/*.test.{ts,tsx}'], environment: 'node' },
  }
})
