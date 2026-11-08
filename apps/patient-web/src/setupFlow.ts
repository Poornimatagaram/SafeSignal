// "Set up who I share with" (Contract 2.0 consent setup): care team, caregiver and emergencies, then a review and
// ONE "Save and send". A small state machine with no React in it; the runtime sends the update through its egress
// gate. Contact names typed here go to the local runtime as `label`, which keeps them on this device only.
import {
  type CaregiverDetail,
  type ConsentOptions,
  type ConsentSetupRequest,
  type ConsentState,
  type ContactType,
  type OutboxReceipt,
  type RuntimeClient,
} from './api.ts'

export const MAX_EMERGENCY_HOSPITALS = 3
export const MAX_CONTACTS = 3
export const MAX_LABEL = 40

export type SetupStep = 'care' | 'caregiver' | 'emergency' | 'review'
export const SETUP_STEPS: readonly SetupStep[] = ['care', 'caregiver', 'emergency', 'review']

/** One emergency contact being typed. Its priority is its place in the list (first = called first). */
export interface DraftContact {
  contact_type: ContactType
  phone: string
  org_id: string | null
  label: string
}

export interface SetupDraft {
  care_org_id: string | null
  share_care_team: boolean
  caregiver_id: string | null
  share_caregiver: boolean
  caregiver_detail: CaregiverDetail
  emergency_consent: boolean
  emergency_org_ids: string[]
  emergency_contacts: DraftContact[]
}

export type SetupPhase = 'loading' | 'load-failed' | 'editing' | 'saving' | 'saved'

export interface SetupState {
  readonly phase: SetupPhase
  readonly step: SetupStep
  readonly options: ConsentOptions
  readonly draft: SetupDraft
  /** Problems shown for the current step (after a "Next" or "Save and send" with something missing or wrong). */
  readonly problems: readonly string[]
  /** The last failure (loading or saving), for plain words; a 422 carries the runtime's reason. */
  readonly failure: { readonly error: unknown } | null
  /** Where the saved update stands (sent, queued, failed). */
  readonly receipt: OutboxReceipt | null
}

export const EMPTY_DRAFT: SetupDraft = {
  care_org_id: null,
  share_care_team: false,
  caregiver_id: null,
  share_caregiver: false,
  caregiver_detail: 'alerts_only',
  emergency_consent: false,
  emergency_org_ids: [],
  emergency_contacts: [],
}

export const INITIAL_SETUP_STATE: SetupState = {
  phase: 'loading',
  step: 'care',
  options: { organizations: [], caregivers: [] },
  draft: EMPTY_DRAFT,
  problems: [],
  failure: null,
  receipt: null,
}

/** The draft as the runtime has it now. */
export function draftFromConsent(consent: ConsentState): SetupDraft {
  const setup = consent.setup
  if (!setup) return EMPTY_DRAFT
  return {
    care_org_id: setup.care_org_id,
    share_care_team: setup.care_org_id !== null && consent.share_care_team,
    caregiver_id: setup.caregiver_id,
    share_caregiver: setup.caregiver_id !== null && consent.share_caregiver,
    caregiver_detail: setup.caregiver_detail,
    emergency_consent: setup.emergency_consent,
    emergency_org_ids: setup.emergency_org_ids.filter((id) => id !== setup.care_org_id),
    emergency_contacts: [...setup.emergency_contacts]
      .sort((a, b) => a.priority - b.priority)
      .slice(0, MAX_CONTACTS)
      .map((c) => ({ contact_type: c.contact_type, phone: c.phone, org_id: c.org_id, label: c.label ?? '' })),
  }
}

/** A phone number without spaces, dashes, dots or brackets: "+1 (555) 010-0199" -> "+15550100199". */
export function normalizePhone(phone: string): string {
  return phone.replace(/[\s\-().]/g, '')
}

/** "+" and 7 to 15 digits, or a 3-digit emergency number such as 911. */
export function isValidPhone(phone: string): boolean {
  const p = normalizePhone(phone)
  return /^\+\d{7,15}$/.test(p) || /^\d{3}$/.test(p)
}

/** Hospitals that can be chosen for emergencies: never the care team. */
export function emergencyHospitalChoices(options: ConsentOptions, draft: SetupDraft) {
  return options.organizations.filter((org) => org.org_type === 'hospital' && org.org_id !== draft.care_org_id)
}

/** Plain-words problems with one step of the draft (the runtime checks again and has the last word). */
export function stepProblems(draft: SetupDraft, step: SetupStep, options: ConsentOptions): string[] {
  const problems: string[] = []
  const orgIds = new Set(options.organizations.map((o) => o.org_id))
  if (step === 'care' || step === 'review') {
    if (draft.share_care_team && draft.care_org_id === null) {
      problems.push('Choose your hospital or clinic, or turn off sharing with your doctor.')
    }
  }
  if (step === 'caregiver' || step === 'review') {
    if (draft.share_caregiver && draft.caregiver_id === null) {
      problems.push('Choose your caregiver, or turn off sharing with your caregiver.')
    }
  }
  if ((step === 'emergency' || step === 'review') && draft.emergency_consent) {
    if (draft.care_org_id !== null && draft.emergency_org_ids.includes(draft.care_org_id)) {
      problems.push('Your care team cannot also be your emergency hospital. Please choose another hospital.')
    }
    if (draft.emergency_org_ids.length > MAX_EMERGENCY_HOSPITALS) {
      problems.push(`Choose at most ${MAX_EMERGENCY_HOSPITALS} emergency hospitals.`)
    }
    if (draft.emergency_contacts.length > MAX_CONTACTS) problems.push(`You can have at most ${MAX_CONTACTS} contacts.`)
    draft.emergency_contacts.forEach((contact, i) => {
      const which = `Contact ${i + 1}`
      if (normalizePhone(contact.phone) === '') {
        problems.push(`${which}: please type a phone number.`)
      } else if (!isValidPhone(contact.phone)) {
        problems.push(
          `${which}: the phone number should start with + and the country code (for example +1 555 010 0199), or be an emergency number like 911.`,
        )
      }
      if (contact.label.trim().length > MAX_LABEL) problems.push(`${which}: the name can be at most ${MAX_LABEL} letters.`)
      if (contact.org_id !== null && !orgIds.has(contact.org_id)) problems.push(`${which}: please choose the hospital again.`)
    })
  }
  return problems
}

/** Everything wrong with the whole draft. */
export function allProblems(draft: SetupDraft, options: ConsentOptions): string[] {
  return stepProblems(draft, 'review', options)
}

/**
 * The PUT /consent/setup body. Without emergency consent no hospital or contact is included at all. Sharing is
 * off when nobody is chosen. Priority is the contact's place in the list. Names go only to the local runtime.
 */
export function setupRequest(draft: SetupDraft): ConsentSetupRequest {
  const emergency = draft.emergency_consent
  return {
    care_org_id: draft.care_org_id,
    share_care_team: draft.care_org_id !== null && draft.share_care_team,
    caregiver_id: draft.caregiver_id,
    share_caregiver: draft.caregiver_id !== null && draft.share_caregiver,
    caregiver_detail: draft.caregiver_detail,
    emergency_consent: emergency,
    emergency_org_ids: emergency ? draft.emergency_org_ids.filter((id) => id !== draft.care_org_id) : [],
    emergency_contacts: emergency
      ? draft.emergency_contacts.map((c, i) => ({
          contact_type: c.contact_type,
          phone: normalizePhone(c.phone),
          org_id: c.contact_type === 'hospital' ? c.org_id : null,
          priority: i + 1,
          label: c.label.trim() === '' ? null : c.label.trim(),
        }))
      : [],
  }
}

export interface SetupFlow {
  getState(): SetupState
  subscribe(listener: () => void): () => void
  /** GET /consent for the current choices and the options. Sends nothing. */
  load(): Promise<void>
  /** Change the draft (nothing is sent until "Save and send"). */
  change(patch: Partial<SetupDraft>): void
  chooseCareTeam(orgId: string | null): void
  chooseCaregiver(caregiverId: string | null): void
  toggleEmergencyHospital(orgId: string): void
  addContact(): void
  updateContact(index: number, patch: Partial<DraftContact>): void
  removeContact(index: number): void
  /** Move a contact up (-1) or down (+1): the order is who is called first. */
  moveContact(index: number, direction: -1 | 1): void
  /** "Next": only when this step has no problems (they are shown otherwise). */
  next(): void
  back(): void
  /** "Change" on the review page: go to that step. */
  goTo(step: SetupStep): void
  /** "Save and send": ONE PUT /consent/setup. A second tap while saving sends nothing. */
  save(): Promise<void>
  dispose(): void
}

export function createSetupFlow(client: RuntimeClient): SetupFlow {
  let state: SetupState = INITIAL_SETUP_STATE
  const listeners = new Set<() => void>()
  let disposed = false
  let loadingNow = false

  const update = (patch: Partial<SetupState>) => {
    state = { ...state, ...patch }
    for (const listener of listeners) listener()
  }

  const editing = () => state.phase === 'editing'

  /** A draft change clears the shown problems only once they are fixed; a 422 message goes as soon as anything changes. */
  const setDraft = (draft: SetupDraft) => {
    const problems = state.problems.length > 0 ? stepProblems(draft, state.step, state.options) : []
    update({ draft, problems, failure: null })
  }

  const contacts = (fn: (list: DraftContact[]) => DraftContact[]) =>
    setDraft({ ...state.draft, emergency_contacts: fn([...state.draft.emergency_contacts]) })

  return {
    getState: () => state,

    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },

    async load() {
      if (disposed || loadingNow || (state.phase !== 'loading' && state.phase !== 'load-failed')) return
      loadingNow = true
      update({ phase: 'loading', failure: null })
      try {
        const consent = await client.getConsent()
        if (disposed) return
        update({ phase: 'editing', options: consent.options, draft: draftFromConsent(consent) })
      } catch (error) {
        if (!disposed) update({ phase: 'load-failed', failure: { error } })
      } finally {
        loadingNow = false
      }
    },

    change(patch) {
      if (editing()) setDraft({ ...state.draft, ...patch })
    },

    chooseCareTeam(orgId) {
      if (!editing()) return
      setDraft({
        ...state.draft,
        care_org_id: orgId,
        // Choosing a team turns sharing on (that is why it was chosen); "None" turns it off.
        share_care_team: orgId !== null,
        emergency_org_ids: state.draft.emergency_org_ids.filter((id) => id !== orgId),
      })
    },

    chooseCaregiver(caregiverId) {
      if (!editing()) return
      setDraft({ ...state.draft, caregiver_id: caregiverId, share_caregiver: caregiverId !== null })
    },

    toggleEmergencyHospital(orgId) {
      if (!editing() || orgId === state.draft.care_org_id) return
      const chosen = state.draft.emergency_org_ids
      if (chosen.includes(orgId)) {
        setDraft({ ...state.draft, emergency_org_ids: chosen.filter((id) => id !== orgId) })
      } else if (chosen.length < MAX_EMERGENCY_HOSPITALS) {
        setDraft({ ...state.draft, emergency_org_ids: [...chosen, orgId] })
      }
    },

    addContact() {
      if (!editing() || state.draft.emergency_contacts.length >= MAX_CONTACTS) return
      contacts((list) => [...list, { contact_type: 'person', phone: '', org_id: null, label: '' }])
    },

    updateContact(index, patch) {
      if (!editing() || !state.draft.emergency_contacts[index]) return
      contacts((list) => {
        const next = { ...list[index], ...patch }
        if (next.contact_type !== 'hospital') next.org_id = null
        list[index] = next
        return list
      })
    },

    removeContact(index) {
      if (!editing() || !state.draft.emergency_contacts[index]) return
      contacts((list) => list.filter((_, i) => i !== index))
    },

    moveContact(index, direction) {
      const to = index + direction
      const list = state.draft.emergency_contacts
      if (!editing() || !list[index] || !list[to]) return
      contacts((l) => {
        ;[l[index], l[to]] = [l[to], l[index]]
        return l
      })
    },

    next() {
      if (!editing()) return
      const problems = stepProblems(state.draft, state.step, state.options)
      if (problems.length > 0) {
        update({ problems })
        return
      }
      const i = SETUP_STEPS.indexOf(state.step)
      update({ step: SETUP_STEPS[Math.min(i + 1, SETUP_STEPS.length - 1)], problems: [], failure: null })
    },

    back() {
      if (!editing()) return
      const i = SETUP_STEPS.indexOf(state.step)
      if (i > 0) update({ step: SETUP_STEPS[i - 1], problems: [], failure: null })
    },

    goTo(step) {
      if (editing()) update({ step, problems: [], failure: null })
    },

    async save() {
      if (!editing() || state.step !== 'review') return
      const problems = allProblems(state.draft, state.options)
      if (problems.length > 0) {
        update({ problems })
        return
      }
      update({ phase: 'saving', problems: [], failure: null })
      try {
        const consent = await client.saveConsentSetup(setupRequest(state.draft))
        if (disposed) return
        update({ phase: 'saved', receipt: consent.receipt, options: consent.options })
      } catch (error) {
        if (disposed) return
        update({ phase: 'editing', failure: { error } })
      }
    },

    dispose() {
      disposed = true
      listeners.clear()
    },
  }
}

export const CONTACT_TYPE_WORDS: Record<ContactType, string> = {
  emergency_service: 'An emergency number (like 911)',
  hospital: 'A hospital',
  person: 'A person',
}

export const CAREGIVER_DETAIL_WORDS: Record<CaregiverDetail, string> = {
  alerts_only: 'Only alerts',
  summary: 'Alerts and a summary',
}

export interface ReviewSection {
  step: Exclude<SetupStep, 'review'>
  title: string
  lines: string[]
}

const nameOf = (list: ReadonlyArray<{ id: string; name: string }>, id: string | null) =>
  list.find((item) => item.id === id)?.name ?? 'the one you chose'

/** The review page in plain words: what was chosen and exactly what will be sent. */
export function reviewSections(draft: SetupDraft, options: ConsentOptions): ReviewSection[] {
  const orgs = options.organizations.map((o) => ({ id: o.org_id, name: o.display_name }))
  const people = options.caregivers.map((c) => ({ id: c.caregiver_id, name: c.display_name }))
  const request = setupRequest(draft)

  const care =
    request.care_org_id === null
      ? ['No care team. Your doctor gets nothing.']
      : request.share_care_team
        ? [`${nameOf(orgs, request.care_org_id)}: your check-ins go to them sealed, so only they can read them.`]
        : [`${nameOf(orgs, request.care_org_id)}: sharing is off, so they get nothing new.`]

  const caregiver =
    request.caregiver_id === null
      ? ['No caregiver. Nobody else is told anything.']
      : request.share_caregiver
        ? [
            request.caregiver_detail === 'summary'
              ? `${nameOf(people, request.caregiver_id)}: alerts about a severe problem, and a summary of each check-in.`
              : `${nameOf(people, request.caregiver_id)}: only alerts about a severe problem.`,
          ]
        : [`${nameOf(people, request.caregiver_id)}: sharing is off, so they get nothing new.`]

  const emergency: string[] = []
  if (!request.emergency_consent) {
    emergency.push('No. No emergency hospital or contact is kept or sent.')
  } else {
    emergency.push('Yes. An emergency hospital may open your history only in an emergency, and that is logged.')
    emergency.push(
      request.emergency_org_ids.length === 0
        ? 'No emergency hospital chosen.'
        : `Hospitals: ${request.emergency_org_ids.map((id) => nameOf(orgs, id)).join(', ')}.`,
    )
    if (request.emergency_contacts.length === 0) emergency.push('No contacts.')
    request.emergency_contacts.forEach((c) => {
      const where = c.contact_type === 'hospital' && c.org_id ? ` (${nameOf(orgs, c.org_id)})` : ''
      emergency.push(`Contact ${c.priority}: ${CONTACT_TYPE_WORDS[c.contact_type]}${where}, ${c.phone}.`)
    })
  }

  return [
    { step: 'care', title: 'My care team', lines: care },
    { step: 'caregiver', title: 'My caregiver', lines: caregiver },
    { step: 'emergency', title: 'Emergencies', lines: emergency },
  ]
}

/** What leaves this computer when the patient taps "Save and send", in plain words. */
export function whatIsSentLines(draft: SetupDraft): string[] {
  const request = setupRequest(draft)
  const phones = request.emergency_contacts.length > 0
  return [
    'A coded update goes through the privacy check on this computer to the service.',
    phones
      ? 'It holds the codes of the places and the caregiver you chose, whether each one is on, and the phone numbers of your emergency contacts.'
      : 'It holds the codes of the places and the caregiver you chose, and whether each one is on. No phone numbers.',
    'No names are sent. The names you typed for your contacts stay on this computer.',
  ]
}
