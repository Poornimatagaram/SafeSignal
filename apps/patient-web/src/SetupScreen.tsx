// "Set up who I share with": care team, caregiver, emergencies, then a review and one "Save and send".
// `SetupView` only renders state and forwards taps; every request goes through the SetupFlow (src/setupFlow.ts).
import { useEffect, useRef, useSyncExternalStore, type ReactNode, type RefObject } from 'react'
import { CONTACT_TYPES, type ConsentOptions } from './api.ts'
import { consentReceiptText, SWITCH_WORDS } from './ConsentScreen.tsx'
import { consentLoadMessage, setupSaveMessage } from './messages.ts'
import {
  CAREGIVER_DETAIL_WORDS,
  CONTACT_TYPE_WORDS,
  emergencyHospitalChoices,
  MAX_CONTACTS,
  MAX_EMERGENCY_HOSPITALS,
  MAX_LABEL,
  reviewSections,
  SETUP_STEPS,
  whatIsSentLines,
  type DraftContact,
  type SetupDraft,
  type SetupFlow,
  type SetupState,
} from './setupFlow.ts'
import { S } from './strings.ts'
import { AlertIcon, CheckIcon, HourglassIcon } from './Icons.tsx'

const W = S.setup

/** The flow's taps, as the view uses them. */
export type SetupActions = Pick<
  SetupFlow,
  | 'change'
  | 'chooseCareTeam'
  | 'chooseCaregiver'
  | 'toggleEmergencyHospital'
  | 'addContact'
  | 'updateContact'
  | 'removeContact'
  | 'moveContact'
  | 'next'
  | 'back'
  | 'goTo'
  | 'save'
  | 'load'
>

export interface SetupViewProps {
  state: SetupState
  actions: SetupActions
  /** Leave the setup (Cancel, or done). */
  onClose: () => void
  headingRef?: RefObject<HTMLHeadingElement | null>
}

const STEP_TITLES = W.stepTitles

export function SetupScreen({ flow, onClose }: { flow: SetupFlow; onClose: () => void }) {
  const state = useSyncExternalStore(flow.subscribe, flow.getState)
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    void flow.load()
  }, [flow])

  // Each step (and the saved page) lands on its heading.
  const where = state.phase === 'saved' ? 'saved' : state.step
  useEffect(() => {
    heading.current?.focus()
  }, [where])

  return <SetupView state={state} actions={flow} onClose={onClose} headingRef={heading} />
}

export function SetupView({ state, actions, onClose, headingRef }: SetupViewProps) {
  if (state.phase === 'loading' || state.phase === 'load-failed') {
    return (
      <main className="screen">
        <h1 className="title" tabIndex={-1} ref={headingRef}>
          {W.title}
        </h1>
        {state.phase === 'loading' ? (
          <p className="status" role="status" aria-live="polite">
            <HourglassIcon className="icon" />
            <span>{W.loading}</span>
          </p>
        ) : (
          <div className="alert" role="alert">
            <AlertIcon className="icon" />
            <p>{consentLoadMessage(state.failure?.error)}</p>
            <button type="button" className="button button--primary" onClick={() => void actions.load()}>
              {W.tryAgain}
            </button>
          </div>
        )}
        <button type="button" className="button button--secondary button--huge" onClick={onClose}>
          {W.back}
        </button>
      </main>
    )
  }

  if (state.phase === 'saved') {
    const status = state.receipt?.status
    return (
      <main className="screen">
        <div className="receipt-head" aria-live="polite">
          {status === 'queued' ? (
            <HourglassIcon className="icon icon--large" />
          ) : status === 'failed' ? (
            <AlertIcon className="icon icon--large" />
          ) : (
            <CheckIcon className="icon icon--large" />
          )}
          <h1 className="title receipt-head__title" tabIndex={-1} ref={headingRef}>
            {W.saved}
          </h1>
        </div>
        <p className="lead">{consentReceiptText(state.receipt)}</p>
        <button type="button" className="button button--primary button--huge" onClick={onClose}>
          {W.backToConsent}
        </button>
      </main>
    )
  }

  const { step, draft, options } = state
  const stepNumber = SETUP_STEPS.indexOf(step) + 1
  const saving = state.phase === 'saving'

  return (
    <main className="screen">
      <p className="progress">{W.step(stepNumber, SETUP_STEPS.length)}</p>
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        {STEP_TITLES[step]}
      </h1>

      {step === 'care' && <CareStep draft={draft} options={options} actions={actions} />}
      {step === 'caregiver' && <CaregiverStep draft={draft} options={options} actions={actions} />}
      {step === 'emergency' && <EmergencyStep draft={draft} options={options} actions={actions} />}
      {step === 'review' && <ReviewStep draft={draft} options={options} actions={actions} saving={saving} />}

      {state.problems.length > 0 && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <ul className="problems">
            {state.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      {state.failure && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{setupSaveMessage(state.failure.error)}</p>
        </div>
      )}

      <p className="status" role="status" aria-live="polite">
        {saving && (
          <>
            <HourglassIcon className="icon" />
            <span>{W.savingStatus}</span>
          </>
        )}
      </p>

      {step === 'review' ? (
        <button
          type="button"
          className="button button--primary button--huge"
          aria-disabled={saving}
          onClick={() => !saving && void actions.save()}
        >
          {saving ? W.sending : W.saveAndSend}
        </button>
      ) : (
        <button type="button" className="button button--primary button--huge" onClick={actions.next}>
          {W.next}
        </button>
      )}
      <button
        type="button"
        className="button button--secondary not-now"
        aria-disabled={saving}
        onClick={() => !saving && (stepNumber === 1 ? onClose() : actions.back())}
      >
        {stepNumber === 1 ? W.cancel : W.back}
      </button>
    </main>
  )
}

interface StepProps {
  draft: SetupDraft
  options: ConsentOptions
  actions: SetupActions
}

/** A question with big buttons; the chosen one shows a tick and "You chose", never colour alone. */
function Choices<T extends string | null>(props: {
  question: string
  choices: ReadonlyArray<{ value: T; label: string; disabled?: boolean }>
  chosen: T | readonly T[]
  onChoose: (value: T) => void
  hint?: ReactNode
}) {
  const isOn = (value: T) => (Array.isArray(props.chosen) ? props.chosen.includes(value) : props.chosen === value)
  const picked = props.choices.filter((c) => isOn(c.value)).map((c) => c.label)
  return (
    <fieldset className="choice">
      <legend className="choice__question">{props.question}</legend>
      {props.hint}
      <div className="choice__buttons choice__buttons--column">
        {props.choices.map((choice) => {
          const on = isOn(choice.value)
          return (
            <button
              key={choice.value ?? 'none'}
              type="button"
              className={`button choice__button${on ? ' choice__button--on' : ''}`}
              aria-pressed={on}
              aria-disabled={choice.disabled === true}
              onClick={() => !choice.disabled && props.onChoose(choice.value)}
            >
              {on && <CheckIcon className="icon" />}
              {choice.label}
            </button>
          )
        })}
      </div>
      <p className="choice__picked">{picked.length > 0 ? W.youChose(picked.join(', ')) : W.notChosen}</p>
    </fieldset>
  )
}

/** A big on/off switch, as on "Who I share with". */
function Switch(props: { label: string; on: boolean; means: string; id: string; onToggle: () => void }) {
  return (
    <div className="switch-row">
      <button
        type="button"
        role="switch"
        aria-checked={props.on}
        aria-describedby={`${props.id}-means`}
        className={`switch${props.on ? ' switch--on' : ''}`}
        onClick={props.onToggle}
      >
        <span className="switch__label">{props.label}</span>
        <span className="switch__state" aria-hidden="true">
          <span className="switch__track">
            <span className="switch__thumb" />
          </span>
          <span className="switch__word">{props.on ? S.consent.on : S.consent.off}</span>
        </span>
      </button>
      <p id={`${props.id}-means`} className="switch__means">
        {props.means}
      </p>
    </div>
  )
}

function CareStep({ draft, options, actions }: StepProps) {
  const words = SWITCH_WORDS.share_care_team
  return (
    <>
      <p className="lead">{W.care.lead}</p>
      <Choices
        question={W.care.question}
        choices={[
          ...options.organizations.map((org) => ({ value: org.org_id as string | null, label: org.display_name })),
          { value: null, label: W.none },
        ]}
        chosen={draft.care_org_id}
        onChoose={actions.chooseCareTeam}
      />
      {draft.care_org_id !== null && (
        <Switch
          id="setup-care"
          label={words.label}
          on={draft.share_care_team}
          means={draft.share_care_team ? words.on : words.off}
          onToggle={() => actions.change({ share_care_team: !draft.share_care_team })}
        />
      )}
    </>
  )
}

function CaregiverStep({ draft, options, actions }: StepProps) {
  const words = SWITCH_WORDS.share_caregiver
  return (
    <>
      <p className="lead">{W.caregiver.lead}</p>
      <Choices
        question={W.caregiver.question}
        choices={[
          ...options.caregivers.map((c) => ({ value: c.caregiver_id as string | null, label: c.display_name })),
          { value: null, label: W.none },
        ]}
        chosen={draft.caregiver_id}
        onChoose={actions.chooseCaregiver}
      />
      {draft.caregiver_id !== null && (
        <Switch
          id="setup-caregiver"
          label={words.label}
          on={draft.share_caregiver}
          means={draft.share_caregiver ? words.on : words.off}
          onToggle={() => actions.change({ share_caregiver: !draft.share_caregiver })}
        />
      )}
      {draft.caregiver_id !== null && draft.share_caregiver && (
        // For now a caregiver gets alerts only; the "summary" detail level is not offered.
        <p className="switch__means">{W.caregiver.alertsOnly(CAREGIVER_DETAIL_WORDS.alerts_only)}</p>
      )}
    </>
  )
}

function EmergencyStep({ draft, options, actions }: StepProps) {
  const hospitals = emergencyHospitalChoices(options, draft)
  const full = draft.emergency_org_ids.length >= MAX_EMERGENCY_HOSPITALS
  return (
    <>
      <Choices
        question={W.emergency.question}
        choices={[
          { value: 'yes', label: W.emergency.yes },
          { value: 'no', label: W.emergency.no },
        ]}
        chosen={draft.emergency_consent ? 'yes' : 'no'}
        onChoose={(value) => actions.change({ emergency_consent: value === 'yes' })}
        hint={<p>{W.emergency.hint}</p>}
      />
      {draft.emergency_consent && (
        <>
          <Choices
            question={W.emergency.hospitals(MAX_EMERGENCY_HOSPITALS)}
            choices={hospitals.map((org) => ({
              value: org.org_id,
              label: org.display_name,
              disabled: full && !draft.emergency_org_ids.includes(org.org_id),
            }))}
            chosen={draft.emergency_org_ids}
            onChoose={actions.toggleEmergencyHospital}
            hint={draft.care_org_id !== null ? <p>{W.emergency.careNotListed}</p> : null}
          />
          <section className="contacts" aria-labelledby="contacts-heading">
            <h2 id="contacts-heading" className="subtitle">
              {W.emergency.contactsHeading}
            </h2>
            <p>{W.emergency.contactsLead(MAX_CONTACTS)}</p>
            {draft.emergency_contacts.map((contact, i) => (
              <ContactEditor
                key={i}
                index={i}
                count={draft.emergency_contacts.length}
                contact={contact}
                options={options}
                actions={actions}
              />
            ))}
            {draft.emergency_contacts.length < MAX_CONTACTS && (
              <button type="button" className="button button--secondary button--huge" onClick={actions.addContact}>
                {W.emergency.addContact}
              </button>
            )}
          </section>
        </>
      )}
    </>
  )
}

function ContactEditor(props: {
  index: number
  count: number
  contact: DraftContact
  options: ConsentOptions
  actions: SetupActions
}) {
  const { index, count, contact, options, actions } = props
  const id = `contact-${index}`
  const set = (patch: Partial<DraftContact>) => actions.updateContact(index, patch)
  const hospitals = options.organizations.filter((org) => org.org_type === 'hospital')
  return (
    <div className="contact" role="group" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`} className="subtitle subtitle--small">
        {W.contact.title(index + 1)}
      </h3>
      <Choices
        question={W.contact.who}
        choices={CONTACT_TYPES.map((type) => ({ value: type, label: CONTACT_TYPE_WORDS[type] }))}
        chosen={contact.contact_type}
        onChoose={(contact_type) => set({ contact_type })}
      />
      {contact.contact_type === 'hospital' && hospitals.length > 0 && (
        <Choices
          question={W.contact.whichHospital}
          choices={[
            ...hospitals.map((org) => ({ value: org.org_id as string | null, label: org.display_name })),
            { value: null, label: W.contact.notListed },
          ]}
          chosen={contact.org_id}
          onChoose={(org_id) => set({ org_id })}
        />
      )}
      <div className="field">
        <label htmlFor={`${id}-phone`}>{W.contact.phone}</label>
        <input
          id={`${id}-phone`}
          className="input"
          type="tel"
          inputMode="tel"
          autoComplete="off"
          value={contact.phone}
          onChange={(event) => set({ phone: event.target.value })}
        />
        <p className="note">{W.contact.phoneHint}</p>
      </div>
      <div className="field">
        <label htmlFor={`${id}-label`}>{W.contact.label}</label>
        <input
          id={`${id}-label`}
          className="input"
          type="text"
          autoComplete="off"
          maxLength={MAX_LABEL}
          value={contact.label}
          onChange={(event) => set({ label: event.target.value })}
        />
        <p className="note">{W.contact.labelHint}</p>
      </div>
      <div className="contact__actions">
        {index > 0 && (
          <button type="button" className="button button--secondary" onClick={() => actions.moveContact(index, -1)}>
            {W.contact.earlier}
          </button>
        )}
        {index < count - 1 && (
          <button type="button" className="button button--secondary" onClick={() => actions.moveContact(index, 1)}>
            {W.contact.later}
          </button>
        )}
        <button type="button" className="button button--secondary" onClick={() => actions.removeContact(index)}>
          {W.contact.remove(index + 1)}
        </button>
      </div>
    </div>
  )
}

function ReviewStep({ draft, options, actions, saving }: StepProps & { saving: boolean }) {
  return (
    <>
      <p className="lead">{W.review.lead}</p>
      {reviewSections(draft, options).map((section) => (
        <section key={section.step} className="review" aria-labelledby={`review-${section.step}`}>
          <h2 id={`review-${section.step}`} className="subtitle">
            {section.title}
          </h2>
          {section.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          <button
            type="button"
            className="button button--secondary"
            aria-disabled={saving}
            onClick={() => !saving && actions.goTo(section.step)}
          >
            {W.review.change(section.title)}
          </button>
        </section>
      ))}
      <section className="share-box" aria-labelledby="review-sent">
        <h2 id="review-sent" className="subtitle">
          {W.review.whatSentHeading}
        </h2>
        {whatIsSentLines(draft).map((line) => (
          <p key={line}>{line}</p>
        ))}
      </section>
    </>
  )
}
