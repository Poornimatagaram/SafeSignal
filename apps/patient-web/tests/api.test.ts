import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, RuntimeError, type FetchLike } from '../src/api.ts'
import { DEFAULT_RUNTIME_URL, resolveRuntimeUrl } from '../src/runtimeUrl.ts'
import {
  BASE,
  json,
  RECEIPT_FAILED,
  RECEIPT_QUEUED,
  RECEIPT_SENT,
  SID,
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
    expect(result).toEqual(TURN)
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
    await expect(client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' }))).resolves.toEqual(body)
  })

  it('accepts a symptom without severity', async () => {
    const body = { ...TURN, symptoms: [{ term_code: 'SE_RASH', label: 'Rash', severity: null, onset: null }] }
    const client = createRuntimeClient(BASE, mockFetch(json(body)))
    await expect(client.postTurn(SID, 'q1', 0, new Blob(['a'], { type: 'audio/webm' }))).resolves.toEqual(body)
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
