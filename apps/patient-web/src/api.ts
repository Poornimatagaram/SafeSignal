// Client for the local patient runtime (apps/patient-runtime). This is the only module that makes requests,
// and it only ever calls the runtime base URL.
import { RUNTIME_URL } from './config.ts'

export interface Question {
  index: number
  total: number
  question_id: string
  purpose: string
  ask: number
  text: string
}

export interface NotedSymptom {
  term_code: string
  label: string
  severity: string | null
  onset?: string | null
}

export interface TurnResult {
  transcript: string
  /** null when the local model is down (`extraction` is then "unavailable"). */
  symptoms: NotedSymptom[] | null
  extraction: string
}

export type RuntimeErrorKind =
  | 'runtime-down' // fetch failed: the runtime is not running on this computer
  | 'empty-audio' // 400
  | 'forbidden' // 403
  | 'not-found' // 404
  | 'too-large' // 413
  | 'bad-format' // 415
  | 'not-understood' // 422
  | 'speech-unavailable' // 503
  | 'bad-response' // 200 with a body we cannot read
  | 'unknown'

export class RuntimeError extends Error {
  readonly kind: RuntimeErrorKind
  readonly status: number | undefined

  constructor(kind: RuntimeErrorKind, status?: number) {
    super(status === undefined ? `runtime error: ${kind}` : `runtime error: ${kind} (HTTP ${status})`)
    this.name = 'RuntimeError'
    this.kind = kind
    this.status = status
  }
}

export function errorKindForStatus(status: number): RuntimeErrorKind {
  switch (status) {
    case 400:
      return 'empty-audio'
    case 403:
      return 'forbidden'
    case 404:
      return 'not-found'
    case 413:
      return 'too-large'
    case 415:
      return 'bad-format'
    case 422:
      return 'not-understood'
    case 503:
      return 'speech-unavailable'
    default:
      return 'unknown'
  }
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>

export interface RuntimeClient {
  readonly baseUrl: string
  /** The question at `index`, or null when there are no more questions (HTTP 404). */
  getQuestion(index: number, ask?: number): Promise<Question | null>
  /** The question spoken by the runtime's local text-to-speech, as a WAV blob. */
  getQuestionAudio(index: number, ask?: number, slow?: boolean): Promise<Blob>
  /** Send one recorded answer; returns the on-device transcript and any noted symptoms. */
  postTurn(questionId: string, ask: number, audio: Blob): Promise<TurnResult>
}

// No cookies, no cache, no referrer: nothing about this screen is kept or passed on by the browser.
const BASE_INIT: RequestInit = { credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer' }

const defaultFetch: FetchLike = (input, init) => fetch(input, init)

export function createRuntimeClient(baseUrl: string = RUNTIME_URL, fetchImpl: FetchLike = defaultFetch): RuntimeClient {
  const base = baseUrl.replace(/\/+$/, '')

  async function send(path: string, init: RequestInit = {}): Promise<Response> {
    try {
      return await fetchImpl(`${base}${path}`, { ...BASE_INIT, ...init })
    } catch {
      throw new RuntimeError('runtime-down')
    }
  }

  async function readJson(res: Response): Promise<unknown> {
    try {
      return await res.json()
    } catch {
      throw new RuntimeError('bad-response', res.status)
    }
  }

  return {
    baseUrl: base,

    async getQuestion(index, ask = 0) {
      const query = new URLSearchParams({ index: String(index), ask: String(ask) })
      const res = await send(`/checkin/question?${query}`, { method: 'GET' })
      if (res.status === 404) return null
      if (!res.ok) throw new RuntimeError(errorKindForStatus(res.status), res.status)
      const body = await readJson(res)
      if (!isQuestion(body)) throw new RuntimeError('bad-response', res.status)
      return body
    },

    async getQuestionAudio(index, ask = 0, slow = false) {
      const query = new URLSearchParams({ index: String(index), ask: String(ask), slow: String(slow) })
      const res = await send(`/checkin/question/audio?${query}`, { method: 'GET' })
      if (!res.ok) throw new RuntimeError(errorKindForStatus(res.status), res.status)
      return res.blob()
    },

    async postTurn(questionId, ask, audio) {
      if (audio.size === 0) throw new RuntimeError('empty-audio')
      const query = new URLSearchParams({ question_id: questionId, ask: String(ask) })
      const res = await send(`/checkin/turn?${query}`, {
        method: 'POST',
        headers: { 'Content-Type': audio.type || 'application/octet-stream' },
        body: audio,
      })
      if (!res.ok) throw new RuntimeError(errorKindForStatus(res.status), res.status)
      const body = await readJson(res)
      if (!isTurnResult(body)) throw new RuntimeError('bad-response', res.status)
      return body
    },
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isQuestion(value: unknown): value is Question {
  return (
    isRecord(value) &&
    typeof value.index === 'number' &&
    typeof value.total === 'number' &&
    typeof value.question_id === 'string' &&
    typeof value.ask === 'number' &&
    typeof value.text === 'string'
  )
}

function isNotedSymptom(value: unknown): value is NotedSymptom {
  return (
    isRecord(value) &&
    typeof value.term_code === 'string' &&
    typeof value.label === 'string' &&
    (value.severity === null || value.severity === undefined || typeof value.severity === 'string')
  )
}

function isTurnResult(value: unknown): value is TurnResult {
  return (
    isRecord(value) &&
    typeof value.transcript === 'string' &&
    typeof value.extraction === 'string' &&
    (value.symptoms === null || (Array.isArray(value.symptoms) && value.symptoms.every(isNotedSymptom)))
  )
}
