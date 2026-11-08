// "Who I share with" (CN-01, CN-03) and the care team's sealed record (care envelope): the API calls, the switches,
// the summary's care section, the envelope receipt and watching it while it waits. Synthetic data only.
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createRuntimeClient,
  readCare,
  readEnvelope,
  RuntimeError,
  type ConsentState,
  type EgressReceipt,
  type FetchLike,
} from '../src/api.ts'
import { canToggle, createConsentFlow, INITIAL_CONSENT_STATE, type ConsentFlowState } from '../src/consentFlow.ts'
import { ConsentView, consentReceiptText } from '../src/ConsentScreen.tsx'
import { consentChangeMessage } from '../src/messages.ts'
import { createShareFlow, INITIAL_SHARE_STATE, isWaitingToSend, type ShareState } from '../src/shareFlow.ts'
import { ShareView } from '../src/ShareScreen.tsx'
import { careTeamPartsText, envelopeText } from '../src/summaryText.ts'
import {
  BASE,
  CARE,
  CARE_FIELDS,
  CONSENT_ON,
  CONSENT_RECEIPT_QUEUED,
  CONSENT_RECEIPT_SENT,
  ENVELOPE_NO_KEY,
  ENVELOPE_OFFLINE,
  ENVELOPE_QUEUED,
  ENVELOPE_REFUSED,
  ENVELOPE_SENT,
  json,
  RECEIPT_QUEUED,
  RECEIPT_SENT,
  SID,
  SUMMARY_READY,
  SUMMARY_WITH_CARE,
} from './fixtures.ts'

interface Call {
  method: string
  path: string
  body: unknown
  contentType: string | null
}

type Handler = () => Response | Promise<Response>

/** A fake runtime that records every request; a list of handlers answers in order, then repeats the last one. */
function fakeRuntime(routes: Record<string, Handler | Handler[]>) {
  const calls: Call[] = []
  const queues = new Map(Object.entries(routes).map(([k, v]) => [k, Array.isArray(v) ? [...v] : v]))
  const fetchMock = vi.fn<FetchLike>(async (input, init) => {
    const url = new URL(input)
    const call: Call = {
      method: init?.method ?? 'GET',
      path: url.pathname,
      body: init?.body,
      contentType: new Headers(init?.headers).get('Content-Type'),
    }
    calls.push(call)
    const route = queues.get(`${call.method} ${call.path}`)
    if (!route) return json({ detail: 'not found' }, 404)
    const handler = Array.isArray(route) ? (route.length > 1 ? route.shift() : route[0]) : route
    return handler ? handler() : json({ detail: 'not found' }, 404)
  })
  const of = (method: string, path: string) => calls.filter((c) => c.method === method && c.path === path)
  return { client: createRuntimeClient(BASE, fetchMock), calls, of, fetchMock }
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

/** The visible text of rendered HTML. */
function textOf(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
}

/** Every opening tag with role="switch". */
function switchTags(html: string): string[] {
  return [...html.matchAll(/<button[^>]*role="switch"[^>]*>/g)].map((m) => m[0])
}

// ---------------------------------------------------------------------------------------------------------------
describe('consent API', () => {
  it('GETs /consent and reads the switches and the receipt', async () => {
    const { client, calls } = fakeRuntime({ 'GET /consent': () => json({ ...CONSENT_ON, receipt: CONSENT_RECEIPT_SENT }) })
    await expect(client.getConsent()).resolves.toEqual({ ...CONSENT_ON, receipt: CONSENT_RECEIPT_SENT })
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/consent' })
  })

  it('reads a missing or unreadable receipt as null', async () => {
    const { client } = fakeRuntime({
      'GET /consent': [
        () => json({ ...CONSENT_ON, receipt: undefined }),
        () => json({ ...CONSENT_ON, receipt: { status: 'lost' } }),
      ],
    })
    expect((await client.getConsent()).receipt).toBeNull()
    expect((await client.getConsent()).receipt).toBeNull()
  })

  it('keeps an older receipt without a label or outbox_id', async () => {
    const { label: _label, outbox_id: _id, ...bare } = CONSENT_RECEIPT_SENT
    const { client } = fakeRuntime({ 'GET /consent': () => json({ ...CONSENT_ON, receipt: bare }) })
    expect((await client.getConsent()).receipt).toEqual({ ...CONSENT_RECEIPT_SENT, outbox_id: '', label: null })
  })

  it('rejects a body without the four switches', async () => {
    const { client } = fakeRuntime({ 'GET /consent': () => json({ share_care_team: true }) })
    await expect(client.getConsent()).rejects.toMatchObject({ kind: 'bad-response' })
  })

  it('PUTs only the changed switch, as JSON', async () => {
    const off: ConsentState = { ...CONSENT_ON, share_caregiver: false, receipt: CONSENT_RECEIPT_QUEUED }
    const { client, calls } = fakeRuntime({ 'PUT /consent': () => json(off) })
    await expect(client.setConsent({ share_caregiver: false })).resolves.toEqual(off)
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/consent', contentType: 'application/json' })
    expect(JSON.parse(String(calls[0].body))).toEqual({ share_caregiver: false })
  })

  it('never sends an empty change, and drops keys that are not switches', async () => {
    const { client, calls } = fakeRuntime({ 'PUT /consent': () => json(CONSENT_ON) })
    await expect(client.setConsent({})).rejects.toBeInstanceOf(RuntimeError)
    expect(calls).toHaveLength(0)
    await client.setConsent({ share_care_team: true, other: true } as never)
    expect(JSON.parse(String(calls[0].body))).toEqual({ share_care_team: true })
  })

  it('maps 422 (nobody set up) to consent-unavailable, and a dead runtime to runtime-down', async () => {
    const { client } = fakeRuntime({ 'PUT /consent': () => json({ detail: 'no care team' }, 422) })
    await expect(client.setConsent({ share_care_team: true })).rejects.toMatchObject({ kind: 'consent-unavailable' })
    const down = createRuntimeClient(BASE, async () => {
      throw new TypeError('Failed to fetch')
    })
    await expect(down.getConsent()).rejects.toMatchObject({ kind: 'runtime-down' })
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('care envelope parsing', () => {
  it('reads share.care on the summary; missing or unreadable reads as null', async () => {
    const { client } = fakeRuntime({
      [`GET /checkin/sessions/${SID}/summary`]: [
        () => json(SUMMARY_WITH_CARE),
        () => json({ ...SUMMARY_READY, share: { ...SUMMARY_READY.share, care: undefined } }),
        () => json({ ...SUMMARY_READY, share: { ...SUMMARY_READY.share, care: { org_id: 'org_x' } } }),
      ],
    })
    expect((await client.getSummary(SID)).share.care).toEqual(CARE)
    expect((await client.getSummary(SID)).share.care).toBeNull()
    expect((await client.getSummary(SID)).share.care).toBeNull()
  })

  it('defaults the method to POST and keeps the runtime destination out of the type', () => {
    const { method: _m, ...noMethod } = CARE
    expect(readCare({ ...noMethod, destination: 'Your care team' })).toEqual(CARE)
  })

  it('reads the envelope on approve and on the receipt', async () => {
    const { client } = fakeRuntime({
      [`POST /checkin/sessions/${SID}/approve`]: () => json({ ...RECEIPT_SENT, envelope: ENVELOPE_SENT }),
      [`GET /checkin/sessions/${SID}/receipt`]: () => json({ ...RECEIPT_SENT, envelope: ENVELOPE_NO_KEY }),
    })
    expect((await client.approve(SID, {})).envelope).toEqual(ENVELOPE_SENT)
    expect((await client.getReceipt(SID)).envelope).toEqual(ENVELOPE_NO_KEY)
  })

  it('reads waiting reasons, unknown reasons as null, and anything else as null', () => {
    expect(readEnvelope(ENVELOPE_OFFLINE)).toEqual(ENVELOPE_OFFLINE)
    expect(readEnvelope(ENVELOPE_REFUSED)).toEqual(ENVELOPE_REFUSED)
    expect(readEnvelope({ status: 'waiting', reason: 'later' })).toEqual({ status: 'waiting', reason: null })
    expect(readEnvelope(ENVELOPE_QUEUED)).toEqual(ENVELOPE_QUEUED)
    expect(readEnvelope(undefined)).toBeNull()
    expect(readEnvelope(null)).toBeNull()
    expect(readEnvelope({ status: 'sent' })).toBeNull()
  })

  it('keeps the receipt when the envelope is missing (older runtimes)', async () => {
    const { envelope: _e, ...old } = RECEIPT_SENT
    const { client } = fakeRuntime({ [`GET /checkin/sessions/${SID}/receipt`]: () => json(old) })
    expect(await client.getReceipt(SID)).toEqual(RECEIPT_SENT)
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('consent switches (flow)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads with one GET and sends nothing else', async () => {
    const runtime = fakeRuntime({ 'GET /consent': () => json(CONSENT_ON) })
    const flow = createConsentFlow(runtime.client)
    await Promise.all([flow.load(), flow.load()])
    await settle()
    expect(flow.getState()).toMatchObject({ phase: 'ready', consent: CONSENT_ON })
    expect(runtime.calls.map((c) => `${c.method} ${c.path}`)).toEqual(['GET /consent'])
  })

  it('a tap sends one PUT with only the tapped switch, flipped, and shows where it stands', async () => {
    const after: ConsentState = { ...CONSENT_ON, share_care_team: false, receipt: CONSENT_RECEIPT_SENT }
    const runtime = fakeRuntime({ 'GET /consent': () => json(CONSENT_ON), 'PUT /consent': () => json(after) })
    const flow = createConsentFlow(runtime.client)
    await flow.load()
    await Promise.all([flow.toggle('share_care_team'), flow.toggle('share_care_team')]) // a double tap
    const puts = runtime.of('PUT', '/consent')
    expect(puts).toHaveLength(1)
    expect(JSON.parse(String(puts[0].body))).toEqual({ share_care_team: false })
    expect(flow.getState()).toMatchObject({
      consent: after,
      saving: null,
      saved: { key: 'share_care_team', receipt: CONSENT_RECEIPT_SENT },
    })
  })

  it('cannot turn on a switch with nobody set up (no request), but can always turn one off', async () => {
    const none: ConsentState = { ...CONSENT_ON, share_care_team: false, has_care_team: false }
    const runtime = fakeRuntime({ 'GET /consent': () => json(none), 'PUT /consent': () => json(none) })
    const flow = createConsentFlow(runtime.client)
    await flow.load()
    expect(canToggle(flow.getState(), 'share_care_team')).toBe(false)
    await flow.toggle('share_care_team')
    expect(runtime.of('PUT', '/consent')).toHaveLength(0)

    const onButNobody: ConsentFlowState = {
      ...INITIAL_CONSENT_STATE,
      phase: 'ready',
      consent: { ...CONSENT_ON, has_caregiver: false },
    }
    expect(canToggle(onButNobody, 'share_caregiver')).toBe(true)
  })

  it('a 422 when turning one on marks that nobody is set up, with a plain reason', async () => {
    const off: ConsentState = { ...CONSENT_ON, share_caregiver: false }
    const runtime = fakeRuntime({
      'GET /consent': () => json(off),
      'PUT /consent': () => json({ detail: 'no caregiver' }, 422),
    })
    const flow = createConsentFlow(runtime.client)
    await flow.load()
    await flow.toggle('share_caregiver')
    const state = flow.getState()
    expect(state.consent).toMatchObject({ share_caregiver: false, has_caregiver: false })
    expect(state.failure?.key).toBe('share_caregiver')
    expect(consentChangeMessage(state.failure?.error)).toMatch(/nobody is set up/)
  })

  it('watches a queued change with GET /consent until it is sent, then stops', async () => {
    vi.useFakeTimers()
    const queued: ConsentState = { ...CONSENT_ON, share_care_team: false, receipt: CONSENT_RECEIPT_QUEUED }
    const sent: ConsentState = { ...queued, receipt: CONSENT_RECEIPT_SENT }
    const runtime = fakeRuntime({
      'GET /consent': [() => json(CONSENT_ON), () => json(queued), () => json(sent)],
      'PUT /consent': () => json(queued),
    })
    const flow = createConsentFlow(runtime.client, { pollMs: 5000 })
    await flow.load()
    await flow.toggle('share_care_team')
    expect(flow.getState().saved?.receipt?.status).toBe('queued')
    const gets = () => runtime.of('GET', '/consent').length
    await vi.advanceTimersByTimeAsync(5000)
    expect(gets()).toBe(2)
    expect(flow.getState().saved?.receipt?.status).toBe('queued')
    await vi.advanceTimersByTimeAsync(5000)
    expect(gets()).toBe(3)
    expect(flow.getState().saved?.receipt?.status).toBe('sent')
    await vi.advanceTimersByTimeAsync(30000)
    expect(gets()).toBe(3)
    expect(runtime.of('PUT', '/consent')).toHaveLength(1) // watching never sends the change again
  })

  it('stops watching when the page is left', async () => {
    vi.useFakeTimers()
    const queued: ConsentState = { ...CONSENT_ON, share_care_team: false, receipt: CONSENT_RECEIPT_QUEUED }
    const runtime = fakeRuntime({ 'GET /consent': () => json(queued), 'PUT /consent': () => json(queued) })
    const flow = createConsentFlow(runtime.client)
    await flow.load()
    await flow.toggle('share_care_team')
    flow.dispose()
    await vi.advanceTimersByTimeAsync(30000)
    expect(runtime.of('GET', '/consent')).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('consent switches (screen)', () => {
  const noop = () => undefined
  const render = (patch: Partial<ConsentFlowState>) =>
    renderToStaticMarkup(
      <ConsentView state={{ ...INITIAL_CONSENT_STATE, ...patch }} onToggle={noop} onRetry={noop} onBack={noop} />,
    )
  const ready = (consent: ConsentState, extra: Partial<ConsentFlowState> = {}) =>
    render({ phase: 'ready', consent, ...extra })

  it('shows two real switches with aria-checked and On/Off in words', () => {
    const html = ready({ ...CONSENT_ON, share_caregiver: false })
    const tags = switchTags(html)
    expect(tags).toHaveLength(2)
    expect(tags[0]).toContain('aria-checked="true"')
    expect(tags[0]).toContain('aria-disabled="false"')
    expect(tags[1]).toContain('aria-checked="false"')
    const text = textOf(html)
    expect(text).toContain('Share with my doctor On')
    expect(text).toContain('Share with my caregiver Off')
    expect(text).toContain("Your doctor's team gets your check-ins, sealed so only they can read them.")
    expect(text).toContain('Your caregiver gets nothing new from now on.')
  })

  it('says where a change stands: sent, queued, failed', () => {
    const saved = (receipt: typeof CONSENT_RECEIPT_SENT) =>
      textOf(ready(CONSENT_ON, { saved: { key: 'share_care_team', receipt } }))
    expect(saved(CONSENT_RECEIPT_SENT)).toContain('Saved and sent.')
    expect(saved(CONSENT_RECEIPT_QUEUED)).toContain("Saved on this device. It will be sent when you're back online.")
    expect(consentReceiptText({ ...CONSENT_RECEIPT_SENT, status: 'failed' })).toMatch(/did not accept/)
    expect(consentReceiptText(null)).toBe('Saved on this device.')
  })

  it('disables a switch with nobody set up, and says why in plain words', () => {
    const html = ready({ ...CONSENT_ON, share_care_team: false, has_care_team: false })
    expect(switchTags(html)[0]).toContain('aria-disabled="true"')
    expect(textOf(html)).toContain('No doctor is set up on this computer yet, so this cannot be turned on.')
  })

  it('shows loading, and a failure with Try again', () => {
    expect(textOf(render({ phase: 'loading' }))).toContain('Getting your choices')
    const failed = textOf(render({ phase: 'load-failed', failure: { error: new RuntimeError('runtime-down'), key: null } }))
    expect(failed).toContain('Try again')
    expect(failed).toContain('not running')
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('summary: what the care team gets', () => {
  const render = (patch: Partial<ShareState>) => {
    const noop = () => undefined
    return textOf(
      renderToStaticMarkup(
        <ShareView
          state={{ ...INITIAL_SHARE_STATE, ...patch }}
          onChoose={noop}
          onShare={noop}
          onNotNow={noop}
          onBack={noop}
          onRetryLoad={noop}
          onRestart={noop}
        />,
      ),
    )
  }

  it('lists what is inside the sealed copy in plain words', () => {
    const text = render({ phase: 'review', summary: SUMMARY_WITH_CARE })
    expect(text).toContain('Sent to your care team, sealed: only your doctors can read it.')
    for (const part of ['Your name', 'The date of this check-in', 'Your medicine', 'How you are doing compared with before']) {
      expect(text).toContain(part)
    }
    expect(text).not.toContain('display_name') // field names only behind "Show exactly what is sent"
  })

  it('says plainly that the doctor gets nothing when sharing is off', () => {
    const text = render({ phase: 'review', summary: SUMMARY_READY })
    expect(text).toContain('Your doctor gets nothing from this check-in: sharing with your doctor is off.')
    expect(text).not.toContain('sealed: only your doctors')
  })

  it('explains every care field, and flags unknown ones', () => {
    expect(careTeamPartsText(CARE_FIELDS)).not.toContain('Other details (see the exact list)')
    expect(careTeamPartsText([...CARE_FIELDS, 'new_thing'])).toContain('Other details (see the exact list)')
  })

  it('shows the sealed copy on the receipt: sent with time and fingerprint, waiting in plain words, null as nothing', () => {
    const receipt = (envelope: EgressReceipt['envelope']) =>
      render({ phase: 'receipt', receipt: { ...RECEIPT_SENT, envelope } })

    const sent = receipt(ENVELOPE_SENT)
    expect(sent).toContain("Your doctor's sealed copy")
    expect(sent).toContain('Your care team (sealed: only your doctors can read it)')
    expect(sent).toContain(ENVELOPE_SENT.payload_sha256)

    expect(receipt(ENVELOPE_NO_KEY)).toContain('their hospital has not set up its lock yet. It will be sent later by itself.')
    expect(receipt(ENVELOPE_OFFLINE)).toContain("It will be sent when you're back online.")
    expect(receipt(ENVELOPE_QUEUED)).toContain("It will be sent when you're back online.")
    expect(receipt(ENVELOPE_REFUSED)).toContain('did not accept')
    expect(receipt(ENVELOPE_QUEUED)).not.toContain(ENVELOPE_SENT.payload_sha256)

    const none = receipt(null)
    expect(none).not.toMatch(/sealed copy/)
    expect(envelopeText(null)).toBeNull()
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('watching the sealed copy while it waits', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  async function shared(approve: EgressReceipt, receipts: EgressReceipt[]) {
    vi.useFakeTimers()
    const runtime = fakeRuntime({
      [`GET /checkin/sessions/${SID}/summary`]: () => json(SUMMARY_WITH_CARE),
      [`POST /checkin/sessions/${SID}/approve`]: () => json(approve),
      [`GET /checkin/sessions/${SID}/receipt`]: receipts.map((r) => () => json(r)),
    })
    const flow = createShareFlow(runtime.client, SID, { pollMs: 5000 })
    await flow.load()
    await flow.share()
    const polls = () => runtime.of('GET', `/checkin/sessions/${SID}/receipt`).length
    return { flow, polls }
  }

  it('keeps polling while only the envelope waits (no key, then queued), and stops once sent', async () => {
    const { flow, polls } = await shared({ ...RECEIPT_SENT, envelope: ENVELOPE_NO_KEY }, [
      { ...RECEIPT_SENT, envelope: ENVELOPE_QUEUED },
      { ...RECEIPT_SENT, envelope: ENVELOPE_SENT },
    ])
    expect(isWaitingToSend(flow.getState().receipt)).toBe(true)
    await vi.advanceTimersByTimeAsync(5000)
    expect(polls()).toBe(1)
    expect(flow.getState().receipt?.envelope).toEqual(ENVELOPE_QUEUED)
    await vi.advanceTimersByTimeAsync(5000)
    expect(polls()).toBe(2)
    expect(flow.getState().receipt?.envelope).toEqual(ENVELOPE_SENT)
    await vi.advanceTimersByTimeAsync(30000)
    expect(polls()).toBe(2)
  })

  it('keeps polling while the record is queued and the envelope waits offline', async () => {
    const { polls } = await shared({ ...RECEIPT_QUEUED, envelope: ENVELOPE_OFFLINE }, [
      { ...RECEIPT_SENT, envelope: ENVELOPE_OFFLINE },
      { ...RECEIPT_SENT, envelope: ENVELOPE_SENT },
    ])
    await vi.advanceTimersByTimeAsync(15000)
    expect(polls()).toBe(2)
  })

  it('does not poll for a refused envelope or none at all', async () => {
    expect(isWaitingToSend({ ...RECEIPT_SENT, envelope: ENVELOPE_REFUSED })).toBe(false)
    expect(isWaitingToSend({ ...RECEIPT_SENT, envelope: { ...ENVELOPE_SENT, status: 'failed' } })).toBe(false)
    expect(isWaitingToSend({ ...RECEIPT_SENT, envelope: null })).toBe(false)
    const { polls } = await shared({ ...RECEIPT_SENT, envelope: ENVELOPE_REFUSED }, [])
    await vi.advanceTimersByTimeAsync(30000)
    expect(polls()).toBe(0)
  })
})
