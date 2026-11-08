// Voice commands during questions (VC-07), the spoken summary with one correction (VC-08), the network-off queue
// (PV-07) and the severe-symptom alert line (AL-02). Driven through the real API client against a mocked runtime.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createRuntimeClient,
  type CheckinSummary,
  type EgressReceipt,
  type FetchLike,
  type Question,
} from '../src/api.ts'
import { afterTurn, createQuestionVoice } from '../src/questionFlow.ts'
import { canCorrect, createShareFlow, isWaitingToSend, RECEIPT_POLL_MS } from '../src/shareFlow.ts'
import { correctionErrorMessage } from '../src/messages.ts'
import { alertText } from '../src/summaryText.ts'
import {
  ALERT_QUEUED,
  ALERT_SENT,
  BASE,
  json,
  RECEIPT_QUEUED,
  RECEIPT_SENT,
  SID,
  SUMMARY_CORRECTED,
  SUMMARY_READY,
} from './fixtures.ts'

interface Call {
  method: string
  path: string
  query: string
  body: unknown
  contentType: string | null
}

type Handler = (call: Call) => Response | Promise<Response>

/** A fake runtime that records every request; `routes` answers `METHOD /path` (in order when given a list). */
function fakeRuntime(routes: Record<string, Handler | Handler[]>) {
  const calls: Call[] = []
  const queues = new Map(Object.entries(routes).map(([k, v]) => [k, Array.isArray(v) ? [...v] : v]))
  const fetchMock = vi.fn<FetchLike>(async (input, init) => {
    const url = new URL(input)
    const call: Call = {
      method: init?.method ?? 'GET',
      path: url.pathname,
      query: url.search,
      body: init?.body,
      contentType: new Headers(init?.headers).get('Content-Type'),
    }
    calls.push(call)
    const route = queues.get(`${call.method} ${call.path}`)
    if (!route) return json({ detail: 'not found' }, 404)
    const handler = Array.isArray(route) ? (route.length > 1 ? route.shift() : route[0]) : route
    if (!handler) return json({ detail: 'not found' }, 404)
    return handler(call)
  })
  const of = (method: string, path: string) => calls.filter((c) => c.method === method && c.path === path)
  return { client: createRuntimeClient(BASE, fetchMock), calls, of }
}

const wav = (label: string) => () => new Response(new Blob([label], { type: 'audio/wav' }), { status: 200 })
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

function fakePlayer() {
  const played: string[] = []
  return {
    played,
    play: vi.fn(async (audio: Blob) => {
      played.push(await audio.text())
    }),
    stop: vi.fn(),
  }
}

// ---------------------------------------------------------------------------------------------------------------
describe('voice commands during questions (VC-07)', () => {
  const QUESTION: Question = { index: 0, total: 3, question_id: 'q1', purpose: 'wellbeing', ask: 0, text: 'How are you?' }
  const turn = (extra: object) => () =>
    json({ transcript: 'x', symptoms: [], extraction: 'ok', rating: null, command: null, ...extra })

  it('replays the same wording (slow for "slower"), keeps the ask, and never counts as a re-ask', async () => {
    const runtime = fakeRuntime({
      'GET /checkin/question/audio': (call) => {
        const q = new URLSearchParams(call.query)
        return wav(`ask=${q.get('ask')} slow=${q.get('slow')}`)()
      },
      'POST /checkin/turn': [
        turn({ transcript: 'say that again', command: 'repeat', next: { action: 'repeat', ask: 0 } }),
        turn({ transcript: 'slower please', command: 'slower', next: { action: 'slower', ask: 0 } }),
        turn({ rating: 'rambling', next: { action: 'reask', ask: 1, text: 'Simpler?' } }),
        turn({ transcript: 'again', command: 'repeat', next: { action: 'repeat', ask: 1 } }),
        turn({ rating: 'partial', next: { action: 'reask', ask: 2, text: 'Better or worse?' } }),
        turn({ rating: 'complete', next: { action: 'next' } }),
      ],
    })
    const player = fakePlayer()
    const voice = createQuestionVoice(runtime.client, player.play)
    const recording = new Blob(['x'], { type: 'audio/webm' })

    let question = QUESTION
    await voice.speak(question, false)
    const steps: string[] = []
    for (;;) {
      const result = await runtime.client.postTurn(SID, question.question_id, question.ask, recording)
      const step = afterTurn(question, result)
      steps.push(step.kind === 'command' ? step.command : step.kind)
      if (step.kind === 'command') {
        expect(step.question).toEqual(question) // same wording, same ask
        await voice.speak(step.question, step.slow)
      } else if (step.kind === 'reask') {
        question = step.question
        await voice.speak(question, false)
      } else break
    }

    // Two commands did not use up the two re-asks.
    expect(steps).toEqual(['repeat', 'slower', 'reask', 'repeat', 'reask', 'answered'])
    expect(runtime.of('POST', '/checkin/turn').map((c) => new URLSearchParams(c.query).get('ask'))).toEqual([
      '0', '0', '0', '1', '1', '2',
    ])
    expect(player.played).toEqual([
      'ask=0 slow=false',
      'ask=0 slow=false', // "say that again": the cached wording
      'ask=0 slow=true', // "slower"
      'ask=1 slow=false',
      'ask=1 slow=false',
      'ask=2 slow=false',
    ])
  })

  it('the screen replays at once with a small note, and does not show the re-ask line', () => {
    const app = readFileSync(fileURLToPath(new URL('../src/App.tsx', import.meta.url)), 'utf8')
    const branch = app.slice(app.indexOf("step.kind === 'command'"), app.indexOf("step.kind === 'move-on'"))
    expect(branch).toContain('void speak(step.question, step.slow)')
    expect(branch).toContain('setNotice(step.command)')
    expect(branch).not.toContain("'reask'")
    expect(branch).not.toContain('setQuestion') // the same question and ask
    expect(app).toContain('Saying it again')
    expect(app).toContain('Saying it more slowly')
  })
})

// ---------------------------------------------------------------------------------------------------------------
function summaryRuntime(extra: Record<string, Handler | Handler[]> = {}) {
  let audioN = 0
  return fakeRuntime({
    [`GET /checkin/sessions/${SID}/summary`]: () => json(SUMMARY_READY),
    [`GET /checkin/sessions/${SID}/summary/audio`]: (call) => {
      audioN += 1
      return wav(`summary#${audioN} ${call.query}`)()
    },
    [`POST /checkin/sessions/${SID}/approve`]: () => json(RECEIPT_SENT),
    ...extra,
  })
}

describe('spoken summary', () => {
  it('is read out loud when it appears; "Hear it again" and "Slower" replay it; nothing is sent', async () => {
    const runtime = summaryRuntime()
    const player = fakePlayer()
    const flow = createShareFlow(runtime.client, SID, player)
    await flow.load()
    await settle()
    expect(player.played).toEqual(['summary#1 ?slow=false'])
    await flow.speakSummary(false) // cached
    await flow.speakSummary(true)
    expect(player.played).toEqual(['summary#1 ?slow=false', 'summary#1 ?slow=false', 'summary#2 ?slow=true'])
    expect(runtime.calls.some((c) => c.path.endsWith('/approve'))).toBe(false)
  })

  it('is not played when the runtime has no spoken text, and a voice failure keeps the summary', async () => {
    const quiet = fakeRuntime({ [`GET /checkin/sessions/${SID}/summary`]: () => json({ ...SUMMARY_READY, spoken: null }) })
    const player = fakePlayer()
    const flow = createShareFlow(quiet.client, SID, player)
    await flow.load()
    await settle()
    expect(player.play).not.toHaveBeenCalled()
    expect(quiet.of('GET', `/checkin/sessions/${SID}/summary/audio`)).toEqual([])

    const broken = summaryRuntime({ [`GET /checkin/sessions/${SID}/summary/audio`]: () => json({ detail: 'x' }, 503) })
    const flow2 = createShareFlow(broken.client, SID, fakePlayer())
    await flow2.load()
    await settle()
    expect(flow2.getState()).toMatchObject({ phase: 'review', voiceFailure: { error: { kind: 'speech-unavailable' } } })
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('one correction before sharing (VC-08)', () => {
  const correctionPath = `/checkin/sessions/${SID}/correction`

  async function opened(handlers: Handler[], summary: CheckinSummary = SUMMARY_READY) {
    const runtime = summaryRuntime({
      [`GET /checkin/sessions/${SID}/summary`]: () => json(summary),
      [`POST ${correctionPath}`]: handlers,
    })
    const player = fakePlayer()
    const flow = createShareFlow(runtime.client, SID, player)
    await flow.load()
    await settle()
    return { ...runtime, flow, player }
  }

  it('by tap: pick the item, then Mild; the updated summary is shown and read; the option is gone', async () => {
    const { flow, of, player } = await opened([() => json(SUMMARY_CORRECTED)])
    expect(canCorrect(flow.getState())).toBe(true)
    flow.openCorrection()
    flow.chooseCorrectionMode('tap')
    expect(flow.getState().correction.step).toBe('pick')
    flow.pickItem('SE_RASH')
    expect(flow.getState().correction).toMatchObject({ step: 'item', termCode: 'SE_RASH' })
    await flow.correct({ term_code: 'SE_RASH', severity: 'mild' })
    await settle()

    const posts = of('POST', correctionPath)
    expect(posts).toHaveLength(1)
    expect(posts[0].contentType).toBe('application/json')
    expect(JSON.parse(String(posts[0].body))).toEqual({ term_code: 'SE_RASH', severity: 'mild' })

    const state = flow.getState()
    expect(state.summary).toEqual(SUMMARY_CORRECTED)
    expect(state.correction.step).toBe('closed')
    expect(canCorrect(state)).toBe(false)
    expect(player.played).toEqual(['summary#1 ?slow=false', 'summary#2 ?slow=false']) // the updated summary, read again

    flow.openCorrection() // gone: ignored
    await flow.correct({ term_code: 'SE_RASH', remove: true })
    expect(of('POST', correctionPath)).toHaveLength(1)
    expect(of('POST', `/checkin/sessions/${SID}/approve`)).toEqual([]) // a correction never shares

    await flow.share() // "Share this" works as before
    expect(of('POST', `/checkin/sessions/${SID}/approve`)).toHaveLength(1)
  })

  it('by tap: onset and "I don\'t have this" send their change', async () => {
    for (const change of [
      { term_code: 'SE_RASH', onset: 'today' as const },
      { term_code: 'SE_RASH', remove: true as const },
    ]) {
      const { flow, of } = await opened([() => json(SUMMARY_CORRECTED)])
      flow.openCorrection()
      flow.chooseCorrectionMode('tap')
      flow.pickItem('SE_RASH')
      await flow.correct(change)
      expect(JSON.parse(String(of('POST', correctionPath)[0].body))).toEqual(change)
    }
  })

  it('by voice: a 422 is not used up; saying it again goes through', async () => {
    const notUnderstood = () => json({ detail: { message: 'not understood', understood: false } }, 422)
    const { flow, of, player } = await opened([notUnderstood, () => json(SUMMARY_CORRECTED)])
    flow.openCorrection()
    flow.chooseCorrectionMode('say')
    expect(player.stop).toHaveBeenCalled() // never talk over the patient
    const recording = new Blob(['the rash is mild'], { type: 'audio/webm' })

    await flow.correct(recording)
    let state = flow.getState()
    expect(state.correction).toMatchObject({ step: 'say', sending: false, failure: { error: { kind: 'correction-not-understood' } } })
    expect(canCorrect(state)).toBe(true)
    expect(correctionErrorMessage(state.correction.failure?.error)).toContain('did not understand the change')

    await flow.correct(recording)
    state = flow.getState()
    const posts = of('POST', correctionPath)
    expect(posts).toHaveLength(2)
    expect(posts.every((c) => c.contentType === 'audio/webm' && c.body === recording)).toBe(true)
    expect(state.summary?.correction_used).toBe(true)
    expect(state.correction).toEqual({ step: 'closed', termCode: null, sending: false, failure: null })
  })

  it('a 409 hides the option, says so, and shows the runtime\'s current summary', async () => {
    const { flow, of } = await opened([() => json({ detail: 'correction already used' }, 409)])
    flow.openCorrection()
    flow.chooseCorrectionMode('tap')
    flow.pickItem('SE_RASH')
    await flow.correct({ term_code: 'SE_RASH', severity: 'severe' })
    const state = flow.getState()
    expect(canCorrect(state)).toBe(false)
    expect(state.correction).toMatchObject({ step: 'closed', failure: { error: { kind: 'correction-used' } } })
    expect(of('GET', `/checkin/sessions/${SID}/summary`)).toHaveLength(2) // reloaded
    expect(correctionErrorMessage(state.correction.failure?.error)).toContain('cannot be changed again')
  })

  it('is not offered when already used, and "Keep it as it is" sends nothing', async () => {
    const used = await opened([], SUMMARY_CORRECTED)
    used.flow.openCorrection()
    expect(used.flow.getState().correction.step).toBe('closed')

    const { flow, calls } = await opened([])
    const before = calls.length
    flow.openCorrection()
    flow.chooseCorrectionMode('tap')
    flow.pickItem('SE_NOT_IN_SUMMARY') // ignored
    expect(flow.getState().correction.step).toBe('pick')
    flow.closeCorrection()
    expect(flow.getState().correction.step).toBe('closed')
    expect(calls.length).toBe(before)
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('network-off queue (PV-07) and alerts (AL-02)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  async function shared(receipts: EgressReceipt[], approve: EgressReceipt = RECEIPT_QUEUED) {
    vi.useFakeTimers()
    const runtime = summaryRuntime({
      [`POST /checkin/sessions/${SID}/approve`]: () => json(approve),
      [`GET /checkin/sessions/${SID}/receipt`]: receipts.map((r) => () => json(r)),
    })
    const flow = createShareFlow(runtime.client, SID, fakePlayer())
    await flow.load()
    await flow.share()
    const polls = () => runtime.of('GET', `/checkin/sessions/${SID}/receipt`).length
    return { ...runtime, flow, polls }
  }

  it('polls a queued receipt every 5 s until it is sent, then stops', async () => {
    const { flow, polls } = await shared([RECEIPT_QUEUED, RECEIPT_SENT])
    expect(RECEIPT_POLL_MS).toBe(5000)
    expect(flow.getState().receipt?.status).toBe('queued')
    expect(polls()).toBe(0)

    await vi.advanceTimersByTimeAsync(4999)
    expect(polls()).toBe(0)
    await vi.advanceTimersByTimeAsync(1)
    expect(polls()).toBe(1)
    expect(flow.getState().receipt?.status).toBe('queued')

    await vi.advanceTimersByTimeAsync(5000)
    expect(polls()).toBe(2)
    expect(flow.getState()).toMatchObject({ phase: 'receipt', receipt: RECEIPT_SENT })

    await vi.advanceTimersByTimeAsync(30000)
    expect(polls()).toBe(2) // stopped on sent
  })

  it('stops on failed, keeps trying while the runtime is down, and stops when the screen is left', async () => {
    const failed = await shared([{ ...RECEIPT_QUEUED, status: 'failed', response_code: 422 }])
    await vi.advanceTimersByTimeAsync(20000)
    expect(failed.polls()).toBe(1)
    vi.useRealTimers()

    const left = await shared([RECEIPT_QUEUED])
    await vi.advanceTimersByTimeAsync(5000)
    expect(left.polls()).toBe(1)
    left.flow.dispose()
    await vi.advanceTimersByTimeAsync(30000)
    expect(left.polls()).toBe(1)
  })

  it('never polls a receipt that was sent straight away', async () => {
    const { polls } = await shared([], RECEIPT_SENT)
    await vi.advanceTimersByTimeAsync(30000)
    expect(polls()).toBe(0)
  })

  it('keeps watching while only the alert is queued, until it is sent', async () => {
    const { flow, polls } = await shared(
      [{ ...RECEIPT_SENT, alert: ALERT_SENT }],
      { ...RECEIPT_SENT, alert: ALERT_QUEUED },
    )
    expect(isWaitingToSend(flow.getState().receipt)).toBe(true)
    await vi.advanceTimersByTimeAsync(5000)
    expect(flow.getState().receipt?.alert).toEqual(ALERT_SENT)
    await vi.advanceTimersByTimeAsync(30000)
    expect(polls()).toBe(1)
  })

  it('says the care team was (or will be) told, never which symptom', () => {
    expect(alertText(ALERT_SENT)).toBe('Your care team was told about the severe symptom.')
    expect(alertText(ALERT_QUEUED)).toBe('Your care team will be told about the severe symptom when the connection is back.')
    for (const status of ['sent', 'queued', 'failed'] as const) {
      expect(alertText({ ...ALERT_SENT, status })).not.toMatch(/rash|SE_|moderate|mild/i)
    }
  })
})
