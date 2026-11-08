// "Who I share with" (CN-01, CN-03): two big switches. `ConsentView` only renders state and forwards taps; every
// request goes through the ConsentFlow (src/consentFlow.ts).
import { useEffect, useRef, useSyncExternalStore, type RefObject } from 'react'
import type { ConsentKey, ConsentState, OutboxReceipt } from './api.ts'
import { canToggle, hasRecipient, type ConsentFlow, type ConsentFlowState } from './consentFlow.ts'
import { consentChangeMessage, consentLoadMessage } from './messages.ts'
import { AlertIcon, CheckIcon, HourglassIcon } from './Icons.tsx'

export interface ConsentViewProps {
  state: ConsentFlowState
  onToggle: (key: ConsentKey) => void
  onRetry: () => void
  onBack: () => void
  headingRef?: RefObject<HTMLHeadingElement | null>
}

interface SwitchWords {
  label: string
  on: string
  off: string
  nobody: string
}

export const SWITCH_WORDS: Record<ConsentKey, SwitchWords> = {
  share_care_team: {
    label: 'Share with my doctor',
    on: "Your doctor's team gets your check-ins, sealed so only they can read them.",
    off: "Your doctor's team gets nothing new from now on.",
    nobody: 'No doctor is set up on this computer yet, so this cannot be turned on. Please ask your helper.',
  },
  share_caregiver: {
    label: 'Share with my caregiver',
    on: 'Your caregiver is told when you report a severe problem.',
    off: 'Your caregiver gets nothing new from now on.',
    nobody: 'No caregiver is set up on this computer yet, so this cannot be turned on. Please ask your helper.',
  },
}

/** Where a change stands, in plain words. */
export function consentReceiptText(receipt: OutboxReceipt | null): string {
  if (receipt === null) return 'Saved on this device.'
  switch (receipt.status) {
    case 'sent':
      return 'Saved and sent.'
    case 'queued':
      return "Saved on this device. It will be sent when you're back online."
    case 'failed':
      return 'Saved on this device, but the service did not accept it. Please tell your helper.'
  }
}

export function ConsentScreen({ flow, onBack }: { flow: ConsentFlow; onBack: () => void }) {
  const state = useSyncExternalStore(flow.subscribe, flow.getState)
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    heading.current?.focus()
    void flow.load()
  }, [flow])

  return (
    <ConsentView
      state={state}
      headingRef={heading}
      onToggle={(key) => void flow.toggle(key)}
      onRetry={() => void flow.load()}
      onBack={onBack}
    />
  )
}

export function ConsentView({ state, onToggle, onRetry, onBack, headingRef }: ConsentViewProps) {
  const { consent } = state
  return (
    <main className="screen">
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        Who I share with
      </h1>
      <p className="lead">Tap a switch to turn it on or off. A change counts straight away.</p>

      {state.phase === 'loading' && (
        <p className="status" role="status" aria-live="polite">
          <HourglassIcon className="icon" />
          <span>Getting your choices…</span>
        </p>
      )}

      {state.phase === 'load-failed' && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{consentLoadMessage(state.failure?.error)}</p>
          <button type="button" className="button button--primary" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}

      {state.phase === 'ready' && consent && (
        <div className="switches">
          {(['share_care_team', 'share_caregiver'] as const).map((key) => (
            <ConsentSwitch key={key} which={key} consent={consent} state={state} onToggle={onToggle} />
          ))}
        </div>
      )}

      <button type="button" className="button button--secondary button--huge" onClick={onBack}>
        Back to my check-in
      </button>
    </main>
  )
}

function ConsentSwitch(props: {
  which: ConsentKey
  consent: ConsentState
  state: ConsentFlowState
  onToggle: (key: ConsentKey) => void
}) {
  const { which, consent, state, onToggle } = props
  const words = SWITCH_WORDS[which]
  const on = consent[which]
  const enabled = canToggle(state, which)
  const nobody = !on && !hasRecipient(consent, which)
  const saving = state.saving === which
  const failed = state.failure?.key === which
  const saved = !saving && !failed && state.saved?.key === which ? state.saved : null
  const meansId = `${which}-means`
  const statusId = `${which}-status`

  return (
    <div className="switch-row">
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-disabled={!enabled}
        aria-describedby={`${meansId} ${statusId}`}
        className={`switch${on ? ' switch--on' : ''}`}
        onClick={() => enabled && onToggle(which)}
      >
        <span className="switch__label">{words.label}</span>
        <span className="switch__state" aria-hidden="true">
          <span className="switch__track">
            <span className="switch__thumb" />
          </span>
          <span className="switch__word">{on ? 'On' : 'Off'}</span>
        </span>
      </button>
      <p id={meansId} className="switch__means">
        {nobody ? words.nobody : on ? words.on : words.off}
      </p>
      <p id={statusId} className="status" role="status" aria-live="polite">
        {saving ? (
          <>
            <HourglassIcon className="icon" />
            <span>Saving…</span>
          </>
        ) : saved ? (
          <>
            {saved.receipt?.status === 'queued' ? (
              <HourglassIcon className="icon" />
            ) : saved.receipt?.status === 'failed' ? (
              <AlertIcon className="icon" />
            ) : (
              <CheckIcon className="icon" />
            )}
            <span>{consentReceiptText(saved.receipt)}</span>
          </>
        ) : null}
      </p>
      {failed && state.failure && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{consentChangeMessage(state.failure.error)}</p>
        </div>
      )}
    </div>
  )
}
