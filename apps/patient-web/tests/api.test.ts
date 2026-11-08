import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, readAlert, RuntimeError, type FetchLike } from '../src/api.ts'
import { DEFAULT_RUNTIME_URL, resolveRuntimeUrl } from '../src/runtimeUrl.ts'
import {
  ALERT_QUEUED,
  ALERT_SENT,
  BASE,
  json,
  RECEIPT_FAILED,
  RECEIPT_QUEUED,
  RECEIPT_SENT,
  SID,
  SUMMARY_CORRECTED,
  SUMMARY_EMPTY,
  SUMMARY_NEEDS_SEVERITY,
  SUMMARY_READY,
} from './fixtures.ts'


const QUESTION = {
  index: 0,
  total: 6,
  question_id: 'q1',
  purpose: 'wellbeing',
  ask: 0,
  text: 'How have you been feeling since yesterday?',
}

const TURN = {
  transcript: 'I have a bit of a rash on my arm',
  symptoms: [{ term_code: 'SE_RASH', label: 'Rash', severity: 'moderate', onset: '1_3_days' }],
  extraction: 'ok',
}

/** What an older runtime's turn reads as: a complete answer, then move on. */
const OLD_RUNTIME_DEFAULTS = { rating: 'complete', next: { action: 'next', unanswered: false }, command: null }

function mockFetch(response: Response | (() => Promise<Response>)) {
  return vi.fn<FetchLike>(typeof response === 'function' ? response : async () => response)
}

function lastCall(fetchMock: ReturnType<typeof mockFetch>): { url: string; init: RequestInit } {
  const [url, init] = fetchMock.mock.calls.at(-1) ?? []
  return { url: String(url), init: init ?? {} }
}

describe('runtime base URL', () => {
  it('defaults to the local runtime', () => {
    expect(DEFAULT_RUNTIME_URL).toBe(BASE)
    expect(resolveRuntimeUrl(undefined)).toBe(BASE)
    expect(resolveRuntimeUrl('  ')).toBe(BASE)
  })

  it('keeps only the origin of a configured URL', () => {
    expect(resolveRuntimeUrl('http://localhost:9001/')).toBe('http://localhost:9001')
  })

  it('rejects non-http URLs', () => {
    expect(() => resolveRuntimeUrl('ftp://127.0.0.1:8001')).toThrow()
  })
})

describe('getQuestion', () => {
  it('GETs /checkin/question with index and ask', async () => {
    const fetchMock = mockFetch(json(QUESTION))
    const client = createRuntimeClient(BASE, fetchMock)
    await expect(client.getQuestion(0)).resolves.toEqual(QUESTION)
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/question?index=0&ask=0`)
    expect(init.method).toBe('GET')
    expect(init.credentials).toBe('omit')
    expect(init.cache).toBe('no-store')
  })

  it('passes a re-ask number', async () => {
    const fetchMock = mockFetch(json({ ...QUESTION, index: 3, ask: 1 }))
    await createRuntimeClient(BASE, fetchMock).getQuestion(3, 1)
    expect(lastCall(fetchMock).url).toBe(`${BASE}/checkin/question?index=3&ask=1`)
  })

  it('returns null when there are no more questions (404)', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'no more questions' }, 404)))
    await expect(client.getQuestion(6)).resolves.toBeNull()
  })

  it('reports a runtime that is not running', async () => {
    const client = createRuntimeClient(BASE, mockFetch(() => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(client.getQuestion(0)).rejects.toMatchObject({ name: 'RuntimeError', kind: 'runtime-down' })
  })

  it("reports today's questions never downloaded (503)", async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'not downloaded' }, 503)))
    await expect(client.getQuestion(0)).rejects.toMatchObject({ kind: 'questions-missing', status: 503 })
  })

  it('rejects a body that is not a question', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ hello: 'world' })))
    await expect(client.getQuestion(0)).rejects.toMatchObject({ kind: 'bad-response' })
  })

  it('does not double the slash for a base URL with a trailing slash', async () => {
    const fetchMock = mockFetch(json(QUESTION))
    await createRuntimeClient(`${BASE}/`, fetchMock).getQuestion(0)
    expect(lastCall(fetchMock).url).toBe(`${BASE}/checkin/question?index=0&ask=0`)
  })
})

describe('getQuestionAudio', () => {
  it('GETs the spoken question at normal speed by default', async () => {
    const wav = new Blob([new Uint8Array([82, 73, 70, 70])], { type: 'audio/wav' })
    const fetchMock = mockFetch(new Response(wav, { status: 200, headers: { 'Content-Type': 'audio/wav' } }))
    const audio = await createRuntimeClient(BASE, fetchMock).getQuestionAudio(0)
    expect(audio.size).toBe(4)
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/question/audio?index=0&ask=0&slow=false`)
    expect(init.method).toBe('GET')
  })

  it('asks for the slower voice', async () => {
    const fetchMock = mockFetch(new Response(new Blob(['x']), { status: 200 }))
    await createRuntimeClient(BASE, fetchMock).getQuestionAudio(2, 1, true)
    expect(lastCall(fetchMock).url).toBe(`${BASE}/checkin/question/audio?index=2&ask=1&slow=true`)
  })

  it('reports text-to-speech that is not available (503)', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'text-to-speech unavailable' }, 503)))
    await expect(client.getQuestionAudio(0)).rejects.toMatchObject({ kind: 'speech-unavailable', status: 503 })
  })
})

describe('postTurn', () => {
  it('POSTs the raw recording with its own Content-Type', async () => {
    const recording = new Blob([new Uint8Array(32)], { type: 'audio/webm;codecs=opus' })
    const fetchMock = mockFetch(json(TURN))
    const result = await createRuntimeClient(BASE, fetchMock).postTurn(SID, 'q1', 0, recording)
    expect(result).toEqual({ ...TURN, ...OLD_RUNTIME_DEFAULTS })
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/turn?session_id=${SID}&question_id=q1&ask=0`)
    expect(init.method).toBe('POST')
    expect(new Headers(init.headers).get('Content-Type')).toBe('audio/webm;codecs=opus')
    expect(init.body).toBe(recording)
    expect(init.credentials).toBe('omit')
  })

  it('sends Safari recordings as audio/mp4', async () => {
    const fetchMock = mockFetch(json(TURN))
    await createRuntimeClient(BASE, fetchMock).postTurn(SID, 'q2', 1, new Blob(['a'], { type: 'audio/mp4' }))
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/turn?session_id=${SID}&question_id=q2&ask=1`)
    expect(new Headers(init.headers).get('Content-Type')).toBe('audio/mp4')
  })

  it('falls back to application/octet-stream for an untyped recording', async () => {
    const fetchMock = mockFetch(json(TURN))
    await createRuntimeClient(BASE, fetchMock).postTurn(SID, 'q1', 0, new Blob(['a']))
    expect(new Headers(lastCall(fetchMock).init.headers).get('Content-Type')).toBe('application/octet-stream')
  })

  it('accepts symptoms: null when the local model is down', async () => {
    const body = { transcript: 'my nails are cracked', symptoms: null, extraction: 'unavailable' }
    const client = createRuntimeClient(BASE, mockFetch(json(body)))
    await expect(client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' }))).resolves.toEqual({
      ...body,
      ...OLD_RUNTIME_DEFAULTS,
    })
  })

  it('accepts a symptom without severity', async () => {
    const body = { ...TURN, symptoms: [{ term_code: 'SE_RASH', label: 'Rash', severity: null, onset: null }] }
    const client = createRuntimeClient(BASE, mockFetch(json(body)))
    await expect(client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' }))).resolves.toEqual({
      ...body,
      ...OLD_RUNTIME_DEFAULTS,
    })
  })

  it('reads a re-ask (VC-05): rating and the simpler wording', async () => {
    const next = { action: 'reask', ask: 1, text: 'Have you felt any different in your body since yesterday?' }
    const body = { ...TURN, rating: 'rambling', next }
    const client = createRuntimeClient(BASE, mockFetch(json(body)))
    const result = await client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' }))
    expect(result.rating).toBe('rambling')
    expect(result.next).toEqual(next)
  })

  it('reads "next" with and without unanswered', async () => {
    for (const [next, unanswered] of [
      [{ action: 'next', unanswered: true }, true],
      [{ action: 'next' }, false],
    ] as const) {
      const client = createRuntimeClient(BASE, mockFetch(json({ ...TURN, rating: 'no_answer', next })))
      const result = await client.postTurn(SID, 'q1', 2, new Blob(['a'], { type: 'audio/webm' }))
      expect(result.rating).toBe('no_answer')
      expect(result.next).toEqual({ action: 'next', unanswered })
    }
  })

  it.each([
    ['null', { rating: null, next: null }, 'complete'],
    ['missing', {}, 'complete'],
    ['unknown', { rating: 'excellent', next: { action: 'dance' } }, 'complete'],
    ['a re-ask with no wording', { rating: 'partial', next: { action: 'reask', ask: 1 } }, 'partial'],
  ])('reads %s rating/next as an answer that moves on', async (_name, extra, rating) => {
    const client = createRuntimeClient(BASE, mockFetch(json({ ...TURN, ...extra })))
    const result = await client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' }))
    expect(result.rating).toBe(rating)
    expect(result.next).toEqual({ action: 'next', unanswered: false })
  })

  it('never sends an empty recording', async () => {
    const fetchMock = mockFetch(json(TURN))
    await expect(createRuntimeClient(BASE, fetchMock).postTurn(SID, 'q1', 0, new Blob([]))).rejects.toMatchObject({
      kind: 'empty-audio',
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    [400, 'empty-audio'],
    [403, 'forbidden'],
    [413, 'too-large'],
    [404, 'session-not-found'],
    [409, 'already-shared'],
    [415, 'bad-format'],
    [422, 'not-understood'],
    [503, 'speech-unavailable'],
    [500, 'unknown'],
  ])('maps HTTP %i to %s', async (status, kind) => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'x' }, status)))
    const error = await client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' })).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(RuntimeError)
    expect(error).toMatchObject({ kind, status })
  })

  it('reports a runtime that is not running', async () => {
    const client = createRuntimeClient(BASE, mockFetch(() => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' }))).rejects.toMatchObject({
      kind: 'runtime-down',
    })
  })
})

describe('startSession', () => {
  it('POSTs /checkin/sessions with no body', async () => {
    const fetchMock = mockFetch(json({ session_id: SID, total: 6 }, 201))
    await expect(createRuntimeClient(BASE, fetchMock).startSession()).resolves.toEqual({ session_id: SID, total: 6 })
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/sessions`)
    expect(init.method).toBe('POST')
    expect(init.body).toBeUndefined()
    expect(init.credentials).toBe('omit')
  })

  it("reports today's questions never downloaded (503)", async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'no survey on this device' }, 503)))
    await expect(client.startSession()).rejects.toMatchObject({ name: 'RuntimeError', kind: 'questions-missing', status: 503 })
  })

  it('reports a runtime that is not running', async () => {
    const client = createRuntimeClient(BASE, mockFetch(() => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(client.startSession()).rejects.toMatchObject({ kind: 'runtime-down' })
  })

  it('rejects a body without a session id', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ total: 6 }, 201)))
    await expect(client.startSession()).rejects.toMatchObject({ kind: 'bad-response' })
  })
})

describe('getSummary', () => {
  it('GETs the session summary', async () => {
    const fetchMock = mockFetch(json(SUMMARY_READY))
    await expect(createRuntimeClient(BASE, fetchMock).getSummary(SID)).resolves.toEqual(SUMMARY_READY)
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/sessions/${SID}/summary`)
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
  })

  it('accepts a missing severity with no record yet, and an empty summary', async () => {
    for (const summary of [SUMMARY_NEEDS_SEVERITY, SUMMARY_EMPTY]) {
      const client = createRuntimeClient(BASE, mockFetch(json(summary)))
      await expect(client.getSummary(SID)).resolves.toEqual(summary)
    }
  })

  it('escapes the session id in the path', async () => {
    const fetchMock = mockFetch(json(SUMMARY_READY))
    await createRuntimeClient(BASE, fetchMock).getSummary('ses_../x')
    expect(lastCall(fetchMock).url).toBe(`${BASE}/checkin/sessions/ses_..%2Fx/summary`)
  })

  it('reports an unknown session (404)', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'unknown session' }, 404)))
    await expect(client.getSummary(SID)).rejects.toMatchObject({ kind: 'session-not-found', status: 404 })
  })

  it('rejects a summary without the share preview', async () => {
    const { share: _share, ...withoutShare } = SUMMARY_READY
    const client = createRuntimeClient(BASE, mockFetch(json(withoutShare)))
    await expect(client.getSummary(SID)).rejects.toMatchObject({ kind: 'bad-response' })
  })
})

describe('approve', () => {
  it('POSTs the chosen severities as JSON', async () => {
    const fetchMock = mockFetch(json(RECEIPT_SENT))
    const receipt = await createRuntimeClient(BASE, fetchMock).approve(SID, { SE_RASH: 'moderate' })
    expect(receipt).toEqual(RECEIPT_SENT)
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/sessions/${SID}/approve`)
    expect(init.method).toBe('POST')
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(String(init.body))).toEqual({ severities: { SE_RASH: 'moderate' } })
    expect(init.credentials).toBe('omit')
  })

  it('sends an empty severities object when none were needed', async () => {
    const fetchMock = mockFetch(json(RECEIPT_SENT))
    await createRuntimeClient(BASE, fetchMock).approve(SID, {})
    expect(JSON.parse(String(lastCall(fetchMock).init.body))).toEqual({ severities: {} })
  })

  it('accepts queued and failed receipts', async () => {
    for (const receipt of [RECEIPT_QUEUED, RECEIPT_FAILED]) {
      const client = createRuntimeClient(BASE, mockFetch(json(receipt)))
      await expect(client.approve(SID, {})).resolves.toEqual(receipt)
    }
  })

  it('reports which severities are still missing (409)', async () => {
    const body = { detail: { message: 'severity missing', needs_severity: ['SE_RASH', 'SE_COUGH'] } }
    const client = createRuntimeClient(BASE, mockFetch(json(body, 409)))
    const error = await client.approve(SID, {}).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(RuntimeError)
    expect(error).toMatchObject({ kind: 'needs-severity', status: 409, needsSeverity: ['SE_RASH', 'SE_COUGH'] })
  })

  it('treats any other 409 as already shared', async () => {
    for (const res of [json({ detail: 'this check-in was already shared' }, 409), new Response('oops', { status: 409 })]) {
      const client = createRuntimeClient(BASE, mockFetch(res))
      await expect(client.approve(SID, {})).rejects.toMatchObject({ kind: 'already-shared', status: 409 })
    }
  })

  it('reports a record refused by the contract check (422)', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'nothing was sent' }, 422)))
    await expect(client.approve(SID, {})).rejects.toMatchObject({ kind: 'record-refused', status: 422 })
  })

  it('reports an unknown session (404)', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'unknown session' }, 404)))
    await expect(client.approve(SID, {})).rejects.toMatchObject({ kind: 'session-not-found', status: 404 })
  })

  it('reports a runtime that is not running', async () => {
    const client = createRuntimeClient(BASE, mockFetch(() => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(client.approve(SID, {})).rejects.toMatchObject({ kind: 'runtime-down' })
  })

  it('rejects a receipt with an unknown status', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ ...RECEIPT_SENT, status: 'maybe' })))
    await expect(client.approve(SID, {})).rejects.toMatchObject({ kind: 'bad-response' })
  })
})

describe('voice commands in a turn (VC-07)', () => {
  const audio = () => new Blob(['a'], { type: 'audio/webm' })

  it.each([
    ['repeat', { action: 'repeat', ask: 1 }],
    ['slower', { action: 'slower', ask: 1 }],
  ] as const)('reads "%s" as a command, not an answer', async (command, next) => {
    const body = { transcript: 'say that again', symptoms: [], extraction: 'ok', rating: null, command, next }
    const result = await createRuntimeClient(BASE, mockFetch(json(body))).postTurn(SID, 'q1', 1, audio())
    expect(result.command).toBe(command)
    expect(result.next).toEqual({ action: command, ask: 1 })
    expect(result.rating).toBe('complete')
  })

  it('keeps the ask that was sent, whatever next.ask says', async () => {
    const body = { ...TURN, command: 'repeat', next: { action: 'repeat', ask: 2 } }
    const result = await createRuntimeClient(BASE, mockFetch(json(body))).postTurn(SID, 'q1', 0, audio())
    expect(result.next).toEqual({ action: 'repeat', ask: 0 })
  })

  it('reads a repeat/slower next with no command field as the command', async () => {
    const body = { ...TURN, next: { action: 'slower' } }
    const result = await createRuntimeClient(BASE, mockFetch(json(body))).postTurn(SID, 'q1', 1, audio())
    expect(result.command).toBe('slower')
    expect(result.next).toEqual({ action: 'slower', ask: 1 })
  })

  it.each([
    ['null', { command: null }],
    ['missing', {}],
    ['unknown', { command: 'dance' }],
  ])('reads a %s command as a normal answer', async (_name, extra) => {
    const result = await createRuntimeClient(BASE, mockFetch(json({ ...TURN, ...extra }))).postTurn(SID, 'q1', 0, audio())
    expect(result.command).toBeNull()
    expect(result.next).toEqual({ action: 'next', unanswered: false })
  })
})

describe('summary voice and correction fields (VC-08)', () => {
  it('reads spoken and correction_used', async () => {
    const summary = await createRuntimeClient(BASE, mockFetch(json(SUMMARY_READY))).getSummary(SID)
    expect(summary.spoken).toBe(SUMMARY_READY.spoken)
    expect(summary.correction_used).toBe(false)
  })

  it.each([
    ['missing', {}],
    ['null', { spoken: null, correction_used: null }],
    ['empty or wrong type', { spoken: '  ', correction_used: 'yes' }],
  ])('reads %s spoken/correction_used as null/false', async (_name, extra) => {
    const { spoken: _s, correction_used: _c, ...older } = SUMMARY_READY
    const summary = await createRuntimeClient(BASE, mockFetch(json({ ...older, ...extra }))).getSummary(SID)
    expect(summary.spoken).toBeNull()
    expect(summary.correction_used).toBe(false)
  })

  it('GETs the spoken summary audio, normal and slow', async () => {
    const fetchMock = mockFetch(() => Promise.resolve(new Response(new Blob(['wav']), { status: 200 })))
    const client = createRuntimeClient(BASE, fetchMock)
    expect((await client.getSummaryAudio(SID)).size).toBe(3)
    expect(lastCall(fetchMock).url).toBe(`${BASE}/checkin/sessions/${SID}/summary/audio?slow=false`)
    await client.getSummaryAudio(SID, true)
    expect(lastCall(fetchMock).url).toBe(`${BASE}/checkin/sessions/${SID}/summary/audio?slow=true`)
    expect(lastCall(fetchMock).init.method).toBe('GET')
  })

  it('reports summary audio that is not available (503)', async () => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'tts down' }, 503)))
    await expect(client.getSummaryAudio(SID)).rejects.toMatchObject({ kind: 'speech-unavailable' })
  })
})

describe('correct', () => {
  it.each([
    [{ term_code: 'SE_RASH', severity: 'mild' }],
    [{ term_code: 'SE_RASH', onset: 'today' }],
    [{ term_code: 'SE_RASH', remove: true }],
  ] as const)('POSTs a tapped change %j as JSON and returns the updated summary', async (change) => {
    const fetchMock = mockFetch(json(SUMMARY_CORRECTED))
    const summary = await createRuntimeClient(BASE, fetchMock).correct(SID, change)
    expect(summary).toEqual(SUMMARY_CORRECTED)
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/sessions/${SID}/correction`)
    expect(init.method).toBe('POST')
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(String(init.body))).toEqual(change)
  })

  it('POSTs the spoken change as the raw recording', async () => {
    const recording = new Blob([new Uint8Array(16)], { type: 'audio/webm;codecs=opus' })
    const fetchMock = mockFetch(json(SUMMARY_CORRECTED))
    await createRuntimeClient(BASE, fetchMock).correct(SID, recording)
    const { init } = lastCall(fetchMock)
    expect(new Headers(init.headers).get('Content-Type')).toBe('audio/webm;codecs=opus')
    expect(init.body).toBe(recording)
  })

  it('never sends an empty recording', async () => {
    const fetchMock = mockFetch(json(SUMMARY_CORRECTED))
    await expect(createRuntimeClient(BASE, fetchMock).correct(SID, new Blob([]))).rejects.toMatchObject({
      kind: 'empty-audio',
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    [422, { detail: { message: 'not understood', understood: false } }, 'correction-not-understood'],
    [409, { detail: 'correction already used' }, 'correction-used'],
    [404, { detail: 'unknown session' }, 'session-not-found'],
    [503, { detail: 'speech down' }, 'speech-unavailable'],
  ])('maps HTTP %i to its kind', async (status, body, kind) => {
    const client = createRuntimeClient(BASE, mockFetch(json(body, status)))
    await expect(client.correct(SID, { term_code: 'SE_RASH', remove: true })).rejects.toMatchObject({ kind, status })
  })
})

describe('receipts with alerts, and getReceipt (PV-07, AL-02)', () => {
  it('reads an alert', async () => {
    for (const alert of [ALERT_SENT, ALERT_QUEUED, { ...ALERT_SENT, status: 'failed' }]) {
      const client = createRuntimeClient(BASE, mockFetch(json({ ...RECEIPT_SENT, alert })))
      await expect(client.approve(SID, {})).resolves.toEqual({ ...RECEIPT_SENT, alert })
    }
  })

  it.each([
    ['missing', undefined],
    ['null', null],
    ['unreadable', { status: 'maybe', alert_id: 'alt_1' }],
    ['without an id', { status: 'sent' }],
  ])('reads a %s alert as null, keeping the receipt', async (_name, alert) => {
    const { alert: _a, ...older } = RECEIPT_SENT
    const body = alert === undefined ? older : { ...older, alert }
    const receipt = await createRuntimeClient(BASE, mockFetch(json(body))).approve(SID, {})
    expect(receipt).toEqual({ ...RECEIPT_SENT, alert: null })
  })

  it('reads an alert with no sent_at as not yet sent', () => {
    expect(readAlert({ status: 'queued', alert_id: 'alt_1' })).toEqual({ status: 'queued', alert_id: 'alt_1', sent_at: null })
  })

  it('GETs the current receipt', async () => {
    const fetchMock = mockFetch(json({ ...RECEIPT_QUEUED, alert: ALERT_QUEUED }))
    const receipt = await createRuntimeClient(BASE, fetchMock).getReceipt(SID)
    expect(receipt).toEqual({ ...RECEIPT_QUEUED, alert: ALERT_QUEUED })
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/sessions/${SID}/receipt`)
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
  })

  it('reports an unknown session, and rejects a body that is not a receipt', async () => {
    await expect(
      createRuntimeClient(BASE, mockFetch(json({ detail: 'x' }, 404))).getReceipt(SID),
    ).rejects.toMatchObject({ kind: 'session-not-found' })
    await expect(createRuntimeClient(BASE, mockFetch(json({ status: 'sent' }))).getReceipt(SID)).rejects.toMatchObject({
      kind: 'bad-response',
    })
  })
})
