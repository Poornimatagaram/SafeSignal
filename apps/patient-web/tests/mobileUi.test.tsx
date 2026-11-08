// The mobile, chat-style screen (owner spec): the greeting and the one big action on Home, the check-in as chat
// bubbles, the 430 px phone frame, the minimum sizes in the stylesheet, and the installable app (manifest, icons and
// an offline shell that never touches the runtime). Synthetic data only.
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { TurnResult } from '../src/api.ts'
import { bubblesAfterTurn, ChatThread, type Bubble } from '../src/CheckinChat.tsx'
import { DEFAULT_DISPLAY_NAME, resolveDisplayName } from '../src/displayName.ts'
import { HomeView, type HomeViewProps } from '../src/HomeScreen.tsx'
import { Shell, SHELL_CLASS } from '../src/Shell.tsx'
import { S } from '../src/strings.ts'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const read = (path: string) => readFileSync(join(ROOT, path), 'utf8')
const noop = () => undefined

/** The visible text of rendered HTML. */
function textOf(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Every button: its opening tag and its visible words. */
function buttons(html: string) {
  return [...html.matchAll(/<button[^>]*>(.*?)<\/button>/g)].map((m) => ({
    tag: m[0].slice(0, m[0].indexOf('>') + 1),
    text: textOf(m[1]),
  }))
}

describe('greeting', () => {
  it('says good morning, afternoon or evening by the local hour', () => {
    expect(S.home.greeting(0, 'Walter')).toBe('Good morning, Walter')
    expect(S.home.greeting(8, 'Walter')).toBe('Good morning, Walter')
    expect(S.home.greeting(11, 'Walter')).toBe('Good morning, Walter')
    expect(S.home.greeting(12, 'Walter')).toBe('Good afternoon, Walter')
    expect(S.home.greeting(17, 'Walter')).toBe('Good afternoon, Walter')
    expect(S.home.greeting(18, 'Walter')).toBe('Good evening, Walter')
    expect(S.home.greeting(23, 'Walter')).toBe('Good evening, Walter')
  })

  it('works without a name', () => {
    expect(S.home.greeting(9, '  ')).toBe('Good morning')
  })

  it('takes the name from VITE_PATIENT_DISPLAY_NAME, "Walter" by default', () => {
    expect(DEFAULT_DISPLAY_NAME).toBe('Walter')
    expect(resolveDisplayName(undefined)).toBe('Walter')
    expect(resolveDisplayName('   ')).toBe('Walter')
    expect(resolveDisplayName('  Ada ')).toBe('Ada')
    expect(resolveDisplayName('x'.repeat(100))).toHaveLength(40)
  })

  it('the name is only ever shown: it never reaches the API client or any other module', () => {
    const config = read('src/config.ts')
    expect(config).toContain('VITE_PATIENT_DISPLAY_NAME')
    for (const file of ['src/api.ts', 'src/shareFlow.ts', 'src/consentFlow.ts', 'src/setupFlow.ts', 'src/networkLog.ts']) {
      expect(read(file)).not.toMatch(/DISPLAY_NAME|displayName/)
    }
  })
})

describe('home screen', () => {
  const props: HomeViewProps = {
    name: 'Walter',
    hour: 9,
    starting: false,
    startError: null,
    onStart: noop,
    onConsent: noop,
    onNetworkLog: noop,
  }

  it('one bold sentence and one giant "Start today\'s check-in" button', () => {
    const html = renderToStaticMarkup(<HomeView {...props} />)
    expect(html).toMatch(/<h1 class="title home__greeting">Good morning, Walter<\/h1>/)
    const start = buttons(html).find((b) => b.text === "Start today's check-in")
    expect(start?.tag).toContain('button--huge')
    expect(start?.tag).toContain('button--primary')
    expect(buttons(html).filter((b) => b.tag.includes('button--primary'))).toHaveLength(1)
  })

  it('the other places are big labelled buttons further down, not a hidden menu', () => {
    const html = renderToStaticMarkup(<HomeView {...props} />)
    const all = buttons(html)
    expect(all.map((b) => b.text)).toEqual(["Start today's check-in", 'Who I share with', 'What this computer sent'])
    for (const b of all) {
      expect(b.tag).toContain('button--huge')
      expect(b.text.length).toBeGreaterThan(3) // never an icon alone
    }
    expect(html).not.toMatch(/aria-haspopup|role="menu"|hamburger/)
  })

  it('shows the start problem and offers "Try again"', () => {
    const html = renderToStaticMarkup(<HomeView {...props} startError={S.errors.runtimeDown} />)
    expect(textOf(html)).toContain(S.errors.runtimeDown)
    expect(buttons(html)[0].text).toBe('Try again')
  })
})

const turn = (transcript: string, patch: Partial<TurnResult> = {}): TurnResult => ({
  transcript,
  symptoms: [],
  extraction: 'ok',
  rating: 'complete',
  next: { action: 'next', unanswered: false },
  command: null,
  ...patch,
})

describe('check-in as a chat', () => {
  const render = (bubbles: Bubble[]) => renderToStaticMarkup(<ChatThread bubbles={bubbles} />)

  it('the question is a bubble from the helper, in the big question text', () => {
    const html = render([{ kind: 'question', text: 'How have you been feeling since yesterday?' }])
    expect(html).toContain('role="log"')
    expect(html).toMatch(/<li class="bubble bubble--app bubble--question bubble--current">/)
    expect(html).toMatch(/<p class="question">.*How have you been feeling since yesterday\?<\/p>/)
  })

  it("Walter's answer is his own bubble, and what was noted follows as the helper's", () => {
    const bubbles = bubblesAfterTurn(
      turn('I have a rash', { symptoms: [{ term_code: 'SE_RASH', label: 'Rash', severity: 'mild' }] }),
      'answered',
    )
    expect(bubbles.map((b) => b.kind)).toEqual(['answer', 'noted'])
    const html = render([{ kind: 'question', text: 'Q?' }, ...bubbles])
    expect(html).toMatch(/<li class="bubble bubble--me"><p class="said">.*I have a rash<\/p><\/li>/)
    expect(textOf(html)).toContain('Noted for review: Rash, mild')
    expect(textOf(html)).not.toMatch(/caus|because of|due to/i)
  })

  it('a re-ask: his words, "Let me ask that more simply." and the simpler question, each a bubble', () => {
    const bubbles = bubblesAfterTurn(turn('the weather was odd', { rating: 'off_topic' }), 'reask', {
      text: 'Have you felt any different in your body?',
    })
    expect(bubbles).toEqual([
      { kind: 'answer', words: 'the weather was odd' },
      { kind: 'reask' },
      { kind: 'question', text: 'Have you felt any different in your body?' },
    ])
    const html = render([{ kind: 'question', text: 'How have you been?' }, ...bubbles])
    expect(html.match(/class="bubble /g)).toHaveLength(4)
    expect(html).toMatch(/bubble--notice"><svg[^]*?<p class="notice">Let me ask that more simply\.<\/p>/)
    // Only the newest wording is marked as the current question.
    expect(html.match(/bubble--current/g)).toHaveLength(1)
    expect(html.indexOf('bubble--current')).toBeGreaterThan(html.indexOf('Let me ask that more simply.'))
  })

  it('"say that again" and "slower" show as small bubbles, never as a re-ask', () => {
    const repeat = bubblesAfterTurn(turn(''), 'command', { text: 'Q?', command: 'repeat' })
    const slower = bubblesAfterTurn(turn('slower please'), 'command', { text: 'Q?', command: 'slower' })
    expect(repeat).toEqual([{ kind: 'command', command: 'repeat' }])
    expect(slower).toEqual([{ kind: 'answer', words: 'slower please' }, { kind: 'command', command: 'slower' }])
    const html = render([...repeat, ...slower])
    expect(html).toMatch(/bubble--small"><p class="note">Saying it again<\/p>/)
    expect(html).toMatch(/bubble--small"><p class="note">Saying it more slowly<\/p>/)
    expect(html).not.toContain(S.checkin.reask)
  })

  it('no words, and a question given up, are kind bubbles too', () => {
    expect(bubblesAfterTurn(turn('  '), 'answered')).toEqual([{ kind: 'no-words' }])
    expect(bubblesAfterTurn(turn(''), 'move-on')).toEqual([{ kind: 'move-on' }])
    const text = textOf(render([{ kind: 'no-words' }, { kind: 'move-on' }]))
    expect(text).toContain(S.checkin.noWords)
    expect(text).toContain("That's okay, let's move on.")
  })

  it('the thread is cleared on every question change, so his words stay no longer than one question', () => {
    const app = read('src/App.tsx')
    const reset = app.slice(app.indexOf('const resetForQuestionChange'), app.indexOf('/** After the last question'))
    expect(reset).toContain('setThread([])')
    expect(reset).toContain('setReply(null)')
  })

  it('the talk button is the one action, at the bottom, with "Hear it again" and "Slower" beside it', () => {
    const app = read('src/App.tsx')
    const dock = app.slice(app.indexOf('<div className="dock">'))
    expect(dock).toContain('className={`button talk talk--${talk}`}')
    expect(dock).toContain('{C.hearAgain}')
    expect(dock).toContain('{C.slowerButton}')
  })
})

describe('phone-sized layout', () => {
  const css = read('src/styles.css').replace(/\/\*[^]*?\*\//g, '')

  it('every screen sits in the 430 px shell', () => {
    expect(SHELL_CLASS).toBe('app-shell')
    expect(renderToStaticMarkup(<Shell>x</Shell>)).toBe(
      '<div class="app-shell"><div class="app-shell__viewport">x</div></div>',
    )
    expect(read('src/App.tsx')).toContain('return <Shell>{renderScreen()}</Shell>')
  })

  it('the shell is at most 430 px wide and centred', () => {
    expect(css).toMatch(/--shell-width:\s*430px/)
    const shell = rule(css, '.app-shell')
    expect(shell).toMatch(/max-width:\s*var\(--shell-width\)/)
    expect(shell).toMatch(/margin:\s*0 auto/)
  })

  it('draws the phone frame only on wide screens', () => {
    expect(css).toMatch(/@media \(min-width: 640px\)[^{]*\{[^]*?\.app-shell \{[^}]*border-radius: 56px/)
  })
})

/** The declarations of the first top-level rule with exactly this selector. */
function rule(css: string, selector: string): string {
  const match = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].find((m) => m[1].trim() === selector)
  if (!match) throw new Error(`no rule ${selector}`)
  return match[2]
}

/** Every rule (also inside @media): its selectors and declarations. */
function rules(css: string) {
  return [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
    selectors: m[1].trim().split(/\s*,\s*/),
    body: m[2],
  }))
}

/** A CSS length in px at the 24 px base (rem and em count as 24 px). */
function px(value: string): number {
  const v = value.trim()
  const max = /^max\(\s*([\d.]+)px/.exec(v)
  if (max) return Number(max[1])
  const unit = /^([\d.]+)(px|rem|em)$/.exec(v)
  if (!unit) throw new Error(`cannot read ${v}`)
  return unit[2] === 'px' ? Number(unit[1]) : Number(unit[1]) * 24
}

describe('minimum sizes (NF-08)', () => {
  const css = read('src/styles.css').replace(/\/\*[^]*?\*\//g, '')
  const all = rules(css)

  it('body text is never below 24 px', () => {
    expect(px(/font-size:\s*([^;]+);/.exec(rule(css, ':root'))![1])).toBeGreaterThanOrEqual(24)
    expect(rule(css, 'body')).toMatch(/font-size:\s*1rem/)
    const sizes = all.flatMap((r) => [...r.body.matchAll(/font-size:\s*([^;]+);/g)].map((m) => ({ at: r.selectors, size: m[1] })))
    expect(sizes.length).toBeGreaterThan(20)
    const small = sizes.filter(({ size }) => px(size) < 24)
    expect(small).toEqual([])
  })

  it('questions are at least 32 px', () => {
    const question = all.filter((r) => r.selectors.includes('.question'))
    expect(question.length).toBeGreaterThan(0)
    for (const r of question) {
      const size = /font-size:\s*([^;]+);/.exec(r.body)
      if (size) expect(px(size[1])).toBeGreaterThanOrEqual(32)
    }
  })

  it('every button, switch and field is at least 64 px tall', () => {
    expect(px(/min-height:\s*([^;]+);/.exec(rule(css, '.button'))![1])).toBeGreaterThanOrEqual(64)
    expect(px(/min-height:\s*([^;]+);/.exec(rule(css, '.switch'))![1])).toBeGreaterThanOrEqual(64)
    expect(px(/min-height:\s*([^;]+);/.exec(rule(css, '.input'))![1])).toBeGreaterThanOrEqual(64)
    const tappable = all.filter((r) => r.selectors.some((s) => /\.(button|talk|switch|input|choice__button)\b/.test(s)))
    const heights = tappable.flatMap((r) => [...r.body.matchAll(/(?:^|[;\s])(?:min-)?height:\s*([^;]+);/g)].map((m) => m[1]))
    expect(heights.length).toBeGreaterThan(5)
    for (const h of heights) expect(px(h)).toBeGreaterThanOrEqual(64)
  })
})

describe('installable app (PWA)', () => {
  const manifest = JSON.parse(read('public/manifest.webmanifest')) as {
    name: string
    short_name: string
    start_url: string
    scope: string
    display: string
    background_color: string
    theme_color: string
    icons: Array<{ src: string; sizes: string; type: string; purpose?: string }>
  }

  it('has a manifest with a name, start page, standalone display and colours', () => {
    expect(manifest.name).toBeTruthy()
    expect(manifest.short_name.length).toBeLessThanOrEqual(12)
    expect(manifest.start_url).toBe('/')
    expect(manifest.scope).toBe('/')
    expect(manifest.display).toBe('standalone')
    expect(manifest.background_color).toMatch(/^#[0-9a-f]{6}$/i)
    expect(manifest.theme_color).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('has 192 px and 512 px PNG icons (and a maskable one), and they exist at that size', () => {
    for (const size of [192, 512]) {
      const icon = manifest.icons.find((i) => i.sizes === `${size}x${size}` && i.type === 'image/png')
      expect(icon).toBeTruthy()
      const png = readFileSync(join(ROOT, 'public', icon!.src))
      expect(png.subarray(1, 4).toString()).toBe('PNG')
      expect(png.readUInt32BE(16)).toBe(size) // IHDR width
      expect(png.readUInt32BE(20)).toBe(size) // IHDR height
    }
    expect(manifest.icons.some((i) => i.purpose === 'maskable')).toBe(true)
    for (const icon of manifest.icons) {
      expect(icon.src.startsWith('/')).toBe(true) // our own files only, never another host
      expect(existsSync(join(ROOT, 'public', icon.src))).toBe(true)
    }
  })

  it('the page links the manifest and icon, and the built page allows only its own manifest and worker', () => {
    const html = read('index.html')
    expect(html).toContain('<link rel="manifest" href="/manifest.webmanifest" />')
    expect(html).toContain('<link rel="icon" href="/icon.svg" type="image/svg+xml" />')
    const config = read('vite.config.ts')
    expect(config).toContain(`"manifest-src 'self'"`)
    expect(config).toContain(`"worker-src 'self'"`)
  })

  it('registers the offline shell only in built pages', () => {
    const main = read('src/main.tsx')
    expect(main).toMatch(/import\.meta\.env\.PROD && 'serviceWorker' in navigator/)
    expect(main).toContain("register('/sw.js'")
  })
})

describe('offline shell worker (public/sw.js)', () => {
  type Handler = (event: Record<string, unknown>) => void
  const ORIGIN = 'http://127.0.0.1:5173'

  function loadWorker() {
    const handlers: Record<string, Handler> = {}
    const cache = { addAll: vi.fn(async () => undefined), put: vi.fn(async () => undefined) }
    const caches = {
      open: vi.fn(async () => cache),
      match: vi.fn(async () => undefined),
      keys: vi.fn(async () => []),
      delete: vi.fn(async () => true),
    }
    const fetchMock = vi.fn(async () => ({ ok: true, clone: () => ({}) }))
    const self = {
      location: { origin: ORIGIN },
      addEventListener: (type: string, handler: Handler) => {
        handlers[type] = handler
      },
      skipWaiting: vi.fn(),
      clients: { claim: vi.fn() },
    }
    new Function('self', 'caches', 'fetch', 'Response', read('public/sw.js'))(self, caches, fetchMock, {
      error: () => ({}),
    })
    const request = (url: string, method = 'GET', mode = 'cors') => {
      const respondWith = vi.fn()
      handlers.fetch({ request: { url, method, mode }, respondWith })
      return respondWith
    }
    return { request, caches, cache, fetchMock }
  }

  it('never answers, and so never caches, a request to the patient runtime', () => {
    const { request } = loadWorker()
    expect(request('http://127.0.0.1:8001/checkin/sessions', 'POST')).not.toHaveBeenCalled()
    expect(request('http://127.0.0.1:8001/checkin/question?index=0&ask=0')).not.toHaveBeenCalled()
    expect(request('http://127.0.0.1:8001/checkin/sessions/ses_1/summary')).not.toHaveBeenCalled()
    expect(request('http://127.0.0.1:8001/network-log')).not.toHaveBeenCalled()
  })

  it('leaves every non-GET and every unknown same-origin path alone', () => {
    const { request } = loadWorker()
    expect(request(`${ORIGIN}/assets/index.js`, 'POST')).not.toHaveBeenCalled()
    expect(request(`${ORIGIN}/checkin/turn`)).not.toHaveBeenCalled()
    expect(request(`${ORIGIN}/anything-else.json`)).not.toHaveBeenCalled()
  })

  it("serves the page and this app's own built files, so the screen opens offline", () => {
    const { request } = loadWorker()
    expect(request(`${ORIGIN}/`, 'GET', 'navigate')).toHaveBeenCalledOnce()
    expect(request(`${ORIGIN}/assets/index-abc123.js`)).toHaveBeenCalledOnce()
    expect(request(`${ORIGIN}/icon-192.png`)).toHaveBeenCalledOnce()
  })

  it('keeps no copy of anything but the shell on install', () => {
    const source = read('public/sw.js')
    expect(source).not.toMatch(/8001|checkin|consent|network-log/)
    const shell = /const SHELL = \[([^\]]*)\]/.exec(source)![1]
    expect(shell.split(',').map((s) => s.trim().replace(/'/g, ''))).toEqual([
      '/',
      '/index.html',
      '/manifest.webmanifest',
      '/icon.svg',
      '/icon-192.png',
      '/icon-512.png',
    ])
  })
})
