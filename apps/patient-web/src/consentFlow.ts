// "Who I share with" (CN-01, CN-03): the two consent switches, as a small state machine with no React in it.
//
// Opening the page GETs the switches. Each tap sends ONE change with only the switch that was tapped. The runtime
// saves it on this device at once, even offline; a queued change is watched until the runtime's retry sends it.
import {
  RuntimeError,
  type ConsentKey,
  type ConsentState,
  type OutboxReceipt,
  type RuntimeClient,
} from './api.ts'

export type ConsentPhase = 'loading' | 'load-failed' | 'ready'

export interface ConsentFlowState {
  readonly phase: ConsentPhase
  /** The switches as the runtime has them (after the last change). */
  readonly consent: ConsentState | null
  /** The switch whose change is on its way to the runtime. */
  readonly saving: ConsentKey | null
  /** The last change made on this page, and where it stands (its receipt). */
  readonly saved: { readonly key: ConsentKey; readonly receipt: OutboxReceipt | null } | null
  /** The last failure (loading, or a change that did not go through), for plain words. */
  readonly failure: { readonly error: unknown; readonly key: ConsentKey | null } | null
}

export interface ConsentFlowOptions {
  /** How often a queued change is checked again, in ms. */
  pollMs?: number
}

export const CONSENT_POLL_MS = 5000

export interface ConsentFlow {
  getState(): ConsentFlowState
  subscribe(listener: () => void): () => void
  /** GET the switches. Sends nothing. */
  load(): Promise<void>
  /** A tap on a switch: one PUT with only this switch, flipped. Ignored while saving or when it cannot be on. */
  toggle(key: ConsentKey): Promise<void>
  /** Leaving the page: stop watching a queued change. */
  dispose(): void
}

export const INITIAL_CONSENT_STATE: ConsentFlowState = {
  phase: 'loading',
  consent: null,
  saving: null,
  saved: null,
  failure: null,
}

/** Whether the person or team behind a switch is set up. */
export function hasRecipient(consent: ConsentState, key: ConsentKey): boolean {
  return key === 'share_care_team' ? consent.has_care_team : consent.has_caregiver
}

/** A switch can be tapped unless it is off with nobody set up to share with (turning one off is always allowed). */
export function canToggle(state: ConsentFlowState, key: ConsentKey): boolean {
  const consent = state.consent
  if (state.phase !== 'ready' || consent === null || state.saving !== null) return false
  return consent[key] || hasRecipient(consent, key)
}

export function createConsentFlow(client: RuntimeClient, options: ConsentFlowOptions = {}): ConsentFlow {
  const { pollMs = CONSENT_POLL_MS } = options
  let state: ConsentFlowState = INITIAL_CONSENT_STATE
  const listeners = new Set<() => void>()
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false
  let loadingNow = false
  let changes = 0 // bumps on every tap; a check started before a tap never overwrites what that tap got back

  const update = (patch: Partial<ConsentFlowState>) => {
    state = { ...state, ...patch }
    for (const listener of listeners) listener()
  }

  /** Check a queued change again every `pollMs` until it is sent or failed, or the page is left. */
  function watchQueued() {
    if (disposed || pollTimer !== null || state.saved?.receipt?.status !== 'queued') return
    pollTimer = setTimeout(async () => {
      const before = changes
      try {
        const consent = await client.getConsent()
        if (disposed) return
        // A new tap since this check started has its own receipt: keep it.
        if (before === changes && state.saving === null && state.saved) {
          update({ consent, saved: { ...state.saved, receipt: consent.receipt } })
        }
      } catch {
        // The runtime is busy or down: try again later. The change is already saved on this device.
      }
      pollTimer = null
      watchQueued()
    }, pollMs)
  }

  return {
    getState: () => state,

    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },

    async load() {
      if (state.phase === 'ready' || disposed || loadingNow) return
      loadingNow = true
      update({ phase: 'loading', failure: null })
      try {
        const consent = await client.getConsent()
        if (disposed) return
        update({ phase: 'ready', consent })
      } catch (error) {
        if (disposed) return
        update({ phase: 'load-failed', failure: { error, key: null } })
      } finally {
        loadingNow = false
      }
    },

    async toggle(key) {
      if (!canToggle(state, key) || state.consent === null) return
      const next = !state.consent[key]
      changes += 1
      update({ saving: key, failure: null })
      try {
        const consent = await client.setConsent({ [key]: next })
        if (disposed) return
        update({ consent, saving: null, saved: { key, receipt: consent.receipt } })
        watchQueued()
      } catch (error) {
        if (disposed) return
        // 422 on turning one on: nobody is set up to share with; mark it so the switch shows why it cannot be on.
        const consent =
          next && error instanceof RuntimeError && error.kind === 'consent-unavailable' && state.consent
            ? {
                ...state.consent,
                ...(key === 'share_care_team' ? { has_care_team: false } : { has_caregiver: false }),
              }
            : state.consent
        update({ consent, saving: null, failure: { error, key } })
      }
    },

    dispose() {
      disposed = true
      if (pollTimer !== null) clearTimeout(pollTimer)
      pollTimer = null
      listeners.clear()
    },
  }
}
