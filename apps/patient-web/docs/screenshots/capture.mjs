// Takes the patient-screen screenshots in this folder, with synthetic data only (Walter, pt_4b82d0c6).
//
// It starts its own patient runtime (port 8011, scratch database), builds the screen into a scratch folder and serves
// it on port 4179, then drives headless Chrome over the DevTools protocol and clicks through the real UI.
// Headless Chrome has no usable microphone, so each recorded answer is swapped for a WAV made with macOS `say` from a
// synthetic line (chosen by the request's question_id). Nothing is written outside the scratch folder and this one;
// the WAVs and the scratch database are deleted at the end. Answers are never printed.
//
// Needs: the Sentinel service on 127.0.0.1:8000 (seeded), Ollama with llama3.2:3b, uv, Node 22, Google Chrome, macOS.
// Run from the repository root:  node apps/patient-web/docs/screenshots/capture.mjs
// Settings (env): CHROME, SCRATCH (default: a new temp folder), RUNTIME_PORT (8011), WEB_PORT (4179), CDP_PORT (9339).
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(OUT, '../../../..')
const RUNTIME_PORT = Number(process.env.RUNTIME_PORT ?? 8011)
const WEB_PORT = Number(process.env.WEB_PORT ?? 4179)
const CDP_PORT = Number(process.env.CDP_PORT ?? 9339)
const CHROME = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const OWN_SCRATCH = !process.env.SCRATCH
const SCRATCH = process.env.SCRATCH ?? mkdtempSync(join(tmpdir(), 'patient-shots-'))
const RUN = join(SCRATCH, `run-${Date.now()}`)
mkdirSync(RUN, { recursive: true })

// Synthetic answers by question. q3 is answered vaguely first so the runtime asks again more simply.
const ANSWERS = {
  q1: ['Not so good, I have been tired.'],
  q2: ['I have an itchy rash on my arms.'],
  q3: ['Um.', 'It is moderate.'],
  q4: ['It started two days ago.'],
  q5: ['Yes, I took my tablets.'],
  q6: ['Yes, a new hand cream about five days ago.'],
}
const FALLBACK = 'Nothing else, thank you.'

const procs = []
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (...a) => console.log('[capture]', ...a)

function start(name, cmd, args, opts) {
  const p = spawn(cmd, args, { stdio: ['ignore', 'ignore', 'pipe'], ...opts })
  let err = ''
  p.stderr.on('data', (d) => (err = (err + d).slice(-4000)))
  p.on('exit', (code) => code && log(`${name} exited ${code}`))
  procs.push({ name, p, err: () => err })
  return p
}

async function waitFor(fn, what, timeout = 60000, every = 250) {
  const until = Date.now() + timeout
  for (;;) {
    try {
      const v = await fn()
      if (v) return v
    } catch {}
    if (Date.now() > until) throw new Error(`timed out waiting for ${what}`)
    await sleep(every)
  }
}

function cleanup() {
  for (const { p } of procs.reverse()) if (p.exitCode === null) p.kill('SIGTERM')
  rmSync(OWN_SCRATCH ? SCRATCH : RUN, { recursive: true, force: true }) // scratch database, build, WAVs, Chrome profile
}
process.on('SIGINT', () => (cleanup(), process.exit(130)))

// ---------- DevTools protocol ----------
let ws
let nextId = 0
const pending = new Map()
const listeners = []
function cdp(method, params = {}) {
  const id = ++nextId
  ws.send(JSON.stringify({ id, method, params }))
  return new Promise((ok, fail) => pending.set(id, { ok, fail, method }))
}
async function connect() {
  const targets = await waitFor(async () => {
    const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()
    return list.find((t) => t.type === 'page')
  }, 'Chrome')
  ws = new WebSocket(targets.webSocketDebuggerUrl)
  await new Promise((ok, fail) => ((ws.onopen = ok), (ws.onerror = fail)))
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data)
    if (m.id && pending.has(m.id)) {
      const { ok, fail, method } = pending.get(m.id)
      pending.delete(m.id)
      m.error ? fail(new Error(`${method}: ${m.error.message}`)) : ok(m.result)
    } else if (m.method) listeners.forEach((l) => l(m))
  }
}
async function js(expression) {
  const r = await cdp('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text)
  return r.result.value
}
const has = (text) => js(`document.body.innerText.includes(${JSON.stringify(text)})`)
const buttonReady = (text) =>
  js(`[...document.querySelectorAll('button')].some(b => b.innerText.trim().startsWith(${JSON.stringify(text)})
        && b.getAttribute('aria-disabled') !== 'true' && !b.disabled)`)
async function click(text, timeout = 60000) {
  await waitFor(() => buttonReady(text), `button "${text}"`, timeout)
  await js(`[...document.querySelectorAll('button')].find(b => b.innerText.trim().startsWith(${JSON.stringify(text)})
        && b.getAttribute('aria-disabled') !== 'true' && !b.disabled).click()`)
  await sleep(150)
}

const PHONE = { width: 390, height: 844, deviceScaleFactor: 2, mobile: true }
const setMetrics = (m) => cdp('Emulation.setDeviceMetricsOverride', m)

// full: grow the viewport to the whole page (the pinned buttons then sit at its end). crop: keep only the top
// `crop` CSS pixels. scale: device pixels per CSS pixel (1 for very tall pages, to keep the file small).
async function shot(name, { full = true, top = false, crop = 0, scale = PHONE.deviceScaleFactor, wide = null } = {}) {
  await sleep(400) // let the last render and any scroll settle
  if (top) await js('window.scrollTo(0, 0)')
  const metrics = { ...PHONE, deviceScaleFactor: scale }
  let height = PHONE.height
  if (full) {
    for (let i = 0; i < 2; i++) {
      height = Math.max(PHONE.height, await js('Math.ceil(document.documentElement.scrollHeight)'))
      await setMetrics({ ...metrics, height })
      await sleep(400)
    }
  }
  if (wide) {
    const { data } = await cdp('Page.captureScreenshot', { format: 'png' })
    writeFileSync(join(OUT, name), Buffer.from(data, 'base64'))
    return log(`saved ${name} (${wide.width}x${wide.height})`)
  }
  const clip = { x: 0, y: 0, width: PHONE.width, height: crop ? Math.min(crop, height) : height, scale: 1 }
  const { data } = await cdp('Page.captureScreenshot', { format: 'png', clip, captureBeyondViewport: true })
  writeFileSync(join(OUT, name), Buffer.from(data, 'base64'))
  await setMetrics(PHONE)
  log(`saved ${name} (${clip.height} of ${height} CSS px, x${scale})`)
}

// ---------- answers ----------
const wavCache = new Map()
function wav(text) {
  if (!wavCache.has(text)) {
    const file = join(RUN, `a${wavCache.size}.wav`)
    execFileSync('say', ['-o', file, '--data-format=LEI16@16000', text])
    wavCache.set(text, readFileSync(file).toString('base64'))
  }
  return wavCache.get(text)
}
const asked = {}
function onPaused(m) {
  if (m.method !== 'Fetch.requestPaused') return
  const { requestId, request } = m.params
  if (request.method !== 'POST') return void cdp('Fetch.continueRequest', { requestId })
  const q = new URL(request.url).searchParams.get('question_id') ?? ''
  const n = (asked[q] = (asked[q] ?? -1) + 1)
  const list = ANSWERS[q] ?? [FALLBACK]
  const text = list[Math.min(n, list.length - 1)]
  const headers = Object.entries(request.headers)
    .filter(([k]) => k.toLowerCase() !== 'content-type' && k.toLowerCase() !== 'content-length')
    .map(([name, value]) => ({ name, value }))
  headers.push({ name: 'Content-Type', value: 'audio/wav' })
  log(`answering ${q} (try ${n + 1})`)
  void cdp('Fetch.continueRequest', { requestId, postData: wav(text), headers })
}

async function answer() {
  await click('Tap to answer')
  await waitFor(() => has("Listening… tap when you're done"), 'listening')
  await sleep(600)
  await click('Listening')
  await waitFor(async () => !(await has('Thinking about your answer…')), 'answer handled', 120000, 400)
  await sleep(300)
}

// ---------- run ----------
async function main() {
  log('scratch folder', RUN)
  start('runtime', 'uv', ['run', 'uvicorn', 'sentinel_patient.main:app', '--host', '127.0.0.1', '--port', String(RUNTIME_PORT)], {
    cwd: join(ROOT, 'apps/patient-runtime'),
    env: {
      ...process.env,
      PATIENT_DB_PATH: join(RUN, 'patient.db'),
      PATIENT_ALLOWED_ORIGINS: `http://127.0.0.1:${WEB_PORT}`,
      SENTINEL_BASE_URL: 'http://127.0.0.1:8000',
      SENTINEL_ACTOR_ID: 'pt_4b82d0c6',
    },
  })
  const web = join(ROOT, 'apps/patient-web')
  execFileSync('npx', ['vite', 'build', '--outDir', join(RUN, 'dist'), '--emptyOutDir', '--logLevel', 'warn'], {
    cwd: web,
    env: { ...process.env, VITE_PATIENT_RUNTIME_URL: `http://127.0.0.1:${RUNTIME_PORT}` },
    stdio: 'inherit',
  })
  start('preview', 'npx', ['vite', 'preview', '--outDir', join(RUN, 'dist'), '--host', '127.0.0.1', '--port', String(WEB_PORT), '--strictPort'], { cwd: web })
  await waitFor(async () => (await fetch(`http://127.0.0.1:${RUNTIME_PORT}/health`)).ok, 'runtime', 120000, 500)
  await waitFor(async () => (await fetch(`http://127.0.0.1:${WEB_PORT}/`)).ok, 'preview')

  start('chrome', CHROME, [
    '--headless=new', `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${join(RUN, 'profile')}`,
    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required',
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', 'about:blank',
  ])
  await connect()
  listeners.push(onPaused)
  await cdp('Page.enable')
  await cdp('Runtime.enable')
  await cdp('Fetch.enable', { patterns: [{ urlPattern: '*checkin/turn*', requestStage: 'Request' }] })
  const home = `http://127.0.0.1:${WEB_PORT}/`
  // Headless Chrome's fake microphone hangs in getUserMedia here, so the page gets a quiet synthetic stream instead
  // (the app records it as usual; the recording is then swapped for the synthetic WAV above).
  await cdp('Page.addScriptToEvaluateOnNewDocument', {
    source: `navigator.mediaDevices.getUserMedia = async () => {
      const c = new AudioContext(); const o = c.createOscillator(); const g = c.createGain(); g.gain.value = 0.001
      const d = c.createMediaStreamDestination(); o.connect(g).connect(d); o.start(); return d.stream }`,
  })

  // Wide shot first: the phone frame on a desktop screen.
  const WIDE = { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false }
  await setMetrics(WIDE)
  await cdp('Page.navigate', { url: home })
  await waitFor(() => has("Start today's check-in"), 'home')
  await shot('home-desktop.png', { full: false, wide: WIDE })

  await setMetrics(PHONE)
  await cdp('Page.navigate', { url: home })
  await waitFor(() => has("Start today's check-in"), 'home')
  await shot('home.png', { top: true })

  // Who I share with, and the setup screen's review step (never saved).
  await click('Who I share with')
  await waitFor(() => has('Share with my doctor'), 'consent')
  await shot('consent.png', { top: true })
  await click('Change my choices')
  await waitFor(() => has('Step 1 of'), 'setup')
  for (let i = 0; i < 5 && !(await has('Check and send')); i++) await click('Next')
  await waitFor(() => has('Save and send'), 'setup review')
  await shot('setup.png', { top: true })
  await click('Back', 5000).catch(() => {})
  await cdp('Page.navigate', { url: home }) // leave setup without saving anything
  await waitFor(() => has("Start today's check-in"), 'home')

  // The check-in.
  await click("Start today's check-in")
  for (let q = 1; q <= 12; q++) {
    await waitFor(async () => (await has('Tap to answer')) || (await has("Here's what you're sharing")), 'question', 60000)
    if (await has("Here's what you're sharing")) break
    const qid = `q${q}`
    await answer()
    if (await has('Let me ask that more simply')) {
      await shot('reask.png')
      await answer()
    }
    // The hero shot: the re-asked question, answered (two exchanges in one thread).
    if (qid === 'q3') await shot('checkin-chat.png')
    if (await buttonReady('Next question')) await click('Next question')
    else await click('Finish check-in')
  }

  await waitFor(() => has("Here's what you're sharing"), 'summary', 120000)
  await waitFor(async () => !(await has('Putting your summary together…')), 'summary ready')
  // Choose a severity for any problem that has none, so "Share this" is enabled.
  // Choose "Moderate" for every problem still without a severity, so "Share this" is enabled.
  for (let i = 0; i < 6 && !(await buttonReady('Share this')); i++) {
    const picked = await js(`(() => { const b = [...document.querySelectorAll('button[aria-pressed]')].find(b =>
      b.innerText.trim() === 'Moderate' && b.getAttribute('aria-pressed') !== 'true'
      && ![...b.parentElement.querySelectorAll('button[aria-pressed]')].some(x => x.getAttribute('aria-pressed') === 'true'));
      if (b) b.click(); return !!b })()`)
    if (!picked) break
    await sleep(300)
  }
  await shot('summary.png', { top: true, crop: 1590 }) // the problems, with the "for review" line
  await shot('summary-full.png', { top: true, scale: 1 })
  await click('Share this')
  await waitFor(() => has("Thank you, that's all for today."), 'receipt', 60000)
  await sleep(1500)
  await shot('receipt.png', { top: true, crop: 1420 }) // "Shared" and what was shared, in plain words
  await shot('receipt-full.png', { top: true, scale: 1 })

  await click('Back to the start')
  await click('What this computer sent')
  await waitFor(async () => (await has('Only these went out')) && !(await has('Getting the list…')), 'network log')
  await click('Show details', 3000).catch(() => {})
  await shot('network-log.png', { top: true, crop: 1535 }) // the newest entries, the first one opened
  await shot('network-log-full.png', { top: true, scale: 1 })
}

try {
  await main()
} catch (e) {
  console.error('[capture] failed:', e.message)
  // Only the screen's own status and error lines (never the conversation), to say why it stopped.
  try { console.error('[capture] screen says:', await js(`[...document.querySelectorAll('.alert, .status, .progress')].map(e => e.innerText.trim()).filter(Boolean).join(' | ')`)) } catch {}
  for (const { name, err } of procs) if (err()) console.error(`--- ${name} (last stderr) ---\n${err().split('\n').slice(-8).join('\n')}`)
  process.exitCode = 1
} finally {
  try { ws?.close() } catch {}
  cleanup()
}
