// "Set up who I share with" (Contract 2.0 consent setup) and one sealed copy per organization. Synthetic data only.
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createRuntimeClient,
  readEnvelopes,
  readOptions,
  readSetup,
  receiptEnvelopes,
  RuntimeError,
  type CareEnvelope,
  type ConsentState,
  type FetchLike,
} from '../src/api.ts'
import { setupSaveMessage } from '../src/messages.ts'
import {
  allProblems,
  createSetupFlow,
  draftFromConsent,
  EMPTY_DRAFT,
  INITIAL_SETUP_STATE,
  isValidPhone,
  reviewSections,
  setupRequest,
  stepProblems,
  whatIsSentLines,
  type SetupDraft,
  type SetupState,
} from '../src/setupFlow.ts'
import { SetupView, type SetupActions } from '../src/SetupScreen.tsx'
import { createShareFlow, INITIAL_SHARE_STATE, isWaitingToSend } from '../src/shareFlow.ts'
import { ShareView } from '../src/ShareScreen.tsx'
import { emergencyCopyText, sealedCopyText } from '../src/summaryText.ts'
import {
  BASE,
  CARE,
  CONSENT_ON,
  CONSENT_RECEIPT_QUEUED,
  CONSENT_RECEIPT_SENT,
  ENVELOPE_QUEUED,
  ENVELOPE_SENT,
  json,
  RECEIPT_SENT,
  SID,
  SUMMARY_READY,
  SUMMARY_WITH_CARE,
} from './fixtures.ts'

// ---- synthetic options and setup ----
const OPTIONS = {
  organizations: [
    { org_id: 'org_clinic_a', display_name: 'Maple Clinic', org_type: 'clinic' as const },
    { org_id: 'org_hosp_b', display_name: 'River Hospital', org_type: 'hospital' as const },
    { org_id: 'org_hosp_c', display_name: 'Hill Hospital', org_type: 'hospital' as const },
  ],
  caregivers: [{ caregiver_id: 'cg_1', display_name: 'Anna' }],
}

const SETUP = {
  care_org_id: 'org_clinic_a',
  caregiver_id: 'cg_1',
  caregiver_detail: 'alerts_only' as const,
  emergency_consent: true,
  emergency_org_ids: ['org_hosp_b'],
  emergency_contacts: [
    { contact_id: 'ec_2', contact_type: 'person' as const, phone: '+15550100199', org_id: null, priority: 2, label: 'Neighbour' },
    { contact_id: 'ec_1', contact_type: 'emergency_service' as const, phone: '911', org_id: null, priority: 1, label: null },
  ],
}

const CONSENT_SET: ConsentState = { ...CONSENT_ON, setup: SETUP, options: OPTIONS }

const DRAFT: SetupDraft = {
  care_org_id: 'org_clinic_a',
  share_care_team: true,
  caregiver_id: 'cg_1',
  share_caregiver: true,
  caregiver_detail: 'summary',
  emergency_consent: true,
  emergency_org_ids: ['org_hosp_b'],
  emergency_contacts: [
    { contact_type: 'emergency_service', phone: '911', org_id: null, label: '' },
    { contact_type: 'person', phone: '+1 (555) 010-0199', org_id: null, label: '  My neighbour ' },
  ],
}

interface Call {
  method: string
  path: string
  body: unknown
}

function fakeRuntime(routes: Record<string, () => Response | Promise<Response>>) {
  const calls: Call[] = []
  const fetchMock = vi.fn<FetchLike>(async (input, init) => {
    const url = new URL(input)
    const call = { method: init?.method ?? 'GET', path: url.pathname, body: init?.body }
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
describe('setup API and parsing', () => {
  it('reads setup and options from GET /consent; missing reads as null and empty', async () => {
    const { client } = fakeRuntime({ 'GET /consent': () => json(CONSENT_SET) })
    const consent = await client.getConsent()
    expect(consent.options).toEqual(OPTIONS)
    expect(consent.setup?.emergency_contacts.map((c) => c.contact_id)).toEqual(['ec_1', 'ec_2']) // priority order
    expect(readSetup(undefined)).toBeNull()
    expect(readOptions(undefined)).toEqual({ organizations: [], caregivers: [] })
  })

  it('drops unreadable options and contacts instead of failing', () => {
    expect(readOptions({ organizations: [{ org_id: 1 }, OPTIONS.organizations[0]], caregivers: 'x' })).toEqual({
      organizations: [OPTIONS.organizations[0]],
      caregivers: [],
    })
    const setup = readSetup({ ...SETUP, emergency_contacts: [{ contact_type: 'pigeon', phone: '1' }] })
    expect(setup?.emergency_contacts).toEqual([])
  })

  it('PUTs the whole setup to /consent/setup and reads the answer', async () => {
    const saved = { ...CONSENT_SET, receipt: CONSENT_RECEIPT_SENT }
    const { client, calls } = fakeRuntime({ 'PUT /consent/setup': () => json(saved) })
    const body = setupRequest(DRAFT)
    await expect(client.saveConsentSetup(body)).resolves.toMatchObject({ receipt: CONSENT_RECEIPT_SENT })
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/consent/setup' })
    expect(JSON.parse(String(calls[0].body))).toEqual(body)
  })

  it("carries the runtime's 422 reason in plain words", async () => {
    const reason = 'Your care team cannot also be your emergency hospital.'
    const { client } = fakeRuntime({ 'PUT /consent/setup': () => json({ detail: reason }, 422) })
    const error = await client.saveConsentSetup(setupRequest(DRAFT)).catch((e: unknown) => e)
    expect(error).toMatchObject({ kind: 'setup-refused', detail: reason })
    expect(setupSaveMessage(error)).toBe(reason)
    expect(setupSaveMessage(new RuntimeError('setup-refused', 422))).toMatch(/could not be saved/)
    expect(setupSaveMessage(new RuntimeError('runtime-down'))).toMatch(/not running/)
  })

  it('reads one sealed copy per organization; exactly one of receipt and waiting', () => {
    const list = readEnvelopes([
      { org_id: 'org_clinic_a', link_type: 'care_team', label: 'Your care team', receipt: ENVELOPE_SENT, waiting: null },
      { org_id: 'org_hosp_b', link_type: 'emergency', label: '', receipt: null, waiting: 'no_key' },
      { org_id: 'org_x', link_type: 'other' },
    ])
    expect(list).toHaveLength(2)
    expect(list[0]).toMatchObject({ link_type: 'care_team', receipt: ENVELOPE_SENT, waiting: null })
    expect(list[1]).toMatchObject({ link_type: 'emergency', receipt: null, waiting: 'no_key' })
    expect(readEnvelopes(undefined)).toEqual([])
  })

  it('lists envelopes when given, else the single care-team envelope (never twice)', () => {
    const both = { ...RECEIPT_SENT, envelope: ENVELOPE_SENT, envelopes: readEnvelopes([{ org_id: 'o', link_type: 'care_team', receipt: ENVELOPE_SENT }]) }
    expect(receiptEnvelopes(both)).toHaveLength(1)
    expect(receiptEnvelopes({ ...RECEIPT_SENT, envelope: ENVELOPE_QUEUED })).toMatchObject([{ receipt: ENVELOPE_QUEUED }])
    expect(receiptEnvelopes(RECEIPT_SENT)).toEqual([])
  })

  it('reads share.care.emergency (empty when missing)', async () => {
    const emergency = [{ org_id: 'org_hosp_b', display_name: 'River Hospital' }]
    const { client } = fakeRuntime({
      [`GET /checkin/sessions/${SID}/summary`]: () =>
        json({ ...SUMMARY_WITH_CARE, share: { ...SUMMARY_WITH_CARE.share, care: { ...CARE, emergency } } }),
    })
    expect((await client.getSummary(SID)).share.care?.emergency).toEqual(emergency)
    expect(CARE.emergency).toEqual([])
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('emergency sealed copies on the summary and receipt', () => {
  const EMERGENCY_WAITING: CareEnvelope = { org_id: 'org_hosp_b', link_type: 'emergency', label: '', receipt: null, waiting: 'offline' }
  const EMERGENCY_SENT: CareEnvelope = {
    org_id: 'org_hosp_b',
    link_type: 'emergency',
    label: 'Your emergency hospital (sealed: opened only in an emergency, and that is logged)',
    receipt: { ...ENVELOPE_SENT, outbox_id: 'env_2', payload_sha256: 'ab'.repeat(32) },
    waiting: null,
  }
  const CARE_SENT: CareEnvelope = { org_id: 'org_clinic_a', link_type: 'care_team', label: '', receipt: ENVELOPE_SENT, waiting: null }
  const render = (patch: Partial<typeof INITIAL_SHARE_STATE>) => {
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

  it('names the emergency hospitals the copy is also sealed to', () => {
    const care = { ...CARE, emergency: [{ org_id: 'h1', display_name: 'River Hospital' }, { org_id: 'h2', display_name: 'Hill Hospital' }] }
    const text = render({ phase: 'review', summary: { ...SUMMARY_READY, share: { ...SUMMARY_READY.share, care } } })
    expect(text).toContain('Also sealed for River Hospital and Hill Hospital: they can open it only in an emergency, and that is logged.')
    expect(emergencyCopyText([])).toBeNull()
  })

  it('shows each copy: the emergency one with its own words, time and fingerprint', () => {
    const text = render({ phase: 'receipt', receipt: { ...RECEIPT_SENT, envelope: ENVELOPE_SENT, envelopes: [CARE_SENT, EMERGENCY_SENT] } })
    expect(text).toContain("Your doctor's sealed copy")
    expect(text).toContain("Emergency hospital's sealed copy")
    expect(text).toContain('Your emergency hospital (sealed: opened only in an emergency, and that is logged)')
    expect(text).toContain('ab'.repeat(32))
    expect(text).toContain(ENVELOPE_SENT.payload_sha256)
    expect(sealedCopyText(EMERGENCY_WAITING)).toBe(
      "The emergency hospital's sealed copy is saved on this computer. It will be sent when you're back online.",
    )
  })

  it('keeps polling while any copy waits, and stops when all are sent', async () => {
    vi.useFakeTimers()
    try {
      expect(isWaitingToSend({ ...RECEIPT_SENT, envelopes: [CARE_SENT, EMERGENCY_WAITING] })).toBe(true)
      expect(isWaitingToSend({ ...RECEIPT_SENT, envelopes: [CARE_SENT, { ...EMERGENCY_WAITING, waiting: 'refused' }] })).toBe(false)
      let polls = 0
      const receipts = [
        { ...RECEIPT_SENT, envelopes: [CARE_SENT, EMERGENCY_WAITING] },
        { ...RECEIPT_SENT, envelopes: [CARE_SENT, EMERGENCY_SENT] },
      ]
      const { client } = fakeRuntime({
        [`GET /checkin/sessions/${SID}/summary`]: () => json(SUMMARY_WITH_CARE),
        [`POST /checkin/sessions/${SID}/approve`]: () => json(receipts[0]),
        [`GET /checkin/sessions/${SID}/receipt`]: () => json(receipts[Math.min(++polls, 1)]),
      })
      const flow = createShareFlow(client, SID, { pollMs: 5000 })
      await flow.load()
      await flow.share()
      await vi.advanceTimersByTimeAsync(5000)
      expect(polls).toBe(1)
      expect(isWaitingToSend(flow.getState().receipt)).toBe(false)
      await vi.advanceTimersByTimeAsync(30000)
      expect(polls).toBe(1)
    } finally {
      vi.useRealTimers()
    }
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('setup choices and checks', () => {
  it('starts from what the runtime has, contacts in priority order', () => {
    const draft = draftFromConsent(CONSENT_SET)
    expect(draft).toMatchObject({ care_org_id: 'org_clinic_a', share_care_team: true, emergency_consent: true })
    expect(draft.emergency_contacts.map((c) => c.phone)).toEqual(['911', '+15550100199'])
    expect(draft.emergency_contacts[1].label).toBe('Neighbour')
    expect(draftFromConsent(CONSENT_ON)).toEqual(EMPTY_DRAFT)
  })

  it('accepts + and 7 to 15 digits, or a 3-digit emergency number', () => {
    for (const ok of ['911', '112', '+15550100199', '+1 (555) 010-0199', '+4930123']) expect(isValidPhone(ok)).toBe(true)
    for (const bad of ['', '5550100199', '+123', '+1234567890123456', '91', 'call me']) expect(isValidPhone(bad)).toBe(false)
  })

  it('shows plain problems: bad phone, long name, care team as emergency hospital, sharing with nobody', () => {
    const bad: SetupDraft = {
      ...DRAFT,
      emergency_org_ids: ['org_clinic_a'],
      emergency_contacts: [{ contact_type: 'person', phone: '555', org_id: null, label: 'x'.repeat(41) }, { contact_type: 'person', phone: '', org_id: null, label: '' }],
    }
    const problems = stepProblems(bad, 'emergency', OPTIONS).join(' ')
    expect(problems).toContain('Your care team cannot also be your emergency hospital')
    expect(problems).toContain('Contact 1: the name can be at most 40 letters.')
    expect(problems).toContain('Contact 2: please type a phone number.')
    expect(stepProblems({ ...DRAFT, care_org_id: null }, 'care', OPTIONS)[0]).toMatch(/Choose your hospital or clinic/)
    expect(allProblems(DRAFT, OPTIONS)).toEqual([])
  })

  it('builds the body: priority by order, phones cleaned, names only as label, nothing for emergencies when off', () => {
    const body = setupRequest(DRAFT)
    expect(body.emergency_contacts).toEqual([
      { contact_type: 'emergency_service', phone: '911', org_id: null, priority: 1, label: null },
      { contact_type: 'person', phone: '+15550100199', org_id: null, priority: 2, label: 'My neighbour' },
    ])
    const off = setupRequest({ ...DRAFT, emergency_consent: false })
    expect(off.emergency_org_ids).toEqual([])
    expect(off.emergency_contacts).toEqual([])
    expect(JSON.stringify(off)).not.toMatch(/neighbour|911|\+1555/i)
    // Display names of places and people are never in the body: only their codes.
    expect(JSON.stringify(body)).not.toMatch(/Maple|River|Anna/)
    expect(setupRequest({ ...DRAFT, caregiver_id: null }).share_caregiver).toBe(false)
  })

  it('a caregiver gets alerts only for now: the summary level is never sent', () => {
    expect(DRAFT.caregiver_detail).toBe('summary') // even a draft that somehow holds it
    expect(setupRequest(DRAFT).caregiver_detail).toBe('alerts_only')
  })
})

// ---------------------------------------------------------------------------------------------------------------
describe('setup flow and screen', () => {
  afterEach(() => vi.useRealTimers())

  const noopActions: SetupActions = {
    change: () => undefined,
    chooseCareTeam: () => undefined,
    chooseCaregiver: () => undefined,
    toggleEmergencyHospital: () => undefined,
    addContact: () => undefined,
    updateContact: () => undefined,
    removeContact: () => undefined,
    moveContact: () => undefined,
    next: () => undefined,
    back: () => undefined,
    goTo: () => undefined,
    save: async () => undefined,
    load: async () => undefined,
  }
  const render = (patch: Partial<SetupState>) =>
    renderToStaticMarkup(
      <SetupView state={{ ...INITIAL_SETUP_STATE, phase: 'editing', options: OPTIONS, ...patch }} actions={noopActions} onClose={() => undefined} />,
    )

  it('the caregiver step offers no summary option, only alerts', () => {
    const html = render({ step: 'caregiver', draft: DRAFT })
    expect(textOf(html)).toContain('Only alerts')
    expect(textOf(html)).not.toContain('Alerts and a summary')
    expect(textOf(html)).not.toContain('What should your caregiver get?')
  })

  it('the review lists choices and what is sent in plain words; names stay on this computer', () => {
    const text = textOf(render({ step: 'review', draft: DRAFT }))
    expect(text).toContain('Step 4 of 4')
    expect(text).toContain('Maple Clinic: your check-ins go to them sealed, so only they can read them.')
    expect(text).toContain('Anna: only alerts about a severe problem.')
    expect(text).not.toContain('summary of each check-in')
    expect(text).toContain('Hospitals: River Hospital.')
    expect(text).toContain('Contact 1: An emergency number (like 911), 911.')
    expect(text).toContain('Contact 2: A person, +15550100199.')
    expect(text).toContain('No names are sent. The names you typed for your contacts stay on this computer.')
    expect(text).toContain('phone numbers of your emergency contacts')
    expect(text).not.toContain('neighbour')
    expect(text).toContain('Save and send')
  })

  it('without emergency consent the review says no phones and nothing about emergencies is sent', () => {
    const draft = { ...DRAFT, emergency_consent: false }
    expect(whatIsSentLines(draft).join(' ')).toContain('No phone numbers.')
    expect(reviewSections(draft, OPTIONS)[2].lines).toEqual(['No. No emergency hospital or contact is kept or sent.'])
  })

  it('the care step offers each place and None; the care team is not offered as an emergency hospital', () => {
    const care = textOf(render({ step: 'care', draft: DRAFT }))
    expect(care).toContain('Maple Clinic')
    expect(care).toContain('None')
    expect(care).toContain('You chose: Maple Clinic')
    expect(render({ step: 'care', draft: DRAFT })).toContain('role="switch"')
    const emergency = textOf(render({ step: 'emergency', draft: { ...DRAFT, care_org_id: 'org_hosp_c' } }))
    expect(emergency).toContain('River Hospital')
    expect(emergency).toContain('This name stays on this computer. It is never sent.')
    const hospitals = emergency.slice(emergency.indexOf('Which hospitals?'), emergency.indexOf('Who to call'))
    expect(hospitals).not.toContain('Hill Hospital')
  })

  it('shows problems and the saved receipt wording', () => {
    expect(textOf(render({ step: 'emergency', draft: DRAFT, problems: ['Contact 1: please type a phone number.'] }))).toContain(
      'Contact 1: please type a phone number.',
    )
    expect(textOf(render({ phase: 'saved', receipt: CONSENT_RECEIPT_QUEUED }))).toContain(
      "Saved on this device. It will be sent when you're back online.",
    )
    expect(textOf(render({ step: 'review', draft: DRAFT, failure: { error: new RuntimeError('setup-refused', 422, [], 'Too many contacts.') } }))).toContain(
      'Too many contacts.',
    )
  })

  it('walks the steps, blocks Next on a problem, and Save sends exactly one PUT', async () => {
    let release: () => void = () => undefined
    const { client, calls } = fakeRuntime({
      'GET /consent': () => json(CONSENT_SET),
      'PUT /consent/setup': () =>
        new Promise<Response>((resolve) => {
          release = () => resolve(json({ ...CONSENT_SET, receipt: CONSENT_RECEIPT_SENT }))
        }),
    })
    const flow = createSetupFlow(client)
    await flow.load()
    expect(flow.getState().phase).toBe('editing')

    flow.next() // care
    flow.next() // caregiver
    expect(flow.getState().step).toBe('emergency')
    flow.addContact() // a third, empty contact
    flow.next()
    expect(flow.getState().step).toBe('emergency')
    expect(flow.getState().problems).toContain('Contact 3: please type a phone number.')
    flow.updateContact(2, { phone: '+44 20 7946 0000', label: 'Daughter' })
    expect(flow.getState().problems).toEqual([])
    flow.moveContact(2, -1)
    flow.next()
    expect(flow.getState().step).toBe('review')
    expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(0) // nothing sent before Save and send

    const first = flow.save()
    const second = flow.save() // a double tap
    release()
    await Promise.all([first, second])
    const puts = calls.filter((c) => c.method === 'PUT')
    expect(puts).toHaveLength(1)
    const body = JSON.parse(String(puts[0].body))
    expect(body.emergency_contacts.map((c: { phone: string; priority: number }) => [c.priority, c.phone])).toEqual([
      [1, '911'],
      [2, '+442079460000'],
      [3, '+15550100199'],
    ])
    expect(body.emergency_contacts[1].label).toBe('Daughter') // to the local runtime only, which keeps it there
    expect(flow.getState()).toMatchObject({ phase: 'saved', receipt: CONSENT_RECEIPT_SENT })
  })

  it('a 422 keeps the choices on screen with the reason; a fix clears it', async () => {
    const { client } = fakeRuntime({
      'GET /consent': () => json(CONSENT_SET),
      'PUT /consent/setup': () => json({ detail: 'That hospital is not known on this computer.' }, 422),
    })
    const flow = createSetupFlow(client)
    await flow.load()
    flow.goTo('review')
    await flow.save()
    expect(flow.getState().phase).toBe('editing')
    expect(setupSaveMessage(flow.getState().failure?.error)).toBe('That hospital is not known on this computer.')
    flow.change({ caregiver_detail: 'summary' })
    expect(flow.getState().failure).toBeNull()
  })

  it('choosing the care team removes it from the emergency hospitals; None turns sharing off', async () => {
    const { client } = fakeRuntime({ 'GET /consent': () => json(CONSENT_SET) })
    const flow = createSetupFlow(client)
    await flow.load()
    flow.chooseCareTeam('org_hosp_b')
    expect(flow.getState().draft.emergency_org_ids).toEqual([])
    flow.toggleEmergencyHospital('org_hosp_b')
    expect(flow.getState().draft.emergency_org_ids).toEqual([])
    flow.chooseCareTeam(null)
    expect(flow.getState().draft).toMatchObject({ care_org_id: null, share_care_team: false })
  })
})
