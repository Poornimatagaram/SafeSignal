// A tiny offline shell for the installed app: it keeps a copy of this page's own files (the HTML, the built
// scripts and styles, the icons) so the screen still opens when the computer is offline.
//
// It NEVER touches anything else. Requests to the patient runtime (another origin), any non-GET request,
// and any same-origin path outside the allowlist below go straight to the network, untouched and uncached: answers,
// recordings, summaries and receipts are never stored by this worker.
const CACHE = 'patient-shell-v1'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon.svg', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

/** Only this page's own static files: never the runtime, never an API path. */
function isShellRequest(request) {
  if (request.method !== 'GET') return false
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return false
  if (request.mode === 'navigate') return true
  return SHELL.includes(url.pathname) || url.pathname.startsWith('/assets/')
}

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (!isShellRequest(request)) return // the browser handles it as if there were no worker

  if (request.mode === 'navigate') {
    // The newest page when online; the saved one when offline.
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone()
            void caches.open(CACHE).then((cache) => cache.put('/index.html', copy))
          }
          return response
        })
        .catch(() => caches.match('/index.html').then((hit) => hit || Response.error())),
    )
    return
  }

  // Built files have a content hash in their name, so a saved copy is always the right one.
  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone()
            void caches.open(CACHE).then((cache) => cache.put(request, copy))
          }
          return response
        }),
    ),
  )
})
