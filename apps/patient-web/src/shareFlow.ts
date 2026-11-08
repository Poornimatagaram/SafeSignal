// Approve-before-share (PV-04) and the egress receipt (PV-05), as a small state machine with no React in it.
//
// The rule this module exists for: NOTHING is sent until the patient taps "Share this". `share()` is that tap and
// is the only code in the app that calls `client.approve` (tests/approval.test.ts checks both). Loading the
// summary, choosing a severity, "Not now" and going back never send anything.
//
// Also here: the spoken summary (played when it appears, "Repeat", "Slower"), the one correction before
// sharing (VC-08), and watching a receipt saved while offline until the runtime's background retry sends it (PV-07).
import {
  receiptEnvelopes,
  RuntimeError,
  type CheckinSummary,
  type CorrectionChange,
  type EgressReceipt,
  type RuntimeClient,
  type Severity,
} from './api.ts'

export type SharePhase =
  | 'loading' // getting the summary
  | 'load-failed' // the summary could not be loaded; nothing was shared
  | 'review' // summary on screen, waiting for "Share this" or "Not now"
  | 'sending' // "Share this" was tapped; waiting for the receipt
  | 'receipt' // the receipt is on screen
  | 'not-shared' // "Not now" was tapped: nothing was shared

/** Where the patient is in "Change one answer": a menu, picking an item, changing it, or saying the change. */
export type CorrectionStep = 'closed' | 'menu' | 'pick' | 'item' | 'say'

export interface CorrectionState {
  readonly step: CorrectionStep
  /** The item being changed by tapping (step 'item'). */
  readonly termCode: string | null
  /** The change is on its way to the runtime. */
  readonly sending: boolean
  /** The last failed try (422 = not understood, try again; 409 = no longer possible), for plain words. */
  readonly failure: { readonly error: unknown } | null
}

export interface ShareState {
  readonly phase: SharePhase
  readonly summary: CheckinSummary | null
  /** Term codes the patient must give a severity for before sharing (the summary's list plus any a 409 names). */
  readonly needs: readonly string[]
  /** Severities the patient chose on this screen, by term code. */
  readonly chosen: Readonly<Record<string, Severity>>
  readonly receipt: EgressReceipt | null
  /** The last failure (loading the summary or sharing), for a plain-words message. */
  readonly failure: { readonly error: unknown } | null
  readonly correction: CorrectionState
  /** The summary could not be read out loud (it is still on screen). */
  readonly voiceFailure: { readonly error: unknown } | null
}

export interface ShareFlowOptions {
  /** Plays a WAV blob (the summary read out loud). Without it the summary is only shown. */
  play?: (audio: Blob) => Promise<void>
  /** Stops playback (before recording a spoken change, and when leaving the screen). */
  stop?: () => void
  /** How often a queued receipt is checked again, in ms. */
  pollMs?: number
}

export const RECEIPT_POLL_MS = 5000

export interface ShareFlow {
  getState(): ShareState
  subscribe(listener: () => void): () => void
  /** GET the summary. Never sends anything. */
  load(): Promise<void>
  chooseSeverity(termCode: string, severity: Severity): void
  /** The "Share this" tap: the only call to approve, and only once every needed severity is chosen. */
  share(): Promise<void>
  /** "Not now": ends without sharing. Makes no request. */
  notNow(): void
  /** From "Nothing was shared" back to the summary (a mistaken "Not now" tap). Makes no request. */
  backToSummary(): void
  /** Read the summary out loud ("Repeat"; `slow` for "Slower"). Also runs when a summary appears. */
  speakSummary(slow: boolean): Promise<void>
  /** Stop the summary voice (the patient is about to speak). */
  stopVoice(): void
  /** "Change one answer": open the menu (only while the one correction is still unused). */
  openCorrection(): void
  /** "Say the change" or "Tap to change". */
  chooseCorrectionMode(mode: 'say' | 'tap'): void
  /** Tap mode: the item to change. */
  pickItem(termCode: string): void
  /** Back out of "Change one answer" without changing anything. Makes no request. */
  closeCorrection(): void
  /** Send the one correction: a tapped change, or the recording of the patient saying it. */
  correct(change: CorrectionChange | Blob): Promise<void>
  /** Leaving the screen: stop watching a queued receipt and stop any playback. */
  dispose(): void
}

/** "Change one answer" is offered only on the unshared summary, while the one correction is unused. */
export function canCorrect(state: ShareState): boolean {
  return state.phase === 'review' && state.summary !== null && !state.summary.correction_used && !state.summary.shared
}

/**
 * True while the record, the severe-symptom alert or any sealed copy (care team, emergency hospitals) is still on
 * this computer and the runtime will send it later by itself. A sealed copy the service refused is not retried, so
 * it is not watched.
 */
export function isWaitingToSend(receipt: EgressReceipt | null): boolean {
  if (receipt === null) return false
  const copyWaiting = receiptEnvelopes(receipt).some((copy) =>
    copy.receipt ? copy.receipt.status === 'queued' : copy.waiting !== 'refused',
  )
  return receipt.status === 'queued' || receipt.alert?.status === 'queued' || copyWaiting
}

/** Term codes that still need a severity from the patient. */
export function missingSeverities(state: ShareState): string[] {
  return state.needs.filter((code) => !state.chosen[code])
}

/** "Share this" is enabled only on the summary, with every needed severity chosen. */
export function canShare(state: ShareState): boolean {
  return state.phase === 'review' && state.summary !== null && missingSeverities(state).length === 0
}

/** The approve body's severities: only for the items that needed one (`{}` otherwise). */
export function severitiesToSend(state: ShareState): Record<string, Severity> {
  const out: Record<string, Severity> = {}
  for (const code of state.needs) {
    const severity = state.chosen[code]
    if (severity) out[code] = severity
  }
  return out
}

export const INITIAL_SHARE_STATE: ShareState = {
  phase: 'loading',
  summary: null,
  needs: [],
  chosen: {},
  receipt: null,
  failure: null,
  correction: { step: 'closed', termCode: null, sending: false, failure: null },
  voiceFailure: null,
}

const CLOSED: CorrectionState = INITIAL_SHARE_STATE.correction

export function createShareFlow(client: RuntimeClient, sessionId: string, options: ShareFlowOptions = {}): ShareFlow {
  const { play, stop, pollMs = RECEIPT_POLL_MS } = options
  let state: ShareState = INITIAL_SHARE_STATE
  const listeners = new Set<() => void>()
  let summaryVersion = 0 // bumps when the summary changes; audio of an older summary is never played
  const audioCache = new Map<string, Blob>()
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  const update = (patch: Partial<ShareState>) => {
    state = { ...state, ...patch }
    for (const listener of listeners) listener()
  }

  const setCorrection = (patch: Partial<CorrectionState>) => update({ correction: { ...state.correction, ...patch } })

  /** A new summary on screen (loaded or corrected): severities still needed, choices kept where still needed. */
  const showSummary = (summary: CheckinSummary, patch: Partial<ShareState> = {}) => {
    summaryVersion += 1
    audioCache.clear()
    const needs = [...summary.needs_severity]
    const chosen: Record<string, Severity> = {}
    for (const code of needs) {
      const severity = state.chosen[code]
      if (severity) chosen[code] = severity
    }
    update({ phase: 'review', summary, needs, chosen, failure: null, voiceFailure: null, ...patch })
  }

  // Only on the summary page, and never over the patient saying a change.
  const mayPlay = (version: number) =>
    !disposed && version === summaryVersion && state.phase === 'review' && state.correction.step !== 'say'

  async function speakSummary(slow: boolean) {
    if (!play || !state.summary?.spoken || !mayPlay(summaryVersion)) return
    const version = summaryVersion
    const key = String(slow)
    try {
      let audio = audioCache.get(key)
      if (!audio) {
        audio = await client.getSummaryAudio(sessionId, slow)
        if (!mayPlay(version)) return
        audioCache.set(key, audio)
      }
      if (state.voiceFailure) update({ voiceFailure: null })
      await play(audio)
    } catch (error) {
      if (version === summaryVersion && !disposed) update({ voiceFailure: { error } })
    }
  }

  /** Check a queued receipt again every `pollMs` until it is sent or failed, or the screen is left. */
  function watchReceipt() {
    if (disposed || pollTimer !== null || !isWaitingToSend(state.receipt)) return
    pollTimer = setTimeout(async () => {
      try {
        const receipt = await client.getReceipt(sessionId)
        if (disposed) return
        update({ receipt })
      } catch (error) {
        // The runtime no longer knows this check-in: nothing more to wait for. Anything else: try again later.
        if (error instanceof RuntimeError && error.kind === 'session-not-found') {
          pollTimer = null
          return
        }
      }
      pollTimer = null
      watchReceipt()
    }, pollMs)
  }

  return {
    getState: () => state,

    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },

    async load() {
      if (state.phase !== 'loading' && state.phase !== 'load-failed') return
      update({ phase: 'loading', failure: null })
      try {
        const summary = await client.getSummary(sessionId)
        showSummary(summary)
        void speakSummary(false) // read out loud as soon as it appears
      } catch (error) {
        update({ phase: 'load-failed', failure: { error } })
      }
    },

    chooseSeverity(termCode, severity) {
      if (state.phase !== 'review' || !state.needs.includes(termCode)) return
      update({ chosen: { ...state.chosen, [termCode]: severity } })
    },

    async share() {
      // A second tap while sending, a tap before the summary or with a severity missing: never sends.
      if (!canShare(state)) return
      update({ phase: 'sending', failure: null })
      try {
        const receipt = await client.approve(sessionId, severitiesToSend(state))
        update({ phase: 'receipt', receipt, correction: CLOSED })
        stop?.()
        watchReceipt() // saved while offline: watch until the background retry sends it
      } catch (error) {
        const extra =
          error instanceof RuntimeError && error.kind === 'needs-severity'
            ? error.needsSeverity.filter((code) => !state.needs.includes(code))
            : []
        update({ phase: 'review', needs: [...state.needs, ...extra], failure: { error } })
      }
    },

    notNow() {
      if (state.phase !== 'review' && state.phase !== 'load-failed') return
      update({ phase: 'not-shared' })
    },

    backToSummary() {
      if (state.phase !== 'not-shared') return
      if (state.summary) update({ phase: 'review', failure: null })
      else update({ phase: 'load-failed' }) // keeps the load failure, so its message and "Try again" show
    },

    speakSummary,

    stopVoice() {
      stop?.()
    },

    openCorrection() {
      if (!canCorrect(state) || state.correction.step !== 'closed') return
      setCorrection({ step: 'menu', termCode: null, failure: null })
    },

    chooseCorrectionMode(mode) {
      if (!canCorrect(state) || state.correction.sending || state.correction.step === 'closed') return
      if (mode === 'say') stop?.() // never talk over the patient
      setCorrection({ step: mode === 'say' ? 'say' : 'pick', termCode: null, failure: null })
    },

    pickItem(termCode) {
      if (!canCorrect(state) || state.correction.sending) return
      if (!state.summary?.items.some((item) => item.term_code === termCode)) return
      setCorrection({ step: 'item', termCode, failure: null })
    },

    closeCorrection() {
      if (state.correction.sending) return
      update({ correction: CLOSED })
    },

    async correct(change) {
      if (!canCorrect(state) || state.correction.step === 'closed' || state.correction.sending) return
      setCorrection({ sending: true, failure: null })
      try {
        const summary = await client.correct(sessionId, change)
        if (disposed) return
        showSummary(summary, { correction: CLOSED })
        void speakSummary(false) // say the updated summary
      } catch (error) {
        if (disposed) return
        if (error instanceof RuntimeError && error.kind === 'correction-used') {
          // No longer possible (already used, or already shared): hide the option and show the runtime's summary.
          const summary = state.summary
          if (summary) update({ summary: { ...summary, correction_used: true } })
          update({ correction: { ...CLOSED, failure: { error } } })
          try {
            const fresh = await client.getSummary(sessionId)
            if (!disposed && state.phase === 'review') {
              // The runtime said no: the option stays hidden whatever this summary says.
              showSummary({ ...fresh, correction_used: true }, { correction: { ...CLOSED, failure: { error } } })
            }
          } catch {
            // Keep the summary on screen; the option stays hidden.
          }
          return
        }
        // Not understood (422) or another problem: the correction is not used up; try again or tap.
        setCorrection({ sending: false, failure: { error } })
      }
    },

    dispose() {
      disposed = true
      if (pollTimer !== null) clearTimeout(pollTimer)
      pollTimer = null
      stop?.()
      listeners.clear()
    },
  }
}
