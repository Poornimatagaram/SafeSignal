import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, RuntimeError, type FetchLike } from '../src/api.ts'
import { DEFAULT_RUNTIME_URL, resolveRuntimeUrl } from '../src/runtimeUrl.ts'

const BASE = 'http://127.0.0.1:8001'

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

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
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
    const result = await createRuntimeClient(BASE, fetchMock).postTurn('q1', 0, recording)
    expect(result).toEqual(TURN)
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/turn?question_id=q1&ask=0`)
    expect(init.method).toBe('POST')
    expect(new Headers(init.headers).get('Content-Type')).toBe('audio/webm;codecs=opus')
    expect(init.body).toBe(recording)
    expect(init.credentials).toBe('omit')
  })

  it('sends Safari recordings as audio/mp4', async () => {
    const fetchMock = mockFetch(json(TURN))
    await createRuntimeClient(BASE, fetchMock).postTurn('q2', 1, new Blob(['a'], { type: 'audio/mp4' }))
    const { url, init } = lastCall(fetchMock)
    expect(url).toBe(`${BASE}/checkin/turn?question_id=q2&ask=1`)
    expect(new Headers(init.headers).get('Content-Type')).toBe('audio/mp4')
  })

  it('falls back to application/octet-stream for an untyped recording', async () => {
    const fetchMock = mockFetch(json(TURN))
    await createRuntimeClient(BASE, fetchMock).postTurn('q1', 0, new Blob(['a']))
    expect(new Headers(lastCall(fetchMock).init.headers).get('Content-Type')).toBe('application/octet-stream')
  })

  it('accepts symptoms: null when the local model is down', async () => {
    const body = { transcript: 'my nails are cracked', symptoms: null, extraction: 'unavailable' }
    const client = createRuntimeClient(BASE, mockFetch(json(body)))
    await expect(client.postTurn('q1', 0, new Blob(['a'], { type: 'audio/webm' }))).resolves.toEqual(body)
  })

  it('accepts a symptom without severity', async () => {
    const body = { ...TURN, symptoms: [{ term_code: 'SE_RASH', label: 'Rash', severity: null, onset: null }] }
    const client = createRuntimeClient(BASE, mockFetch(json(body)))
    await expect(client.postTurn('q1', 0, new Blob(['a'], { type: 'audio/webm' }))).resolves.toEqual(body)
  })

  it('never sends an empty recording', async () => {
    const fetchMock = mockFetch(json(TURN))
    await expect(createRuntimeClient(BASE, fetchMock).postTurn('q1', 0, new Blob([]))).rejects.toMatchObject({
      kind: 'empty-audio',
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    [400, 'empty-audio'],
    [403, 'forbidden'],
    [413, 'too-large'],
    [415, 'bad-format'],
    [422, 'not-understood'],
    [503, 'speech-unavailable'],
    [500, 'unknown'],
  ])('maps HTTP %i to %s', async (status, kind) => {
    const client = createRuntimeClient(BASE, mockFetch(json({ detail: 'x' }, status)))
    const error = await client.postTurn('q1', 0, new Blob(['a'], { type: 'audio/webm' })).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(RuntimeError)
    expect(error).toMatchObject({ kind, status })
  })

  it('reports a runtime that is not running', async () => {
    const client = createRuntimeClient(BASE, mockFetch(() => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(client.postTurn('q1', 0, new Blob(['a'], { type: 'audio/webm' }))).rejects.toMatchObject({
      kind: 'runtime-down',
    })
  })
})
