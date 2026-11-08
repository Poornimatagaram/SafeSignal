// The end of the check-in: summary, approve-before-share (PV-04) and the egress receipt (PV-05).
// `ShareView` only renders state and forwards taps; every request goes through the ShareFlow (src/shareFlow.ts).
// Also: the spoken summary, "Change one answer" (VC-08) and a receipt saved while offline (PV-07, AL-02).
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type RefObject } from 'react'
import {
  ONSETS,
  SEVERITIES,
  type CheckinSummary,
  type CorrectionChange,
  receiptEnvelopes,
  type CareEnvelope,
  type EgressReceipt,
  type Severity,
  type SummaryItem,
} from './api.ts'
import { startRecording, type ActiveRecording } from './recorder.ts'
import {
  canCorrect,
  canShare,
  missingSeverities,
  type ShareFlow,
  type SharePhase,
  type ShareState,
} from './shareFlow.ts'
import {
  correctionErrorMessage,
  needsRestart,
  shareErrorMessage,
  summaryErrorMessage,
  summaryVoiceMessage,
} from './messages.ts'
import {
  alertText,
  CARE_TEAM_OFF,
  CARE_TEAM_SEALED,
  careTeamPartsText,
  emergencyCopyText,
  sealedCopyDestination,
  sealedCopyHeading,
  sealedCopyText,
  formatLocalTime,
  itemLabel,
  NOTHING_TO_REPORT,
  ONSET_CHOICES,
  onsetSentence,
  POSSIBLE_LINK_TEXT,
  QUEUED_EXPLANATION,
  receiptStatusText,
  severityQuestion,
  severityText,
  SEVERITY_WORDS,
  sharedPartsText,
} from './summaryText.ts'
import { S } from './strings.ts'
import { SoundOffNote } from './SoundControls.tsx'
import { AlertIcon, BackIcon, CheckIcon, HourglassIcon, MicIcon, ShareIcon, SlowIcon, SpeakerIcon, StopIcon } from './Icons.tsx'

const W = S.summary
const B = S.summary.box
const R = S.receipt

type HeadingRef = RefObject<HTMLHeadingElement | null>

/** Recording the spoken change: tap to start, tap to stop (like an answer). */
export type SayTalk = 'idle' | 'starting' | 'listening'

export interface ShareViewProps {
  state: ShareState
  onChoose: (termCode: string, severity: Severity) => void
  onShare: () => void
  onNotNow: () => void
  onBack: () => void
  onRetryLoad: () => void
  onRestart: () => void
  headingRef?: HeadingRef
  /** "Repeat" (false) and "Slower" (true) for the spoken summary. */
  onHear?: (slow: boolean) => void
  onOpenCorrection?: () => void
  onCorrectionMode?: (mode: 'say' | 'tap') => void
  onPickItem?: (termCode: string) => void
  onCorrect?: (change: CorrectionChange) => void
  onCloseCorrection?: () => void
  /** Tap to start or stop recording the spoken change. */
  onSayToggle?: () => void
  sayTalk?: SayTalk
  /** A microphone problem while recording the spoken change. */
  sayError?: unknown
  /** "Repeat" or "Slower" was tapped with the sound off: "Sound is off. Tap Unmute to hear it." */
  soundOff?: boolean
}

const noop = () => undefined

/** Which page is showing; focus moves to its heading only when this changes. */
function pageOf(phase: SharePhase): string {
  if (phase === 'sending') return 'review'
  if (phase === 'load-failed') return 'loading'
  return phase
}

export interface ShareScreenProps {
  flow: ShareFlow
  onRestart: () => void
  /** Sound off: "Repeat" and "Slower" play nothing and say so instead. */
  muted?: boolean
}

export function ShareScreen({ flow, onRestart, muted = false }: ShareScreenProps) {
  const state = useSyncExternalStore(flow.subscribe, flow.getState)
  const heading = useRef<HTMLHeadingElement>(null)
  const page = pageOf(state.phase)
  const recording = useRef<ActiveRecording | null>(null)
  const sayNow = useRef<SayTalk>('idle')
  const [sayTalk, setSayTalk] = useState<SayTalk>('idle')
  const [sayError, setSayError] = useState<unknown>(null)
  const mounted = useRef(true)
  const [soundOff, setSoundOff] = useState(false)
  // Turning the sound back on hides the note (nothing replays by itself).
  useEffect(() => {
    if (!muted) setSoundOff(false)
  }, [muted])

  const updateSay = useCallback((next: SayTalk) => {
    sayNow.current = next
    setSayTalk(next)
  }, [])

  // Keyboard and screen-reader users land on each new page's heading.
  useEffect(() => {
    heading.current?.focus()
  }, [page])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      recording.current?.cancel()
      recording.current = null
    }
  }, [])

  // Leaving "Say the change" (closed, tapped instead, or the change went through) drops any open recording.
  const sayOpen = state.correction.step === 'say'
  useEffect(() => {
    if (sayOpen) return
    recording.current?.cancel()
    recording.current = null
    updateSay('idle')
    setSayError(null)
  }, [sayOpen, updateSay])

  const toggleSay = async () => {
    if (sayNow.current === 'idle') {
      if (state.correction.sending) return
      flow.stopVoice()
      setSayError(null)
      updateSay('starting')
      try {
        const active = await startRecording()
        if (!mounted.current || flow.getState().correction.step !== 'say') {
          active.cancel()
          return
        }
        recording.current = active
        updateSay('listening')
      } catch (error) {
        if (!mounted.current) return
        updateSay('idle')
        setSayError(error)
      }
      return
    }
    if (sayNow.current === 'listening') {
      // Only this tap ends the recording: long pauses never do (VC-03).
      const active = recording.current
      recording.current = null
      updateSay('idle')
      if (!active) return
      try {
        const audio = await active.stop() // also releases the microphone
        await flow.correct(audio)
      } catch (error) {
        if (mounted.current) setSayError(error)
      }
    }
  }

  return (
    <ShareView
      state={state}
      headingRef={heading}
      onChoose={flow.chooseSeverity}
      onShare={() => void flow.share()}
      onNotNow={flow.notNow}
      onBack={flow.backToSummary}
      onRetryLoad={() => void flow.load()}
      onRestart={onRestart}
      onHear={(slow) => {
        if (muted) setSoundOff(true)
        else void flow.speakSummary(slow)
      }}
      soundOff={soundOff}
      onOpenCorrection={flow.openCorrection}
      onCorrectionMode={flow.chooseCorrectionMode}
      onPickItem={flow.pickItem}
      onCorrect={(change) => void flow.correct(change)}
      onCloseCorrection={flow.closeCorrection}
      onSayToggle={() => void toggleSay()}
      sayTalk={sayTalk}
      sayError={sayError}
    />
  )
}

export function ShareView(props: ShareViewProps) {
  const { state, headingRef } = props
  switch (state.phase) {
    case 'loading':
    case 'load-failed':
      return <LoadingPage {...props} />
    case 'receipt':
      return state.receipt ? (
        <ReceiptPage receipt={state.receipt} headingRef={headingRef} onHome={props.onRestart} />
      ) : null
    case 'not-shared':
      return <NotSharedPage onBack={props.onBack} onHome={props.onRestart} headingRef={headingRef} />
    default:
      return state.summary ? <SummaryPage {...props} summary={state.summary} /> : null
  }
}

function LoadingPage({ state, headingRef, onRetryLoad, onRestart, onNotNow }: ShareViewProps) {
  const error = state.failure?.error
  const failed = state.phase === 'load-failed'
  return (
    <main className="screen">
      <p className="progress">{W.progress}</p>
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        {W.loadingTitle}
      </h1>
      <p className="status" role="status" aria-live="polite">
        {!failed && (
          <>
            <HourglassIcon className="icon" />
            <span>{W.putting}</span>
          </>
        )}
      </p>
      {failed && (
        <>
          <div className="alert" role="alert">
            <AlertIcon className="icon" />
            <p>{summaryErrorMessage(error)}</p>
            {needsRestart(error) ? (
              <button type="button" className="button button--primary" onClick={onRestart}>
                {W.startAgain}
              </button>
            ) : (
              <button type="button" className="button button--primary" onClick={onRetryLoad}>
                {W.tryAgain}
              </button>
            )}
          </div>
          <button type="button" className="button button--secondary not-now" onClick={onNotNow}>
            {W.notNow}
          </button>
        </>
      )}
    </main>
  )
}

function SummaryPage(props: ShareViewProps & { summary: CheckinSummary }) {
  const { state, summary, headingRef, onChoose, onShare, onNotNow, onRestart } = props
  const correcting = state.correction.step !== 'closed'
  const sending = state.phase === 'sending' || state.correction.sending
  const missing = missingSeverities(state)
  const enabled = canShare(state)
  const error = state.failure?.error
  // Codes the runtime needs a severity for but that are not in the item list (should not happen; never hide one).
  const orphanNeeds = state.needs.filter((code) => !summary.items.some((item) => item.term_code === code))

  return (
    <main className="screen">
      <p className="progress">{W.progress}</p>
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        {W.title}
      </h1>
      {summary.shared && <p className="note">{W.alreadyShared}</p>}

      {summary.spoken && (
        <div className="voice-controls">
          <button
            type="button"
            className="button button--secondary"
            aria-disabled={sending}
            onClick={() => !sending && (props.onHear ?? noop)(false)}
          >
            <SpeakerIcon className="icon" />
            <span className="button__label">{W.hearAgain}</span>
          </button>
          <button
            type="button"
            className="button button--secondary"
            aria-disabled={sending}
            onClick={() => !sending && (props.onHear ?? noop)(true)}
          >
            <SlowIcon className="icon" />
            <span className="button__label">{W.slower}</span>
          </button>
        </div>
      )}
      {summary.spoken && props.soundOff && <SoundOffNote />}
      {state.voiceFailure && <p className="note">{summaryVoiceMessage(state.voiceFailure.error)}</p>}

      <section className="summary card" aria-labelledby="told-heading">
        <h2 id="told-heading" className="subtitle">
          {W.toldHeading}
        </h2>
        {summary.items.length === 0 ? (
          <p className="lead">{NOTHING_TO_REPORT}</p>
        ) : (
          <ul className="items">
            {summary.items.map((item, i) => (
              <Item
                key={`${item.term_code}-${i}`}
                item={item}
                needsSeverity={state.needs.includes(item.term_code)}
                chosen={state.chosen[item.term_code]}
                disabled={sending}
                onChoose={onChoose}
              />
            ))}
          </ul>
        )}
        {orphanNeeds.map((code) => (
          <SeverityChoice
            key={code}
            termCode={code}
            label={itemLabel(summary.items, code)}
            chosen={state.chosen[code]}
            disabled={sending}
            onChoose={onChoose}
          />
        ))}
        {summary.unanswered_questions > 0 && (
          <p>{W.unanswered(summary.unanswered_questions)}</p>
        )}
      </section>

      {canCorrect(state) && !correcting && (
        <button
          type="button"
          className="button button--secondary button--huge"
          aria-disabled={sending}
          onClick={() => !sending && (props.onOpenCorrection ?? noop)()}
        >
          {W.changeOne}
        </button>
      )}
      {canCorrect(state) && correcting && <CorrectionPanel {...props} summary={summary} />}
      {!correcting && state.correction.failure && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{correctionErrorMessage(state.correction.failure.error)}</p>
        </div>
      )}

      <WhatWillBeShared summary={summary} />

      {state.failure && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{shareErrorMessage(error)}</p>
          {needsRestart(error) && (
            <button type="button" className="button button--primary" onClick={onRestart}>
              {W.startAgain}
            </button>
          )}
        </div>
      )}

      <p className="status" role="status" aria-live="polite" id="share-hint">
        {sending ? (
          <>
            <HourglassIcon className="icon" />
            <span>{W.sharing}</span>
          </>
        ) : missing.length > 0 ? (
          <span>{W.chooseHint}</span>
        ) : null}
      </p>

      {/* Nothing is sent before this tap (PV-04). */}
      <button
        type="button"
        className="button button--primary button--huge"
        aria-disabled={!enabled || state.correction.sending}
        aria-describedby="share-hint"
        onClick={() => enabled && !state.correction.sending && onShare()}
      >
        <ShareIcon className="icon" />
        <span>{sending ? W.sharing : W.share}</span>
      </button>
      <button
        type="button"
        className="button button--secondary not-now"
        aria-disabled={sending}
        onClick={() => !sending && onNotNow()}
      >
        {W.notNow}
      </button>
    </main>
  )
}

/** "Change one answer" (VC-08): say the change, or tap an item and pick the new answer. Only one change. */
function CorrectionPanel(props: ShareViewProps & { summary: CheckinSummary }) {
  const { state, summary } = props
  const { step, termCode, sending, failure } = state.correction
  const sayTalk = props.sayTalk ?? 'idle'
  const correct = props.onCorrect ?? noop
  const item = summary.items.find((it) => it.term_code === termCode)
  const error = props.sayError ?? failure?.error
  const close = (
    <button
      type="button"
      className="button button--secondary"
      aria-disabled={sending || sayTalk !== 'idle'}
      onClick={() => !sending && sayTalk === 'idle' && (props.onCloseCorrection ?? noop)()}
    >
      {W.keep}
    </button>
  )

  return (
    <section className="correction" aria-labelledby="change-heading">
      <h2 id="change-heading" className="subtitle">
        {W.changeOne}
      </h2>
      <p>{W.canChangeOne}</p>

      {step === 'menu' && (
        <div className="correction__choices">
          <button
            type="button"
            className="button button--primary button--huge"
            onClick={() => (props.onCorrectionMode ?? noop)('say')}
          >
            <MicIcon className="icon" /> {W.sayChange}
          </button>
          {summary.items.length > 0 && (
            <button
              type="button"
              className="button button--secondary button--huge"
              onClick={() => (props.onCorrectionMode ?? noop)('tap')}
            >
              {W.tapChange}
            </button>
          )}
        </div>
      )}

      {step === 'say' && (
        <>
          <p>{W.sayExample}</p>
          <button
            type="button"
            className={`button talk talk--${sending ? 'sending' : sayTalk}`}
            aria-disabled={sending || sayTalk === 'starting'}
            onClick={() => !sending && sayTalk !== 'starting' && (props.onSayToggle ?? noop)()}
          >
            {sending ? (
              <>
                <HourglassIcon className="icon icon--large" />
                <span>{W.changing}</span>
              </>
            ) : sayTalk === 'listening' ? (
              <>
                <StopIcon className="icon icon--large" />
                <span>{S.checkin.talk.listening}</span>
              </>
            ) : sayTalk === 'starting' ? (
              <>
                <MicIcon className="icon icon--large" />
                <span>{S.checkin.talk.starting}</span>
              </>
            ) : (
              <>
                <MicIcon className="icon icon--large" />
                <span>{W.tapAndSay}</span>
              </>
            )}
          </button>
          {summary.items.length > 0 && (
            <button
              type="button"
              className="button button--secondary"
              aria-disabled={sending || sayTalk !== 'idle'}
              onClick={() => !sending && sayTalk === 'idle' && (props.onCorrectionMode ?? noop)('tap')}
            >
              {W.tapInstead}
            </button>
          )}
        </>
      )}

      {step === 'pick' && (
        <fieldset className="choice">
          <legend className="choice__question">{W.whichOne}</legend>
          <div className="choice__buttons choice__buttons--column">
            {summary.items.map((it, i) => (
              <button
                key={`${it.term_code}-${i}`}
                type="button"
                className="button choice__button"
                onClick={() => (props.onPickItem ?? noop)(it.term_code)}
              >
                {it.label}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {step === 'item' && item && (
        <>
          <fieldset className="choice">
            <legend className="choice__question">{severityQuestion(item.label)}</legend>
            <div className="choice__buttons">
              {SEVERITIES.map((severity) => (
                <button
                  key={severity}
                  type="button"
                  className="button choice__button"
                  aria-disabled={sending}
                  onClick={() => !sending && correct({ term_code: item.term_code, severity })}
                >
                  {SEVERITY_WORDS[severity]}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset className="choice">
            <legend className="choice__question">{W.whenStart}</legend>
            <div className="choice__buttons choice__buttons--column">
              {ONSETS.map((onset) => (
                <button
                  key={onset}
                  type="button"
                  className="button choice__button"
                  aria-disabled={sending}
                  onClick={() => !sending && correct({ term_code: item.term_code, onset })}
                >
                  {ONSET_CHOICES[onset]}
                </button>
              ))}
            </div>
          </fieldset>
          <button
            type="button"
            className="button button--secondary button--huge"
            aria-disabled={sending}
            onClick={() => !sending && correct({ term_code: item.term_code, remove: true })}
          >
            {W.dontHave}
          </button>
        </>
      )}

      <p className="status" role="status" aria-live="polite">
        {sending && (
          <>
            <HourglassIcon className="icon" />
            <span>{W.changingSummary}</span>
          </>
        )}
      </p>
      {error !== undefined && error !== null && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{correctionErrorMessage(error)}</p>
        </div>
      )}
      {close}
    </section>
  )
}

function Item(props: {
  item: SummaryItem
  needsSeverity: boolean
  chosen: Severity | undefined
  disabled: boolean
  onChoose: (termCode: string, severity: Severity) => void
}) {
  const { item, needsSeverity } = props
  return (
    <li className="item">
      <p className="item__name">
        <strong>{item.label}</strong> <span className="tag">{W.forReview}</span>
      </p>
      {needsSeverity ? (
        <SeverityChoice
          termCode={item.term_code}
          label={item.label}
          chosen={props.chosen}
          disabled={props.disabled}
          onChoose={props.onChoose}
        />
      ) : (
        <p>{W.howBad(severityText(item.severity))}</p>
      )}
      <p>{onsetSentence(item.onset)}</p>
      {item.possible_link && <p className="item__flag">{POSSIBLE_LINK_TEXT}</p>}
    </li>
  )
}

/** "How bad is the rash?" with three big buttons. The choice shows as a tick and words, not colour alone. */
function SeverityChoice(props: {
  termCode: string
  label: string
  chosen: Severity | undefined
  disabled: boolean
  onChoose: (termCode: string, severity: Severity) => void
}) {
  const { termCode, chosen, disabled, onChoose } = props
  return (
    <fieldset className="choice">
      <legend className="choice__question">{severityQuestion(props.label)}</legend>
      <div className="choice__buttons">
        {SEVERITIES.map((severity) => {
          const on = chosen === severity
          return (
            <button
              key={severity}
              type="button"
              className={`button choice__button${on ? ' choice__button--on' : ''}`}
              aria-pressed={on}
              aria-disabled={disabled}
              onClick={() => !disabled && onChoose(termCode, severity)}
            >
              {on && <CheckIcon className="icon" />}
              {SEVERITY_WORDS[severity]}
            </button>
          )
        })}
      </div>
      <p className="choice__picked">{chosen ? W.youChose(SEVERITY_WORDS[chosen]) : W.notChosen}</p>
    </fieldset>
  )
}

function WhatWillBeShared({ summary }: { summary: CheckinSummary }) {
  const [showExact, setShowExact] = useState(false)
  const { share } = summary
  return (
    <section className="share-box card" aria-labelledby="share-heading">
      <h2 id="share-heading" className="subtitle">
        {B.heading}
      </h2>
      <p>
        <strong>{B.whoGetsIt}</strong> {share.destination}
      </p>
      <p>
        <strong>{B.onlyCoded}</strong> {B.onlyCodedRest}
      </p>
      {summary.items.length === 0 && <p>{B.noProblems}</p>}
      <ul className="parts">
        {sharedPartsText(share.fields).map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
      <section className="care-box" aria-labelledby="care-heading">
        <h3 id="care-heading" className="subtitle subtitle--small">
          {B.yourDoctor}
        </h3>
        {share.care ? (
          <>
            <p>
              <strong>{CARE_TEAM_SEALED}</strong>
            </p>
            <p>{B.insideSealed}</p>
            <ul className="parts">
              {careTeamPartsText(share.care.fields).map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
            {emergencyCopyText(share.care.emergency) && <p>{emergencyCopyText(share.care.emergency)}</p>}
          </>
        ) : (
          <p>{CARE_TEAM_OFF}</p>
        )}
      </section>
      <button
        type="button"
        className="button button--secondary"
        aria-expanded={showExact}
        aria-controls="exact-record"
        onClick={() => setShowExact((shown) => !shown)}
      >
        {showExact ? B.hideExact : B.showExact}
      </button>
      {showExact && (
        <div className="exact" id="exact-record">
          <p>
            <strong>{B.sentWith}</strong> <span className="mono">{`${share.method} ${share.url}`}</span>
          </p>
          <h3 className="subtitle subtitle--small">{B.fieldNames(share.fields.length)}</h3>
          <ul className="mono fields">
            {share.fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
          <h3 className="subtitle subtitle--small">{B.theRecord}</h3>
          {share.record ? (
            <pre className="mono record">{JSON.stringify(share.record, null, 2)}</pre>
          ) : (
            <p>{B.recordLater}</p>
          )}
          {share.care && (
            <>
              <h3 className="subtitle subtitle--small">{B.sealedForCare}</h3>
              <p>
                <strong>{B.sentWith}</strong> <span className="mono">{`${share.care.method} ${share.care.url}`}</span>
              </p>
              <p>
                <strong>{B.lockedFor}</strong> <span className="mono">{share.care.org_id}</span>
              </p>
              <h3 className="subtitle subtitle--small">{B.insideSealedCount(share.care.fields.length)}</h3>
              <ul className="mono fields">
                {share.care.fields.map((field) => (
                  <li key={field}>{field}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  )
}

function ReceiptPage({
  receipt,
  headingRef,
  onHome,
}: {
  receipt: EgressReceipt
  headingRef?: HeadingRef
  onHome: () => void
}) {
  const { status } = receipt
  const queued = status === 'queued'
  const time = queued
    ? { label: R.sentAt, value: R.notYet }
    : receipt.sent_at
      ? { label: status === 'failed' ? R.triedAt : R.sentAt, value: formatLocalTime(receipt.sent_at) }
      : null
  // The fields in plain words (the same wording as the summary); the exact field names follow below.
  const plainParts = status === 'failed' ? [] : sharedPartsText(receipt.fields_sent)
  return (
    <main className="screen">
      <p className="progress">{R.progress}</p>
      {/* Updated in place when a queued record is sent: announced, with no page change. */}
      <div className={`receipt-head receipt-head--${status}`} aria-live="polite">
        {status === 'sent' ? (
          <CheckIcon className="icon icon--large" />
        ) : status === 'queued' ? (
          <HourglassIcon className="icon icon--large" />
        ) : (
          <AlertIcon className="icon icon--large" />
        )}
        <h1 className="title receipt-head__title" tabIndex={-1} ref={headingRef}>
          {receiptStatusText(status)}
        </h1>
      </div>
      {status === 'queued' && <p className="lead">{QUEUED_EXPLANATION}</p>}
      {status === 'failed' && <p className="lead">{R.failedLead}</p>}
      {receipt.alert && (
        <p className="lead alert-line" aria-live="polite">
          {alertText(receipt.alert)}
        </p>
      )}
      {receiptEnvelopes(receipt).map((copy, i) => (
        <p key={`${copy.org_id}-${i}`} className="lead alert-line" aria-live="polite">
          {sealedCopyText(copy)}
        </p>
      ))}

      {plainParts.length > 0 && (
        <section className="card receipt-card" aria-labelledby="receipt-plain">
          <h2 id="receipt-plain" className="subtitle subtitle--small">
            {R.plainHeading(queued)}
          </h2>
          <ul className="parts parts--checked">
            {plainParts.map((text) => (
              <li key={text}>
                <CheckIcon className="icon" />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <dl className="receipt">
        <div>
          <dt>{queued ? R.willBeSentTo : R.sentTo}</dt>
          <dd>{receipt.destination}</dd>
        </div>
        {time && (
          <div>
            <dt>{time.label}</dt>
            <dd>{time.value}</dd>
          </div>
        )}
        <div>
          <dt>{R.recordNumber}</dt>
          <dd className="mono">{receipt.record_id}</dd>
        </div>
        {status === 'failed' && receipt.response_code !== null && (
          <div>
            <dt>{R.serviceAnswer}</dt>
            <dd>{R.code(receipt.response_code)}</dd>
          </div>
        )}
        <div>
          <dt>{R.whatSent(queued)}</dt>
          <dd>
            <ul className="mono fields">
              {receipt.fields_sent.map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ul>
          </dd>
        </div>
        <div>
          <dt>{R.fingerprint}</dt>
          <dd>
            <p className="mono fingerprint">{receipt.payload_sha256}</p>
            <p className="note">{R.fingerprintNote(queued)}</p>
          </dd>
        </div>
      </dl>

      {receiptEnvelopes(receipt).map((copy, i) => (
        <SealedCopyReceipt key={`${copy.org_id}-${i}`} copy={copy} index={i} />
      ))}

      <div className="closing">
        <CheckIcon className="icon icon--large" />
        <p className="closing__text">{R.thanks}</p>
      </div>
      <button type="button" className="button button--primary button--huge" onClick={onHome}>
        <BackIcon className="icon" />
        <span>{R.home}</span>
      </button>
    </main>
  )
}

/** A sent sealed copy: where it went, when, and its fingerprint (the network log has the same one). */
function SealedCopyReceipt({ copy, index }: { copy: CareEnvelope; index: number }) {
  const receipt = copy.receipt
  if (receipt === null || receipt.status !== 'sent') return null
  const headingId = `sealed-copy-${index}`
  return (
    <section className="care-receipt" aria-labelledby={headingId}>
      <h2 id={headingId} className="subtitle">
        {sealedCopyHeading(copy.link_type)}
      </h2>
      <dl className="receipt">
        <div>
          <dt>{R.sentTo}</dt>
          <dd>{sealedCopyDestination(copy)}</dd>
        </div>
        {receipt.sent_at && (
          <div>
            <dt>{R.sentAt}</dt>
            <dd>{formatLocalTime(receipt.sent_at)}</dd>
          </div>
        )}
        <div>
          <dt>{R.fingerprint}</dt>
          <dd>
            <p className="mono fingerprint">{receipt.payload_sha256}</p>
            <p className="note">{R.sealedFingerprintNote}</p>
          </dd>
        </div>
      </dl>
    </section>
  )
}

function NotSharedPage({
  onBack,
  onHome,
  headingRef,
}: {
  onBack: () => void
  onHome: () => void
  headingRef?: HeadingRef
}) {
  return (
    <main className="screen screen--done">
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        {R.nothingShared}
      </h1>
      <p className="lead">{R.thanks}</p>
      <button type="button" className="button button--secondary button--huge" onClick={onBack}>
        {R.backToSummary}
      </button>
      <button type="button" className="button button--primary button--huge" onClick={onHome}>
        <BackIcon className="icon" />
        <span>{R.home}</span>
      </button>
    </main>
  )
}
