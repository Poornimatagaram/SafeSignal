// Approve-before-share (PV-04) and the egress receipt (PV-05), as a small state machine with no React in it.
//
// The rule this module exists for: NOTHING is sent until the patient taps "Share this". `share()` is that tap and
// is the only code in the app that calls `client.approve` (tests/approval.test.ts checks both). Loading the
// summary, choosing a severity, "Not now" and going back never send anything.
import { RuntimeError, type CheckinSummary, type EgressReceipt, type RuntimeClient, type Severity } from './api.ts'

export type SharePhase =
  | 'loading' // getting the summary
  | 'load-failed' // the summary could not be loaded; nothing was shared
  | 'review' // summary on screen, waiting for "Share this" or "Not now"
  | 'sending' // "Share this" was tapped; waiting for the receipt
  | 'receipt' // the receipt is on screen
  | 'not-shared' // "Not now" was tapped: nothing was shared

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
}

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
}

export function createShareFlow(client: RuntimeClient, sessionId: string): ShareFlow {
  let state: ShareState = INITIAL_SHARE_STATE
  const listeners = new Set<() => void>()

  const update = (patch: Partial<ShareState>) => {
    state = { ...state, ...patch }
    for (const listener of listeners) listener()
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
        update({ phase: 'review', summary, needs: [...summary.needs_severity], failure: null })
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
        update({ phase: 'receipt', receipt })
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
  }
}
