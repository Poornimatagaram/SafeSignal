// "What this computer sent" (PV-06): the runtime's network log in plain words, as a small state machine with no
// React in it. Reading the log sends nothing; it only GETs from the runtime on this computer.
import type { ConsentState, NetworkLogEntry, RuntimeClient } from './api.ts'

/** Who an organization is to the patient, from GET /consent (to name a sealed copy or a lock). */
export interface OrgContext {
  careOrgId: string | null
  emergencyOrgIds: readonly string[]
  /** org_id -> display name */
  names: Readonly<Record<string, string>>
}

export function orgContextFrom(consent: ConsentState): OrgContext {
  const names: Record<string, string> = {}
  for (const org of consent.options.organizations) names[org.org_id] = org.display_name
  return {
    careOrgId: consent.setup?.care_org_id ?? null,
    emergencyOrgIds: consent.setup?.emergency_org_ids ?? [],
    names,
  }
}

type OrgRole = 'care' | 'emergency' | 'unknown'

function orgRole(orgId: string | null, orgs: OrgContext | null): OrgRole {
  if (orgId === null || orgs === null) return 'unknown'
  if (orgId === orgs.careOrgId) return 'care'
  if (orgs.emergencyOrgIds.includes(orgId)) return 'emergency'
  return 'unknown'
}

/** " (Maple Clinic)" when the name is known, else "". */
function orgName(orgId: string | null, orgs: OrgContext | null): string {
  const name = orgId !== null ? orgs?.names[orgId] : undefined
  return name ? ` (${name})` : ''
}

/** The path of a URL ("/v1/survey"), or the text itself when it is not a full URL. */
function pathOf(url: string): string {
  try {
    return new URL(url).pathname
  } catch {
    return url.split('?')[0]
  }
}

const PUBLIC_KEY_PATH = /\/v1\/orgs\/([^/]+)\/public-key\/?$/

/** What the entry was, in plain words. */
export function entryWhat(entry: NetworkLogEntry, orgs: OrgContext | null): string {
  if (entry.kind === 'config_fetch') {
    const path = pathOf(entry.url)
    if (/\/v1\/survey\/?$/.test(path)) return "Today's questions downloaded"
    if (/\/v1\/terms\/?$/.test(path)) return 'Symptom word list downloaded'
    const key = PUBLIC_KEY_PATH.exec(path)
    if (key) {
      const orgId = entry.org_id ?? decodeURIComponent(key[1])
      const role = orgRole(orgId, orgs)
      const who = role === 'care' ? 'your care team' : role === 'emergency' ? 'an emergency hospital' : 'a hospital or clinic'
      return `Lock for ${who}${orgName(orgId, orgs)} fetched`
    }
    return 'Settings downloaded'
  }
  if (entry.kind === 'send') {
    switch (entry.destination) {
      case 'company_record':
        return 'Check-in sent to the drug company safety team (coded answers only, no name)'
      case 'care_envelope': {
        const role = orgRole(entry.org_id, orgs)
        const who =
          role === 'care'
            ? 'your care team'
            : role === 'emergency'
              ? 'an emergency hospital'
              : 'your care team or an emergency hospital'
        return `Sealed copy sent to ${who}${orgName(entry.org_id, orgs)}`
      }
      case 'alert':
        return 'Severe-problem alert sent'
      case 'consent':
        return 'Your sharing choices sent'
      default:
        return 'Something sent to the service (see the details)'
    }
  }
  return 'Something sent or fetched (see the details)'
}

export type EntryOutcome = 'accepted' | 'refused' | 'retry' | 'unknown'

export function entryOutcome(code: number | null): EntryOutcome {
  if (code === null) return 'unknown'
  if (code >= 200 && code < 300) return 'accepted'
  if (code >= 400 && code < 500) return 'refused'
  if (code >= 500 && code < 600) return 'retry'
  return 'unknown'
}

/** The service's answer, in plain words. */
export function entryStatus(code: number | null): string {
  switch (entryOutcome(code)) {
    case 'accepted':
      return 'Accepted'
    case 'refused':
      return 'Refused'
    case 'retry':
      return 'Service error, will try again'
    case 'unknown':
      return 'Answer not known'
  }
}

/** A stable key for a row (the log id, or its place in the list). */
export function entryKey(entry: NetworkLogEntry, index: number): string {
  return entry.log_id !== null ? `log-${entry.log_id}` : `row-${index}`
}

export const ONLY_THESE =
  'Only these went out. Nothing else leaves this computer: no recordings, no words you said.'
export const NOTHING_SENT = 'Nothing has been sent yet.'

export type NetworkLogPhase = 'loading' | 'load-failed' | 'ready'

export interface NetworkLogState {
  readonly phase: NetworkLogPhase
  readonly entries: readonly NetworkLogEntry[]
  /** Names of the care team and emergency hospitals; null when they could not be read (generic words then). */
  readonly orgs: OrgContext | null
  /** "Refresh" is on its way; the old list stays on screen. */
  readonly refreshing: boolean
  readonly failure: { readonly error: unknown } | null
  /** Rows whose details are shown (by entryKey). */
  readonly open: readonly string[]
}

export const INITIAL_NETWORK_LOG_STATE: NetworkLogState = {
  phase: 'loading',
  entries: [],
  orgs: null,
  refreshing: false,
  failure: null,
  open: [],
}

export interface NetworkLogFlow {
  getState(): NetworkLogState
  subscribe(listener: () => void): () => void
  /** GET the log (and the org names). Also "Refresh". Sends nothing. */
  load(): Promise<void>
  /** "Show details" / "Hide details" for one row. */
  toggleDetails(key: string): void
  dispose(): void
}

export function createNetworkLogFlow(client: RuntimeClient): NetworkLogFlow {
  let state: NetworkLogState = INITIAL_NETWORK_LOG_STATE
  const listeners = new Set<() => void>()
  let disposed = false
  let loadingNow = false

  const update = (patch: Partial<NetworkLogState>) => {
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
      if (disposed || loadingNow) return
      loadingNow = true
      if (state.phase === 'ready') update({ refreshing: true, failure: null })
      else update({ phase: 'loading', failure: null })
      try {
        // The names are a nicety: without them the rows use general words.
        const [entries, orgs] = await Promise.all([
          client.getNetworkLog(),
          client.getConsent().then(orgContextFrom, () => state.orgs),
        ])
        if (disposed) return
        update({ phase: 'ready', entries, orgs, refreshing: false })
      } catch (error) {
        if (disposed) return
        // A failed refresh keeps the list on screen, with the message.
        update({ phase: state.phase === 'ready' ? 'ready' : 'load-failed', refreshing: false, failure: { error } })
      } finally {
        loadingNow = false
      }
    },

    toggleDetails(key) {
      const open = state.open.includes(key) ? state.open.filter((k) => k !== key) : [...state.open, key]
      update({ open })
    },

    dispose() {
      disposed = true
      listeners.clear()
    },
  }
}
