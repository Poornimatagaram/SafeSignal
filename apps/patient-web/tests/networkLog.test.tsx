// "What this computer sent" (PV-06): parsing the runtime's network log, the plain words for each row, the empty
// state and the details toggle. Synthetic data only.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, readNetworkLogEntry, type ConsentState, type FetchLike, type NetworkLogEntry } from '../src/api.ts'
import { networkLogMessage } from '../src/messages.ts'
import {
  createNetworkLogFlow,
  entryKey,
  entryStatus,
  entryWhat,
  INITIAL_NETWORK_LOG_STATE,
  NOTHING_SENT,
  ONLY_THESE,
  orgContextFrom,
  type NetworkLogState,
} from '../src/networkLog.ts'
import { NetworkLogView } from '../src/NetworkLogScreen.tsx'
import { RuntimeError } from '../src/api.ts'
import { BASE, CONSENT_ON, json } from './fixtures.ts'

const SERVICE = 'http://127.0.0.1:8000'

const RECORD_SENT: NetworkLogEntry = {
  log_id: 7,
  kind: 'send',
  destination: 'company_record',
  org_id: null,
  method: 'POST',
  url: `${SERVICE}/v1/records`,
  fields_sent: ['patient_ref', 'symptoms[].term_code'],
  payload_sha256: '3f2a9c0b7d1e4f5a6b8c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c',
  response_code: 201,
  sent_at: '2026-11-08T14:03:12Z',
  outbox_id: 'rec_7f3c9a1e',
}

const SURVEY_FETCH: NetworkLogEntry = {
  log_id: 3,
  kind: 'config_fetch',
  destination: null,
  org_id: null,
  method: 'GET',
  url: `${SERVICE}/v1/survey?cohort_id=cohort_B`,
  fields_sent: ['cohort_id'],
  payload_sha256: '',
  response_code: 200,
  sent_at: '2026-11-08T08:00:00Z',
  outbox_id: null,
}

const CONSENT_WITH_ORGS: ConsentState = {
  ...CONSENT_ON,
  setup: {
    care_org_id: 'org_clinic_a',
    caregiver_id: null,
    caregiver_detail: 'alerts_only',
    emergency_consent: true,
    emergency_org_ids: ['org_hosp_b'],
    emergency_contacts: [],
  },
  options: {
    organizations: [
      { org_id: 'org_clinic_a', display_name: 'Maple Clinic', org_type: 'clinic' },
      { org_id: 'org_hosp_b', display_name: 'River Hospital', org_type: 'hospital' },
    ],
    caregivers: [],
  },
}
const ORGS = orgContextFrom(CONSENT_WITH_ORGS)

function fakeRuntime(routes: Record<string, () => Response | Promise<Response>>) {
  const calls: Array<{ method: string; path: string; search: string }> = []
  const fetchMock = vi.fn<FetchLike>(async (input, init) => {
    const url = new URL(input)
    const call = { method: init?.method ?? 'GET', path: url.pathname, search: url.search }
    calls.push(call)
    const route = routes[`${call.method} ${call.path}`]
    return route ? route() : json({ detail: 'not found' }, 404)
  })
  return { client: createRuntimeClient(BASE, fetchMock), calls }
}

function textOf(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
}

// ---------------------------------------------------------------------------------------------------------------
describe('network log API', () => {
  it('GETs /network-log?limit=200 and reads the entries in order', async () => {
    const { client, calls } = fakeRuntime({ 'GET /network-log': () => json({ entries: [RECORD_SENT, SURVEY_FETCH] }) })
    await expect(client.getNetworkLog()).resolves.toEqual([RECORD_SENT, SURVEY_FETCH])
    expect(calls).toEqual([{ method: 'GET', path: '/network-log', search: '?limit=200' }])
  })

  it('reads missing and unknown fields as plain defaults, and drops entries without a URL', () => {
    expect(readNetworkLogEntry({ url: `${SERVICE}/v1/new`, kind: 'teleport', response_code: '201', fields_sent: [1] })).toEqual({
      log_id: null,
      kind: 'other',
      destination: null,
      org_id: null,
      method: 'GET',
      url: `${SERVICE}/v1/new`,
      fields_sent: [],
      payload_sha256: '',
      response_code: null,
      sent_at: null,
      outbox_id: null,
    })
    expect(readNetworkLogEntry({ ...RECORD_SENT, destination: 'pigeon_post' })?.destination).toBe('pigeon_post')
    expect(readNetworkLogEntry({ kind: 'send' })).toBeNull()
    expect(readNetworkLogEntry('x')).toBeNull()
  })

  it('skips unreadable entries but rejects a body without a list', async () => {
    const ok = fakeRuntime({ 'GET /network-log': () => json({ entries: [null, RECORD_SENT, { url: '' }] }) })
    await expect(ok.client.getNetworkLog()).resolves.toEqual([RECORD_SENT])
    const bad = fakeRuntime({ 'GET /network-log': () => json({ rows: [] }) })
    await expect(bad.client.getNetworkLog()).rejects.toMatchObject({ kind: 'bad-response' })
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('plain words for each row', () => {
  const send = (destination: string | null, org_id: string | null = null): NetworkLogEntry => ({
    ...RECORD_SENT,
    destination,
    org_id,
  })
  const fetchOf = (path: string, org_id: string | null = null): NetworkLogEntry => ({
    ...SURVEY_FETCH,
    url: `${SERVICE}${path}`,
    org_id,
  })

  it('names each kind of send', () => {
    expect(entryWhat(send('company_record'), null)).toBe(
      'Check-in sent to the drug company safety team (coded answers only, no name)',
    )
    expect(entryWhat(send('alert'), null)).toBe('Severe-problem alert sent')
    expect(entryWhat(send('consent'), null)).toBe('Your sharing choices sent')
    expect(entryWhat(send('pigeon_post'), null)).toBe('Something sent to the service (see the details)')
    expect(entryWhat({ ...RECORD_SENT, kind: 'other' }, null)).toBe('Something sent or fetched (see the details)')
  })

  it('says whose sealed copy it was, with the name when known', () => {
    expect(entryWhat(send('care_envelope', 'org_clinic_a'), ORGS)).toBe('Sealed copy sent to your care team (Maple Clinic)')
    expect(entryWhat(send('care_envelope', 'org_hosp_b'), ORGS)).toBe(
      'Sealed copy sent to an emergency hospital (River Hospital)',
    )
    expect(entryWhat(send('care_envelope', 'org_hosp_b'), null)).toBe(
      'Sealed copy sent to your care team or an emergency hospital',
    )
  })

  it('names each download', () => {
    expect(entryWhat(SURVEY_FETCH, null)).toBe("Today's questions downloaded")
    expect(entryWhat(fetchOf('/v1/terms'), null)).toBe('Symptom word list downloaded')
    expect(entryWhat(fetchOf('/v1/orgs/org_clinic_a/public-key'), ORGS)).toBe(
      'Lock for your care team (Maple Clinic) fetched',
    )
    expect(entryWhat(fetchOf('/v1/orgs/org_hosp_b/public-key'), ORGS)).toBe(
      'Lock for an emergency hospital (River Hospital) fetched',
    )
    expect(entryWhat(fetchOf('/v1/orgs/org_zz/public-key'), null)).toBe('Lock for a hospital or clinic fetched')
    expect(entryWhat(fetchOf('/v1/other'), null)).toBe('Settings downloaded')
  })

  it("says the service's answer in words", () => {
    expect(entryStatus(200)).toBe('Accepted')
    expect(entryStatus(201)).toBe('Accepted')
    expect(entryStatus(409)).toBe('Refused')
    expect(entryStatus(503)).toBe('Service error, will try again')
    expect(entryStatus(null)).toBe('Answer not known')
    expect(entryStatus(302)).toBe('Answer not known')
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('the page', () => {
  const noop = () => undefined
  const render = (patch: Partial<NetworkLogState>) =>
    renderToStaticMarkup(
      <NetworkLogView state={{ ...INITIAL_NETWORK_LOG_STATE, ...patch }} onRefresh={noop} onToggle={noop} onBack={noop} />,
    )

  it('says only these went out, and shows the empty state', () => {
    const text = textOf(render({ phase: 'ready', entries: [] }))
    expect(text).toContain(ONLY_THESE)
    expect(text).toContain(NOTHING_SENT)
    expect(text).toContain('Refresh')
  })

  it('shows one row per entry with what, when and status; details hidden until asked', () => {
    const html = render({ phase: 'ready', entries: [RECORD_SENT, SURVEY_FETCH], orgs: ORGS })
    const text = textOf(html)
    expect(text).toContain('Check-in sent to the drug company safety team')
    expect(text).toContain("Today's questions downloaded")
    expect(text).toContain('Accepted')
    expect(html.match(/<li class="netlog__row">/g)).toHaveLength(2)
    expect(text.match(/Show details/g)).toHaveLength(2)
    expect(html).toContain('aria-expanded="false"')
    expect(text).not.toContain(RECORD_SENT.payload_sha256)
    expect(text).not.toContain('symptoms[].term_code')
  })

  it('shows method, URL, field names and fingerprint when a row is open', () => {
    const html = render({ phase: 'ready', entries: [RECORD_SENT, SURVEY_FETCH], open: [entryKey(RECORD_SENT, 0)] })
    const text = textOf(html)
    expect(html).toContain('aria-expanded="true"')
    expect(text).toContain('Hide details')
    expect(text).toContain(`POST ${SERVICE}/v1/records`)
    expect(text).toContain('symptoms[].term_code')
    expect(text).toContain(RECORD_SENT.payload_sha256)
    expect(text.match(/Show details/g)).toHaveLength(1) // the other row stays closed
  })

  it('shows a plain message when the list cannot be read', () => {
    const text = textOf(render({ phase: 'load-failed', failure: { error: new RuntimeError('runtime-down') } }))
    expect(text).toContain('not running')
    expect(text).toContain('Try again')
    expect(networkLogMessage(new Error('x'))).toBe('I could not show what this computer sent. Please try again.')
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('the flow', () => {
  it('loads the log and the names with GETs only; works without the names', async () => {
    const { client, calls } = fakeRuntime({
      'GET /network-log': () => json({ entries: [RECORD_SENT] }),
      'GET /consent': () => json({ detail: 'down' }, 500),
    })
    const flow = createNetworkLogFlow(client)
    await flow.load()
    expect(flow.getState()).toMatchObject({ phase: 'ready', entries: [RECORD_SENT], orgs: null })
    expect(calls.every((c) => c.method === 'GET')).toBe(true)
  })

  it('toggles details per row, and a failed refresh keeps the list', async () => {
    let fail = false
    const { client } = fakeRuntime({
      'GET /network-log': () => (fail ? json({}, 500) : json({ entries: [RECORD_SENT] })),
      'GET /consent': () => json(CONSENT_WITH_ORGS),
    })
    const flow = createNetworkLogFlow(client)
    await flow.load()
    expect(flow.getState().orgs).toEqual(ORGS)
    flow.toggleDetails('log-7')
    expect(flow.getState().open).toEqual(['log-7'])
    flow.toggleDetails('log-7')
    expect(flow.getState().open).toEqual([])
    fail = true
    await flow.load()
    expect(flow.getState()).toMatchObject({ phase: 'ready', entries: [RECORD_SENT], refreshing: false })
    expect(flow.getState().failure).not.toBeNull()
  })
})
