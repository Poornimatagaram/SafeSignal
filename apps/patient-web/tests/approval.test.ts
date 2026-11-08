// PV-04: nothing is sent until the patient taps "Share this". The check-in is driven end to end through the real
// API client against a mocked runtime, and every request is recorded: no approve call may appear before share().
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, type CheckinSummary, type FetchLike } from '../src/api.ts'
import { canShare, createShareFlow, missingSeverities, severitiesToSend, type ShareFlow } from '../src/shareFlow.ts'
import {
  BASE,
  json,
  RECEIPT_QUEUED,
  RECEIPT_SENT,
  SID,
  SUMMARY_EMPTY,
  SUMMARY_NEEDS_SEVERITY,
  SUMMARY_READY,
} from './fixtures.ts'

const TURN = { transcript: 'a bit of a rash', symptoms: [], extraction: 'ok' }

interface Call {
  method: string
  path: string
  body: unknown
}

/** A fake runtime that records every request. `approveResponse` may be delayed to test a double tap. */
function fakeRuntime(summary: CheckinSummary, approveResponse: () => Promise<Response> = async () => json(RECEIPT_SENT)) {
  const calls: Call[] = []
  const fetchMock = vi.fn<FetchLike>(async (input, init) => {
    const url = new URL(input)
    const method = init?.method ?? 'GET'
    calls.push({ method, path: url.pathname, body: init?.body })
    if (method === 'POST' && url.pathname === '/checkin/sessions') return json({ session_id: SID, total: 2 }, 201)
    if (method === 'POST' && url.pathname === '/checkin/turn') return json(TURN)
    if (method === 'GET' && url.pathname === `/checkin/sessions/${SID}/summary`) return json(summary)
    if (method === 'POST' && url.pathname === `/checkin/sessions/${SID}/approve`) return approveResponse()
    return json({ detail: 'not found' }, 404)
  })
  const client = createRuntimeClient(BASE, fetchMock)
  const approveCalls = () => calls.filter((call) => call.path.endsWith('/approve'))
  return { client, calls, approveCalls }
}

/** Start a check-in, answer both questions and open the summary, exactly as the screen does. */
async function throughTheQuestions(summary: CheckinSummary, approveResponse?: () => Promise<Response>) {
  const runtime = fakeRuntime(summary, approveResponse)
  const session = await runtime.client.startSession()
  const audio = new Blob(['x'], { type: 'audio/webm' })
  await runtime.client.postTurn(session.session_id, 'q1', 0, audio)
  await runtime.client.postTurn(session.session_id, 'q2', 0, audio)
  const flow = createShareFlow(runtime.client, session.session_id)
  await flow.load()
  return { ...runtime, flow }
}

/** Let any stray promise (an accidental auto-share) run before checking. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('approve-before-share (PV-04)', () => {
  it('sends every answer with the session id, and nothing before "Share this"', async () => {
    const { calls, approveCalls, flow } = await throughTheQuestions(SUMMARY_READY)
    await settle()
    expect(calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      'POST /checkin/sessions',
      'POST /checkin/turn',
      'POST /checkin/turn',
      `GET /checkin/sessions/${SID}/summary`,
    ])
    expect(approveCalls()).toEqual([])
    expect(flow.getState().phase).toBe('review')
    expect(canShare(flow.getState())).toBe(true)
  })

  it('makes exactly one approve call, on the tap, with {} when no severity was needed', async () => {
    const { approveCalls, flow } = await throughTheQuestions(SUMMARY_READY)
    await flow.share()
    expect(approveCalls()).toHaveLength(1)
    expect(JSON.parse(String(approveCalls()[0].body))).toEqual({ severities: {} })
    expect(flow.getState().phase).toBe('receipt')
    expect(flow.getState().receipt).toEqual(RECEIPT_SENT)
  })

  it('never sends while a severity is missing; sends only the chosen ones after the tap', async () => {
    const { approveCalls, flow } = await throughTheQuestions(SUMMARY_NEEDS_SEVERITY)
    expect(missingSeverities(flow.getState())).toEqual(['SE_RASH'])
    expect(canShare(flow.getState())).toBe(false)

    await flow.share() // tapped while still disabled
    expect(approveCalls()).toEqual([])
    expect(flow.getState().phase).toBe('review')

    flow.chooseSeverity('SE_RASH', 'mild')
    flow.chooseSeverity('SE_RASH', 'severe') // changed their mind
    flow.chooseSeverity('SE_FATIGUE', 'severe') // not asked for: ignored
    await settle()
    expect(approveCalls()).toEqual([])
    expect(canShare(flow.getState())).toBe(true)

    await flow.share()
    expect(approveCalls()).toHaveLength(1)
    expect(JSON.parse(String(approveCalls()[0].body))).toEqual({ severities: { SE_RASH: 'severe' } })
  })

  it('"Not now" and going back send nothing', async () => {
    const { calls, approveCalls, flow } = await throughTheQuestions(SUMMARY_READY)
    const before = calls.length
    flow.notNow()
    expect(flow.getState().phase).toBe('not-shared')
    await flow.share() // not on the summary: ignored
    flow.backToSummary()
    expect(flow.getState().phase).toBe('review')
    flow.notNow()
    await settle()
    expect(calls.length).toBe(before)
    expect(approveCalls()).toEqual([])
  })

  it('shares "no new problems" only on the tap', async () => {
    const { approveCalls, flow } = await throughTheQuestions(SUMMARY_EMPTY)
    await settle()
    expect(approveCalls()).toEqual([])
    expect(canShare(flow.getState())).toBe(true)
    await flow.share()
    expect(approveCalls()).toHaveLength(1)
  })

  it('a double tap sends once', async () => {
    let release: (response: Response) => void = () => undefined
    const pending = new Promise<Response>((resolve) => {
      release = resolve
    })
    const { approveCalls, flow } = await throughTheQuestions(SUMMARY_READY, () => pending)
    const first = flow.share()
    const second = flow.share()
    expect(flow.getState().phase).toBe('sending')
    release(json(RECEIPT_QUEUED))
    await Promise.all([first, second])
    await flow.share() // tapping again on the receipt
    expect(approveCalls()).toHaveLength(1)
    expect(flow.getState().receipt).toEqual(RECEIPT_QUEUED)
  })

  it('on 409 asks for the missing severities and waits for another tap', async () => {
    let answer = json({ detail: { message: 'severity missing', needs_severity: ['SE_RASH'] } }, 409)
    const { approveCalls, flow } = await throughTheQuestions(SUMMARY_READY, async () => answer)
    await flow.share()
    let state = flow.getState()
    expect(state.phase).toBe('review')
    expect(state.needs).toEqual(['SE_RASH'])
    expect(state.failure).not.toBeNull()
    expect(canShare(state)).toBe(false)

    answer = json(RECEIPT_SENT)
    flow.chooseSeverity('SE_RASH', 'moderate')
    await settle()
    expect(approveCalls()).toHaveLength(1) // only the refused tap so far
    await flow.share()
    state = flow.getState()
    expect(approveCalls()).toHaveLength(2)
    expect(JSON.parse(String(approveCalls()[1].body))).toEqual({ severities: { SE_RASH: 'moderate' } })
    expect(state.phase).toBe('receipt')
  })

  it('keeps the summary and allows another tap after a failed request', async () => {
    let down = true
    const { approveCalls, flow } = await throughTheQuestions(SUMMARY_READY, async () => {
      if (down) throw new TypeError('Failed to fetch')
      return json(RECEIPT_SENT)
    })
    await flow.share()
    expect(flow.getState()).toMatchObject({ phase: 'review', failure: { error: { kind: 'runtime-down' } } })
    down = false
    await flow.share()
    expect(approveCalls()).toHaveLength(2)
    expect(flow.getState().phase).toBe('receipt')
  })

  it('a summary that fails to load can be retried and never sends', async () => {
    let fail = true
    const calls: string[] = []
    const client = createRuntimeClient(
      BASE,
      vi.fn<FetchLike>(async (input) => {
        calls.push(new URL(input).pathname)
        if (fail) return json({ detail: 'unknown session' }, 404)
        return json(SUMMARY_READY)
      }),
    )
    const flow: ShareFlow = createShareFlow(client, SID)
    await flow.load()
    expect(flow.getState()).toMatchObject({ phase: 'load-failed', failure: { error: { kind: 'session-not-found' } } })
    await flow.share()
    fail = false
    await flow.load()
    expect(flow.getState().phase).toBe('review')
    expect(calls.every((path) => path.endsWith('/summary'))).toBe(true)
  })

  it('notifies subscribers on every change', async () => {
    const { flow } = await throughTheQuestions(SUMMARY_NEEDS_SEVERITY)
    const seen: string[] = []
    const stop = flow.subscribe(() => seen.push(flow.getState().phase))
    flow.chooseSeverity('SE_RASH', 'mild')
    await flow.share()
    stop()
    flow.notNow()
    expect(seen).toEqual(['review', 'sending', 'receipt'])
  })
})

describe('severitiesToSend', () => {
  it('includes only the severities the runtime asked for', () => {
    const state = {
      ...createShareFlow(fakeRuntime(SUMMARY_READY).client, SID).getState(),
      needs: ['SE_RASH'],
      chosen: { SE_RASH: 'mild', SE_COUGH: 'severe' } as const,
    }
    expect(severitiesToSend(state)).toEqual({ SE_RASH: 'mild' })
  })
})

describe('only the "Share this" tap can approve', () => {
  const ROOT = fileURLToPath(new URL('..', import.meta.url))
  const SRC = join(ROOT, 'src')
  const filesUnder = (dir: string): string[] =>
    readdirSync(dir).flatMap((name) => {
      const path = join(dir, name)
      return statSync(path).isDirectory() ? filesUnder(path) : [path]
    })

  it('calls approve( only from src/shareFlow.ts, once, inside share()', () => {
    const callers = filesUnder(SRC)
      .filter((path) => !path.endsWith('api.ts'))
      .flatMap((path) => {
        const text = readFileSync(path, 'utf8')
        return [...text.matchAll(/\.approve\s*\(/g)].map(() => relative(ROOT, path))
      })
    expect(callers).toEqual([join('src', 'shareFlow.ts')])

    const flow = readFileSync(join(SRC, 'shareFlow.ts'), 'utf8')
    const start = flow.indexOf('async share()')
    const shareBody = flow.slice(start, flow.indexOf('notNow()', start))
    expect(start).toBeGreaterThan(0)
    expect(shareBody).toMatch(/\.approve\s*\(/)
  })

  it('wires the Share this button to flow.share and nothing else', () => {
    const screen = readFileSync(join(SRC, 'ShareScreen.tsx'), 'utf8')
    expect(screen.match(/flow\.share\b/g)).toHaveLength(1)
    expect(screen).toMatch(/onShare=\{\(\) => void flow\.share\(\)\}/)
  })
})
