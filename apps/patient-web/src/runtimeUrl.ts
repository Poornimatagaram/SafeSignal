// The patient runtime on this computer is the only server this screen ever talks to.
// Every outbound byte leaves through the runtime's egress gate, never from the browser.
export const DEFAULT_RUNTIME_URL = 'http://127.0.0.1:8001'

/** Normalize a configured runtime URL to its origin (no path, no trailing slash). */
export function resolveRuntimeUrl(configured: string | undefined | null): string {
  const raw = (configured ?? '').trim()
  if (!raw) return DEFAULT_RUNTIME_URL
  const url = new URL(raw)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('VITE_PATIENT_RUNTIME_URL must be an http(s) URL')
  }
  return url.origin
}
