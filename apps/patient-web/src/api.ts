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

export const TURN_RATINGS = ['complete', 'partial', 'off_topic', 'rambling', 'no_answer'] as const
/** How well the answer fit the question (VC-05). */
export type TurnRating = (typeof TURN_RATINGS)[number]

/** Most re-asks of one question: ask 1 = simpler wording, ask 2 = choices or yes/no. */
export const MAX_ASK = 2

/** What the runtime wants next (VC-05). */
export type TurnNext =
  /** Ask the SAME question again with `ask`, worded as `text`. */
  | { action: 'reask'; ask: number; text: string }
  /** Move on to the next question; `unanswered` when it was given up after the re-asks. */
  | { action: 'next'; unanswered: boolean }

export interface TurnResult {
  transcript: string
  /** null when the local model is down (`extraction` is then "unavailable"). */
  symptoms: NotedSymptom[] | null
  extraction: string
  /** Always set: a missing or null rating (older runtimes) reads as "complete". */
  rating: TurnRating
  /** Always set: a missing or unreadable `next` (older runtimes) reads as "move on". */
  next: TurnNext
}

/** One check-in, opened by "Start check-in". Every answer and the approval belong to it. */
export interface CheckinSession {
  session_id: string
  total: number
}

export const SEVERITIES = ['mild', 'moderate', 'severe'] as const
export type Severity = (typeof SEVERITIES)[number]

/** One coded symptom in the end-of-check-in summary. */
export interface SummaryItem {
  term_code: string
  label: string
  /** null until the patient says how bad it is (the code is then in `needs_severity`). */
  severity: string | null
  /** today | 1_3_days | 4_7_days | over_7_days | unknown */
  onset: string | null
  known_side_effect: boolean
}

/** What the egress gate would send, shown before the patient approves (PV-04). */
export interface SharePreview {
  destination: string
  method: string
  url: string
  /** Field names, format `symptoms[].term_code`. */
  fields: string[]
  /** The exact JSON that will be sent, or null while a severity is still missing. */
  record: Record<string, unknown> | null
}

export interface CheckinSummary {
  session_id: string
  shared: boolean
  items: SummaryItem[]
  /** Term codes whose severity the patient still has to choose before sharing. */
  needs_severity: string[]
  unanswered_questions: number
  text: string
  share: SharePreview
}

export type ReceiptStatus = 'sent' | 'queued' | 'failed'

/** The egress receipt (PV-05): what left this device, where, when, and its fingerprint. */
export interface EgressReceipt {
  /** sent; queued = no network, kept on this device and sent later; failed = the service refused it. */
  status: ReceiptStatus
  record_id: string
  destination: string
  method: string
  url: string
  fields_sent: string[]
  payload_sha256: string
  /** UTC ISO time; null while queued. */
  sent_at: string | null
  /** The service's HTTP status; null while queued. */
  response_code: number | null
}

export type RuntimeErrorKind =
  | 'runtime-down' // fetch failed: the runtime is not running on this computer
  | 'empty-audio' // 400
  | 'forbidden' // 403
  | 'not-found' // 404
  | 'session-not-found' // 404 on a session call: unknown check-in (for example the runtime restarted)
  | 'already-shared' // 409 on a turn: this check-in was already shared
  | 'needs-severity' // 409 on approve: a severity is still missing (see `needsSeverity`)
  | 'record-refused' // 422 on approve: the egress gate's contract check refused the record; nothing was sent
  | 'too-large' // 413
  | 'bad-format' // 415
  | 'not-understood' // 422
  | 'speech-unavailable' // 503
  | 'questions-missing' // 503 on start or a question: today's questions were never downloaded to this device
  | 'bad-response' // 2xx with a body we cannot read
  | 'unknown'

export class RuntimeError extends Error {
  readonly kind: RuntimeErrorKind
  readonly status: number | undefined
  /** For 'needs-severity': the term codes the runtime still needs a severity for. */
  readonly needsSeverity: readonly string[]

  constructor(kind: RuntimeErrorKind, status?: number, needsSeverity: readonly string[] = []) {
    super(status === undefined ? `runtime error: ${kind}` : `runtime error: ${kind} (HTTP ${status})`)
    this.name = 'RuntimeError'
    this.kind = kind
    this.status = status
    this.needsSeverity = needsSeverity
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
  /** Open today's check-in ("Start check-in"). 503 = today's questions were never downloaded. */
  startSession(): Promise<CheckinSession>
  /** Send one recorded answer; returns the on-device transcript and any noted symptoms. */
  postTurn(sessionId: string, questionId: string, ask: number, audio: Blob): Promise<TurnResult>
  /** The end-of-check-in summary and exactly what sharing would send. Sends nothing. */
  getSummary(sessionId: string): Promise<CheckinSummary>
  /**
   * The patient's approval: the runtime's egress gate sends the record and returns the receipt.
   * Call ONLY from the "Share this" tap (PV-04). Calling it again returns the same receipt; it never sends twice.
   */
  approve(sessionId: string, severities: Readonly<Record<string, Severity>>): Promise<EgressReceipt>
}

type StatusKinds = Partial<Record<number, RuntimeErrorKind>>

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

  /** The error for a non-2xx response; `kinds` overrides the general mapping for this call. */
  function failure(res: Response, kinds: StatusKinds = {}): RuntimeError {
    return new RuntimeError(kinds[res.status] ?? errorKindForStatus(res.status), res.status)
  }

  const sessionPath = (sessionId: string) => `/checkin/sessions/${encodeURIComponent(sessionId)}`

  return {
    baseUrl: base,

    async getQuestion(index, ask = 0) {
      const query = new URLSearchParams({ index: String(index), ask: String(ask) })
      const res = await send(`/checkin/question?${query}`, { method: 'GET' })
      if (res.status === 404) return null
      if (!res.ok) throw failure(res, { 503: 'questions-missing' })
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

    async startSession() {
      const res = await send('/checkin/sessions', { method: 'POST' })
      if (!res.ok) throw failure(res, { 503: 'questions-missing' })
      const body = await readJson(res)
      if (!isCheckinSession(body)) throw new RuntimeError('bad-response', res.status)
      return body
    },

    async postTurn(sessionId, questionId, ask, audio) {
      if (audio.size === 0) throw new RuntimeError('empty-audio')
      const query = new URLSearchParams({ session_id: sessionId, question_id: questionId, ask: String(ask) })
      const res = await send(`/checkin/turn?${query}`, {
        method: 'POST',
        headers: { 'Content-Type': audio.type || 'application/octet-stream' },
        body: audio,
      })
      if (!res.ok) throw failure(res, { 404: 'session-not-found', 409: 'already-shared' })
      const body = await readJson(res)
      if (!isTurnResult(body)) throw new RuntimeError('bad-response', res.status)
      return { ...body, rating: readRating(body.rating), next: readNext(body.next) }
    },

    async getSummary(sessionId) {
      const res = await send(`${sessionPath(sessionId)}/summary`, { method: 'GET' })
      if (!res.ok) throw failure(res, { 404: 'session-not-found' })
      const body = await readJson(res)
      if (!isCheckinSummary(body)) throw new RuntimeError('bad-response', res.status)
      return body
    },

    async approve(sessionId, severities) {
      const res = await send(`${sessionPath(sessionId)}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ severities }),
      })
      if (res.status === 409) {
        // {"detail": {"message": "...", "needs_severity": ["SE_RASH"]}}; any other 409 means already shared.
        const body: unknown = await res.json().catch(() => null)
        const detail = isRecord(body) && isRecord(body.detail) ? body.detail : null
        if (detail && isStringArray(detail.needs_severity)) {
          throw new RuntimeError('needs-severity', 409, detail.needs_severity)
        }
        throw new RuntimeError('already-shared', 409)
      }
      if (!res.ok) throw failure(res, { 404: 'session-not-found', 422: 'record-refused' })
      const body = await readJson(res)
      if (!isEgressReceipt(body)) throw new RuntimeError('bad-response', res.status)
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

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

const isNullableString = (value: unknown) => value === null || typeof value === 'string'

function isCheckinSession(value: unknown): value is CheckinSession {
  return isRecord(value) && typeof value.session_id === 'string' && value.session_id !== '' && typeof value.total === 'number'
}

function isSummaryItem(value: unknown): value is SummaryItem {
  return (
    isRecord(value) &&
    typeof value.term_code === 'string' &&
    typeof value.label === 'string' &&
    isNullableString(value.severity) &&
    (value.onset === undefined || isNullableString(value.onset))
  )
}

function isSharePreview(value: unknown): value is SharePreview {
  return (
    isRecord(value) &&
    typeof value.destination === 'string' &&
    typeof value.method === 'string' &&
    typeof value.url === 'string' &&
    isStringArray(value.fields) &&
    (value.record === null || isRecord(value.record))
  )
}

function isCheckinSummary(value: unknown): value is CheckinSummary {
  return (
    isRecord(value) &&
    typeof value.session_id === 'string' &&
    typeof value.shared === 'boolean' &&
    Array.isArray(value.items) &&
    value.items.every(isSummaryItem) &&
    isStringArray(value.needs_severity) &&
    typeof value.unanswered_questions === 'number' &&
    isSharePreview(value.share)
  )
}

function isEgressReceipt(value: unknown): value is EgressReceipt {
  return (
    isRecord(value) &&
    (value.status === 'sent' || value.status === 'queued' || value.status === 'failed') &&
    typeof value.record_id === 'string' &&
    typeof value.destination === 'string' &&
    typeof value.method === 'string' &&
    typeof value.url === 'string' &&
    isStringArray(value.fields_sent) &&
    typeof value.payload_sha256 === 'string' &&
    isNullableString(value.sent_at) &&
    (value.response_code === null || typeof value.response_code === 'number')
  )
}

/** A missing, null or unknown rating reads as "complete" (older runtimes send none). */
export function readRating(value: unknown): TurnRating {
  return TURN_RATINGS.find((rating) => rating === value) ?? 'complete'
}

/** A missing or unreadable `next` reads as "move on", so a turn is never lost over it. */
export function readNext(value: unknown): TurnNext {
  if (
    isRecord(value) &&
    value.action === 'reask' &&
    typeof value.ask === 'number' &&
    Number.isInteger(value.ask) &&
    typeof value.text === 'string' &&
    value.text.trim() !== ''
  ) {
    return { action: 'reask', ask: value.ask, text: value.text }
  }
  return { action: 'next', unanswered: isRecord(value) && value.action === 'next' && value.unanswered === true }
}

function isTurnResult(value: unknown): value is Omit<TurnResult, 'rating' | 'next'> & { rating?: unknown; next?: unknown } {
  return (
    isRecord(value) &&
    typeof value.transcript === 'string' &&
    typeof value.extraction === 'string' &&
    (value.symptoms === null || (Array.isArray(value.symptoms) && value.symptoms.every(isNotedSymptom)))
  )
}
