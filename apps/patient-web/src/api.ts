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

/** A spoken voice command instead of an answer (VC-07): "say that again" or "slower, please". */
export const VOICE_COMMANDS = ['repeat', 'slower'] as const
export type VoiceCommand = (typeof VOICE_COMMANDS)[number]

/** What the runtime wants next (VC-05, VC-07). */
export type TurnNext =
  /** Ask the SAME question again with `ask`, worded as `text`. */
  | { action: 'reask'; ask: number; text: string }
  /** Move on to the next question; `unanswered` when it was given up after the re-asks. */
  | { action: 'next'; unanswered: boolean }
  /** A voice command, not an answer: say the same wording again (slowly for "slower") and wait with the same `ask`. */
  | { action: VoiceCommand; ask: number }

export interface TurnResult {
  transcript: string
  /** null when the local model is down (`extraction` is then "unavailable"). */
  symptoms: NotedSymptom[] | null
  extraction: string
  /** Always set: a missing or null rating (older runtimes) reads as "complete". */
  rating: TurnRating
  /** Always set: a missing or unreadable `next` (older runtimes) reads as "move on". */
  next: TurnNext
  /** The voice command heard instead of an answer; null for a normal answer (and for older runtimes). */
  command: VoiceCommand | null
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
  /** The sealed record for the care team, or null when not sharing with the care team (also when missing). */
  care: CareShare | null
}

/** The sealed record for the patient's care team: only the care team can open it (CN-01). */
export interface CareShare {
  org_id: string
  /** Defaults to POST when the runtime does not say. */
  method: string
  url: string
  sealed: boolean
  /** The field names INSIDE the sealed record, format `symptoms[].term_code`. */
  fields: string[]
}

export interface CheckinSummary {
  session_id: string
  shared: boolean
  items: SummaryItem[]
  /** Term codes whose severity the patient still has to choose before sharing. */
  needs_severity: string[]
  unanswered_questions: number
  text: string
  /** What the runtime reads out loud ("Here is what I heard. ..."); null from older runtimes. */
  spoken: string | null
  /** True once the one correction before sharing was used (VC-08); a missing value reads as false. */
  correction_used: boolean
  share: SharePreview
}

/** Onset choices for a tapped correction, in the order they are offered. */
export const ONSETS = ['today', '1_3_days', '4_7_days', 'over_7_days', 'unknown'] as const
export type Onset = (typeof ONSETS)[number]

/** One tapped change to one summary item (VC-08). The spoken change is sent as a recording instead. */
export type CorrectionChange =
  | { term_code: string; severity: Severity }
  | { term_code: string; onset: Onset }
  | { term_code: string; remove: true }

/** A severe symptom told to the care team and caregiver (AL-02), within consent. Never carries symptom details. */
export interface ReceiptAlert {
  status: ReceiptStatus
  alert_id: string
  sent_at: string | null
}

export type ReceiptStatus = 'sent' | 'queued' | 'failed'

/** One outbound payload from the runtime's egress gate (the care envelope, a consent change). */
export interface OutboxReceipt {
  status: ReceiptStatus
  outbox_id: string
  destination: string
  method: string
  url: string
  fields_sent: string[]
  payload_sha256: string
  sent_at: string | null
  response_code: number | null
  /** The runtime's plain-words name for where it goes, when it gives one; else null. */
  label: string | null
}

export const WAITING_REASONS = ['no_key', 'offline', 'refused'] as const
/** no_key = the hospital has not set up its lock yet; offline = no connection; refused = the service said no. */
export type WaitingReason = (typeof WAITING_REASONS)[number]

/** The doctors' sealed record is still on this device. `reason` is null when the runtime gave none we know. */
export interface EnvelopeWaiting {
  status: 'waiting'
  reason: WaitingReason | null
}

/** The care envelope after approval: a receipt, waiting, or null (not sharing with the care team). */
export type EnvelopeState = OutboxReceipt | EnvelopeWaiting | null

/** Who the patient shares with (CN-01, CN-03), and the receipt of the last change. */
export interface ConsentState {
  share_care_team: boolean
  share_caregiver: boolean
  /** False: no care team is set up, so sharing with it cannot be turned on. */
  has_care_team: boolean
  /** False: no caregiver is set up, so sharing with them cannot be turned on. */
  has_caregiver: boolean
  /** The receipt of the change just sent (queued while offline), or null. */
  receipt: OutboxReceipt | null
}

export type ConsentKey = 'share_care_team' | 'share_caregiver'
/** A consent change: only the switches that changed. */
export type ConsentChange = Partial<Record<ConsentKey, boolean>>

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
  /** The severe-symptom alert, or null when there was none (also when missing or unreadable). */
  alert: ReceiptAlert | null
  /** The sealed record for the care team; null when not sharing with them (also when missing or unreadable). */
  envelope: EnvelopeState
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
  | 'correction-not-understood' // 422 on a spoken correction: not understood; the correction is NOT used up
  | 'correction-used' // 409 on a correction: the one correction was already used, or the check-in was shared
  | 'speech-unavailable' // 503
  | 'questions-missing' // 503 on start or a question: today's questions were never downloaded to this device
  | 'consent-unavailable' // 422 on a consent change: no care team or caregiver is set up to share with
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
  /** The summary read out loud by the runtime's local text-to-speech, as a WAV blob. */
  getSummaryAudio(sessionId: string, slow?: boolean): Promise<Blob>
  /**
   * The one correction before sharing (VC-08): a tapped change (JSON) or the recording of the patient saying it.
   * Returns the updated summary. 422 = spoken change not understood (not used up); 409 = already used or shared.
   */
  correct(sessionId: string, change: CorrectionChange | Blob): Promise<CheckinSummary>
  /** The current receipt of a shared check-in, so a queued record can be watched until it is sent. */
  getReceipt(sessionId: string): Promise<EgressReceipt>
  /** Who the patient shares with now. Sends nothing. */
  getConsent(): Promise<ConsentState>
  /**
   * Change who the patient shares with: only the changed switches are sent. It takes effect on this device at once,
   * even offline (the receipt is then "queued"). 422 = nobody is set up to share with.
   */
  setConsent(change: ConsentChange): Promise<ConsentState>
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
      const command = readCommand(body.command, body.next)
      // A command always replays the wording being asked now, whatever `next.ask` says.
      const next: TurnNext = command ? { action: command, ask } : readNext(body.next)
      return { ...body, rating: readRating(body.rating), next, command }
    },

    async getSummary(sessionId) {
      const res = await send(`${sessionPath(sessionId)}/summary`, { method: 'GET' })
      if (!res.ok) throw failure(res, { 404: 'session-not-found' })
      const body = await readJson(res)
      if (!isCheckinSummary(body)) throw new RuntimeError('bad-response', res.status)
      return readSummary(body)
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
      return readReceipt(body)
    },

    async getSummaryAudio(sessionId, slow = false) {
      const query = new URLSearchParams({ slow: String(slow) })
      const res = await send(`${sessionPath(sessionId)}/summary/audio?${query}`, { method: 'GET' })
      if (!res.ok) throw failure(res, { 404: 'session-not-found' })
      return res.blob()
    },

    async correct(sessionId, change) {
      let init: RequestInit
      if (change instanceof Blob) {
        if (change.size === 0) throw new RuntimeError('empty-audio')
        init = { method: 'POST', headers: { 'Content-Type': change.type || 'application/octet-stream' }, body: change }
      } else {
        init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change) }
      }
      const res = await send(`${sessionPath(sessionId)}/correction`, init)
      if (!res.ok) {
        // The runtime's 422 message is not shown: the screen has its own plain words, and it may echo what was said.
        throw failure(res, { 404: 'session-not-found', 409: 'correction-used', 422: 'correction-not-understood' })
      }
      const body = await readJson(res)
      if (!isCheckinSummary(body)) throw new RuntimeError('bad-response', res.status)
      return readSummary(body)
    },

    async getReceipt(sessionId) {
      const res = await send(`${sessionPath(sessionId)}/receipt`, { method: 'GET' })
      if (!res.ok) throw failure(res, { 404: 'session-not-found' })
      const body = await readJson(res)
      if (!isEgressReceipt(body)) throw new RuntimeError('bad-response', res.status)
      return readReceipt(body)
    },

    async getConsent() {
      const res = await send('/consent', { method: 'GET' })
      if (!res.ok) throw failure(res)
      return readConsent(await readJson(res), res.status)
    },

    async setConsent(change) {
      const body: ConsentChange = {}
      for (const key of CONSENT_KEYS) {
        const value = change[key]
        if (typeof value === 'boolean') body[key] = value
      }
      if (Object.keys(body).length === 0) throw new RuntimeError('not-understood')
      const res = await send('/consent', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw failure(res, { 422: 'consent-unavailable' })
      return readConsent(await readJson(res), res.status)
    },
  }
}

export const CONSENT_KEYS: readonly ConsentKey[] = ['share_care_team', 'share_caregiver']

function readConsent(body: unknown, status: number): ConsentState {
  if (
    !isRecord(body) ||
    typeof body.share_care_team !== 'boolean' ||
    typeof body.share_caregiver !== 'boolean' ||
    typeof body.has_care_team !== 'boolean' ||
    typeof body.has_caregiver !== 'boolean'
  ) {
    throw new RuntimeError('bad-response', status)
  }
  return {
    share_care_team: body.share_care_team,
    share_caregiver: body.share_caregiver,
    has_care_team: body.has_care_team,
    has_caregiver: body.has_caregiver,
    receipt: readOutboxReceipt(body.receipt),
  }
}

/** A missing or unreadable receipt reads as null. */
export function readOutboxReceipt(value: unknown): OutboxReceipt | null {
  if (
    isRecord(value) &&
    (value.status === 'sent' || value.status === 'queued' || value.status === 'failed') &&
    typeof value.destination === 'string' &&
    typeof value.method === 'string' &&
    typeof value.url === 'string' &&
    isStringArray(value.fields_sent) &&
    typeof value.payload_sha256 === 'string' &&
    (value.sent_at === undefined || isNullableString(value.sent_at)) &&
    (value.response_code === undefined || value.response_code === null || typeof value.response_code === 'number')
  ) {
    return {
      status: value.status,
      outbox_id: typeof value.outbox_id === 'string' ? value.outbox_id : '',
      destination: value.destination,
      method: value.method,
      url: value.url,
      fields_sent: value.fields_sent,
      payload_sha256: value.payload_sha256,
      sent_at: (value.sent_at as string | null | undefined) ?? null,
      response_code: (value.response_code as number | null | undefined) ?? null,
      label: typeof value.label === 'string' && value.label.trim() !== '' ? value.label : null,
    }
  }
  return null
}

/** The care envelope: a receipt, waiting (unknown reasons read as null), or null when missing or unreadable. */
export function readEnvelope(value: unknown): EnvelopeState {
  if (isRecord(value) && value.status === 'waiting') {
    return { status: 'waiting', reason: WAITING_REASONS.find((reason) => reason === value.reason) ?? null }
  }
  return readOutboxReceipt(value)
}

/** The sealed care-team preview, or null when not sharing with the care team (also when missing or unreadable). */
export function readCare(value: unknown): CareShare | null {
  if (isRecord(value) && typeof value.org_id === 'string' && typeof value.url === 'string' && isStringArray(value.fields)) {
    return {
      org_id: value.org_id,
      method: typeof value.method === 'string' ? value.method : 'POST',
      url: value.url,
      sealed: value.sealed !== false,
      fields: value.fields,
    }
  }
  return null
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

function isSharePreview(value: unknown): value is Omit<SharePreview, 'care'> & { care?: unknown } {
  return (
    isRecord(value) &&
    typeof value.destination === 'string' &&
    typeof value.method === 'string' &&
    typeof value.url === 'string' &&
    isStringArray(value.fields) &&
    (value.record === null || isRecord(value.record))
  )
}

type RawSummary = Omit<CheckinSummary, 'spoken' | 'correction_used' | 'share'> & {
  spoken?: unknown
  correction_used?: unknown
  share: Omit<SharePreview, 'care'> & { care?: unknown }
}

function isCheckinSummary(value: unknown): value is RawSummary {
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

/** `spoken` missing or not text reads as null; `correction_used` missing or not true reads as false. */
function readSummary(body: RawSummary): CheckinSummary {
  const spoken = typeof body.spoken === 'string' && body.spoken.trim() !== '' ? body.spoken : null
  return {
    ...body,
    spoken,
    correction_used: body.correction_used === true,
    share: { ...body.share, care: readCare(body.share.care) },
  }
}

type RawReceipt = Omit<EgressReceipt, 'alert' | 'envelope'> & { alert?: unknown; envelope?: unknown }

function isEgressReceipt(value: unknown): value is RawReceipt {
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

/** A missing, null or unreadable alert reads as null: the receipt itself is never lost over it. */
export function readAlert(value: unknown): ReceiptAlert | null {
  if (
    isRecord(value) &&
    (value.status === 'sent' || value.status === 'queued' || value.status === 'failed') &&
    typeof value.alert_id === 'string' &&
    (value.sent_at === undefined || isNullableString(value.sent_at))
  ) {
    return { status: value.status, alert_id: value.alert_id, sent_at: (value.sent_at as string | null | undefined) ?? null }
  }
  return null
}

function readReceipt(body: RawReceipt): EgressReceipt {
  return { ...body, alert: readAlert(body.alert), envelope: readEnvelope(body.envelope) }
}

/** The voice command in a turn: `command`, or a repeat/slower `next.action`; null for a normal answer. */
export function readCommand(command: unknown, next: unknown): VoiceCommand | null {
  const fromCommand = VOICE_COMMANDS.find((c) => c === command)
  if (fromCommand) return fromCommand
  return (isRecord(next) && VOICE_COMMANDS.find((c) => c === next.action)) || null
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

function isTurnResult(
  value: unknown,
): value is Omit<TurnResult, 'rating' | 'next' | 'command'> & { rating?: unknown; next?: unknown; command?: unknown } {
  return (
    isRecord(value) &&
    typeof value.transcript === 'string' &&
    typeof value.extraction === 'string' &&
    (value.symptoms === null || (Array.isArray(value.symptoms) && value.symptoms.every(isNotedSymptom)))
  )
}
