// "Or type your answer", the sound controls (Mute / Unmute, Stop) and the one-line "Repeat" label.
// Rendered to static HTML and driven through the pure modules (no browser needed). Synthetic data only.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, MAX_TYPED_ANSWER, RuntimeError, type FetchLike, type Question, type TurnResult } from '../src/api.ts'
import { turnOutcome } from '../src/CheckinChat.tsx'
import { typedAnswerErrorMessage } from '../src/messages.ts'
import { createPlayer, type AudioLike } from '../src/player.ts'
import { INITIAL_SHARE_STATE, type ShareState } from '../src/shareFlow.ts'
import { ShareView } from '../src/ShareScreen.tsx'
import { Shell } from '../src/Shell.tsx'
import { MUTED_KEY, readMuted, saveMuted, type SoundStorage } from '../src/soundSetting.ts'
import { S } from '../src/strings.ts'
import { canSendTyped, TypeAnswer } from '../src/TypeAnswer.tsx'
import { BASE, json, SID, SUMMARY_READY } from './fixtures.ts'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const read = (path: string) => readFileSync(join(ROOT, path), 'utf8')
const noop = () => undefined

const TYPED = 'My arm itches a little'
const TURN = {
  transcript: TYPED,
  symptoms: [{ term_code: 'SE_RASH', label: 'Rash', severity: 'mild', onset: null }],
  extraction: 'ok',
  rating: 'complete',
  next: { action: 'next', unanswered: false },
}

const QUESTION: Question = { index: 0, total: 5, question_id: 'q1', purpose: 'wellbeing', ask: 0, text: 'How are you?' }

function mockFetch(response: Response) {
  return vi.fn<FetchLike>(async () => response)
}

function textOf(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim()
}

function buttonTag(html: string, label: string): string {
  const match = [...html.matchAll(/<button[^>]*>(.*?)<\/button>/g)].find((m) => textOf(m[1]) === label)
  if (!match) throw new Error(`no button "${label}"`)
  return match[0].slice(0, match[0].indexOf('>') + 1)
}

describe('postTextTurn', () => {
  it('POSTs the typed words as JSON to /checkin/turn/text and reads the answer like a spoken one', async () => {
    const fetchMock = mockFetch(json(TURN))
    const result = await createRuntimeClient(BASE, fetchMock).postTextTurn(SID, 'q1', 1, TYPED)
    expect(result).toEqual({ ...TURN, command: null })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/checkin/turn/text?session_id=${SID}&question_id=q1&ask=1`)
    expect(init?.method).toBe('POST')
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(String(init?.body))).toEqual({ text: TYPED })
    expect(init?.credentials).toBe('omit')
  })

  it('a typed "repeat" or "slower" comes back as a command at the same ask', async () => {
    for (const command of ['repeat', 'slower'] as const) {
      const body = { ...TURN, transcript: command, symptoms: [], next: { action: command, ask: 0 }, command }
      const result = await createRuntimeClient(BASE, mockFetch(json(body))).postTextTurn(SID, 'q1', 1, command)
      expect(result.command).toBe(command)
      expect(result.next).toEqual({ action: command, ask: 1 })
    }
  })

  it.each([
    [400, 'empty-text'],
    [422, 'text-too-long'],
    [403, 'forbidden'],
    [503, 'speech-unavailable'],
    [404, 'session-not-found'],
    [409, 'already-shared'],
  ])('maps HTTP %i to %s', async (status, kind) => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'x' }, status)))
    await expect(client.postTextTurn(SID, 'q1', 0, TYPED)).rejects.toMatchObject({ kind, status })
  })

  it('never sends a blank or too-long answer', async () => {
    const fetchMock = mockFetch(json(TURN))
    const client = createRuntimeClient(BASE, fetchMock)
    await expect(client.postTextTurn(SID, 'q1', 0, '   ')).rejects.toMatchObject({ kind: 'empty-text' })
    await expect(client.postTextTurn(SID, 'q1', 0, 'a'.repeat(MAX_TYPED_ANSWER + 1))).rejects.toMatchObject({
      kind: 'text-too-long',
    })
    expect(fetchMock).not.toHaveBeenCalled()
    expect(MAX_TYPED_ANSWER).toBe(1000)
  })

  it('says each problem in plain words', () => {
    expect(typedAnswerErrorMessage(new RuntimeError('empty-text', 400))).toBe(S.errors.typed.empty)
    expect(typedAnswerErrorMessage(new RuntimeError('text-too-long', 422))).toBe(S.errors.typed.tooLong)
    expect(typedAnswerErrorMessage(new RuntimeError('speech-unavailable', 503))).toBe(S.errors.typed.unavailable)
    expect(typedAnswerErrorMessage(new RuntimeError('forbidden', 403))).toBe(S.errors.answer.forbidden)
    expect(typedAnswerErrorMessage(new RuntimeError('runtime-down'))).toBe(S.errors.runtimeDown)
  })
})

describe('typed answers take the same path as spoken ones', () => {
  const result = (patch: Partial<TurnResult>): TurnResult => ({ ...(TURN as TurnResult), command: null, ...patch })

  it('shows the typed words as his own bubble, then what was noted, and moves on like a spoken answer', () => {
    const { step, bubbles } = turnOutcome(QUESTION, result({}))
    expect(step).toEqual({ kind: 'answered' })
    expect(bubbles[0]).toEqual({ kind: 'answer', words: TYPED })
    expect(bubbles[1]).toMatchObject({ kind: 'noted' })
  })

  it('a typed command repeats the question at the same ask, slowly for "slower"', () => {
    const { step, bubbles } = turnOutcome(
      QUESTION,
      result({ transcript: 'slower', symptoms: [], next: { action: 'slower', ask: 0 }, command: 'slower' }),
    )
    expect(step).toEqual({ kind: 'command', command: 'slower', slow: true, question: QUESTION })
    expect(bubbles).toEqual([
      { kind: 'answer', words: 'slower' },
      { kind: 'command', command: 'slower' },
    ])
  })

  it('App sends spoken and typed answers through one handler, and clears the box only after it worked', () => {
    const app = read('src/App.tsx')
    expect(app.match(/handleTurn\(question, result\)/g)).toHaveLength(2)
    expect(app).toContain('client.postTextTurn(sessionId, question.question_id, question.ask, text)')
    const send = app.slice(app.indexOf('const sendTyped'), app.indexOf('const hear ='))
    expect(send.indexOf("setTyped('')")).toBeGreaterThan(send.indexOf('await client.postTextTurn'))
    expect(send.slice(send.indexOf('catch'))).not.toContain("setTyped('')")
  })

  it('the typed box sits in the dock, under the talk button', () => {
    const app = read('src/App.tsx')
    const dock = app.slice(app.indexOf('<div className="dock">'))
    expect(dock.indexOf('<TypeAnswer')).toBeGreaterThan(dock.indexOf('className={`button talk talk--${talk}`}'))
  })

  it('the typed words are cleared on every question change', () => {
    const app = read('src/App.tsx')
    const reset = app.slice(app.indexOf('const resetForQuestionChange'), app.indexOf('/** After the last question'))
    expect(reset).toContain("setTyped('')")
  })
})

describe('"Or type your answer"', () => {
  const render = (text: string, busy = false) =>
    renderToStaticMarkup(<TypeAnswer text={text} onChange={noop} onSend={noop} busy={busy} />)

  it('has a labelled box of up to 1000 characters and a big Send with an icon', () => {
    const html = render('')
    expect(textOf(html)).toContain(S.checkin.typeLabel)
    expect(html).toMatch(/<label for="([^"]+)"[^>]*>[^<]*<\/label><textarea id="\1"/)
    expect(html).toContain('maxLength="1000"')
    expect(html).toMatch(/spell[cC]heck="false"/)
    expect(buttonTag(html, 'Send')).toContain('button--primary')
    expect(html).toMatch(/<button[^>]*><svg[^>]*aria-hidden="true"/)
  })

  it('Send is disabled while the box is empty or blank, or while an answer is recorded or sent', () => {
    expect(buttonTag(render(''), 'Send')).toContain('aria-disabled="true"')
    expect(buttonTag(render('   \n '), 'Send')).toContain('aria-disabled="true"')
    expect(buttonTag(render(TYPED, true), 'Send')).toContain('aria-disabled="true"')
    expect(buttonTag(render(TYPED), 'Send')).toContain('aria-disabled="false"')
    expect(canSendTyped('', false)).toBe(false)
    expect(canSendTyped(TYPED, true)).toBe(false)
    expect(canSendTyped(TYPED, false)).toBe(true)
  })

  it('the typed words are never put in browser storage', () => {
    for (const file of ['src/App.tsx', 'src/TypeAnswer.tsx']) {
      expect(read(file)).not.toMatch(/localstorage|sessionstorage|indexeddb/i)
    }
    // The only storage writer is the sound setting, and it only ever writes "1" or "0".
    expect(read('src/App.tsx').match(/saveMuted\(([^)]*)\)/g)).toEqual(['saveMuted(next)'])
  })
})

/** A stand-in for the audio element: records play/pause and fires the same events. */
class FakeAudio extends EventTarget {
  src = ''
  preload = ''
  currentTime = 0
  play = vi.fn(async () => {
    this.dispatchEvent(new Event('playing'))
  })
  pause = vi.fn(() => {
    this.dispatchEvent(new Event('pause'))
  })
  load = vi.fn()
  removeAttribute = vi.fn()
}

function fakePlayer() {
  const element = new FakeAudio()
  const changes: boolean[] = []
  const player = createPlayer((playing) => changes.push(playing), element as unknown as AudioLike)
  return { element, changes, player }
}

const wav = () => new Blob(['RIFF'], { type: 'audio/wav' })

describe('player: playing state, Stop and Mute', () => {
  it('reports playing while audio plays, and Stop ends it at once and goes back to the start', async () => {
    const { element, changes, player } = fakePlayer()
    const seen: boolean[] = []
    player.subscribe((playing) => seen.push(playing))
    await player.play(wav())
    expect(player.isPlaying()).toBe(true)
    element.currentTime = 3
    player.stop()
    expect(player.isPlaying()).toBe(false)
    expect(element.currentTime).toBe(0)
    expect(changes).toEqual([true, false])
    expect(seen).toEqual([true, false])
  })

  it('Mute stops the sound now, and nothing plays while muted (questions, re-asks, the summary)', async () => {
    const { element, player } = fakePlayer()
    await player.play(wav())
    player.setMuted(true)
    expect(player.isPlaying()).toBe(false)
    expect(element.pause).toHaveBeenCalled()
    element.play.mockClear()
    await player.play(wav())
    expect(element.play).not.toHaveBeenCalled()
    expect(player.isPlaying()).toBe(false)
  })

  it('Unmute never replays anything by itself', async () => {
    const { element, player } = fakePlayer()
    player.setMuted(true)
    player.setMuted(false)
    expect(element.play).not.toHaveBeenCalled()
    await player.play(wav())
    expect(element.play).toHaveBeenCalledOnce()
  })

  it('App: muted means no question is fetched or spoken, and Repeat shows a note instead', () => {
    const app = read('src/App.tsx')
    const speak = app.slice(app.indexOf('const speak = useCallback'), app.indexOf('const resetForQuestionChange'))
    expect(speak).toContain('if (!player.current || mutedNow.current) return')
    const hear = app.slice(app.indexOf('const hear ='), app.indexOf('const toggleMute'))
    expect(hear).toContain('setSoundOffNote(true)')
    expect(app).toContain('player.current.setMuted(mutedNow.current)')
    const toggle = app.slice(app.indexOf('const toggleMute'), app.indexOf('const stopSound'))
    expect(toggle).toContain('player.current?.setMuted(next)')
    expect(toggle).not.toMatch(/speak\(|play\(/)
  })
})

describe('sound setting: this browser session only', () => {
  function memory(): SoundStorage & { data: Map<string, string> } {
    const data = new Map<string, string>()
    return { data, getItem: (key) => data.get(key) ?? null, setItem: (key, value) => void data.set(key, value) }
  }

  it('is on by default and remembers Mute under one key', () => {
    const store = memory()
    expect(readMuted(store)).toBe(false)
    saveMuted(true, store)
    expect([...store.data]).toEqual([[MUTED_KEY, '1']])
    expect(readMuted(store)).toBe(true)
    saveMuted(false, store)
    expect(readMuted(store)).toBe(false)
    expect(MUTED_KEY).toBe('patient-web.muted')
  })

  it('blocked storage never breaks the screen: the sound is simply on', () => {
    const blocked: SoundStorage = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    }
    expect(readMuted(blocked)).toBe(false)
    expect(() => saveMuted(true, blocked)).not.toThrow()
    expect(readMuted(null)).toBe(false)
  })

  it('uses sessionStorage, never localStorage', () => {
    const source = read('src/soundSetting.ts')
    expect(source).toContain('globalThis.sessionStorage')
    expect(source).not.toMatch(/localstorage/i)
  })
})

describe('Mute / Unmute on every screen, Stop only while playing', () => {
  it('the shell shows the sound switch with its word and aria-pressed', () => {
    const on = renderToStaticMarkup(<Shell sound={{ muted: false, onToggle: noop }}>x</Shell>)
    expect(buttonTag(on, 'Mute')).toContain('aria-pressed="false"')
    const off = renderToStaticMarkup(<Shell sound={{ muted: true, onToggle: noop }}>x</Shell>)
    expect(buttonTag(off, 'Unmute')).toContain('aria-pressed="true"')
    expect(off).toMatch(/<header class="app-header"><button[^>]*><svg/)
  })

  const render = (patch: Partial<Parameters<typeof ShareView>[0]> = {}) => {
    const state: ShareState = { ...INITIAL_SHARE_STATE, phase: 'review', summary: SUMMARY_READY }
    return renderToStaticMarkup(
      <ShareView
        state={state}
        onChoose={noop}
        onShare={noop}
        onNotNow={noop}
        onBack={noop}
        onRetryLoad={noop}
        onRestart={noop}
        {...patch}
      />,
    )
  }


  it('Repeat with the sound off says how to hear it', () => {
    expect(textOf(render())).not.toContain(S.sound.offNote)
    expect(textOf(render({ soundOff: true }))).toContain('Sound is off. Tap Unmute to hear it.')
  })

  it('Stop sits in the top bar beside Mute, only while a question or the summary is playing', () => {
    const idle = renderToStaticMarkup(<Shell sound={{ muted: false, onToggle: noop, playing: false, onStop: noop }}>x</Shell>)
    expect(() => buttonTag(idle, 'Stop')).toThrow()
    const playing = renderToStaticMarkup(<Shell sound={{ muted: false, onToggle: noop, playing: true, onStop: noop }}>x</Shell>)
    expect(buttonTag(playing, 'Stop')).toBeTruthy()
    expect(playing.indexOf('Stop')).toBeLessThan(playing.indexOf('Mute'))
    expect(() => buttonTag(render(), 'Stop')).toThrow() // not repeated in the summary's own controls
    const app = read('src/App.tsx')
    expect(app).toContain('playing: speaking, onStop: stopSound')
    expect(app).toContain('const stopSound = () => player.current?.stop()')
  })
})

describe('"Repeat" fits on one line at phone width', () => {
  const css = read('src/styles.css').replace(/\/\*[^]*?\*\//g, '')

  it('is called "Repeat" on the check-in and the summary', () => {
    expect(S.checkin.hearAgain).toBe('Repeat')
    expect(S.summary.hearAgain).toBe('Repeat')
  })

  it('button words never wrap; whole buttons wrap instead', () => {
    expect(css).toMatch(/\.button__label \{[^}]*white-space: nowrap/)
    expect(css).toMatch(/\.voice-controls \{[^}]*flex-wrap: wrap/)
    expect(css).toMatch(/\.voice-controls \.button \{[^}]*flex: 1 1 auto/)
    for (const file of ['src/App.tsx', 'src/ShareScreen.tsx']) {
      expect(read(file)).toMatch(/<span className="button__label">\{[CW]\.hearAgain\}<\/span>/)
    }
  })
})
