// The end of the check-in: summary, approve-before-share (PV-04) and the egress receipt (PV-05).
// `ShareView` only renders state and forwards taps; every request goes through the ShareFlow (src/shareFlow.ts).
import { useEffect, useRef, useState, useSyncExternalStore, type RefObject } from 'react'
import { SEVERITIES, type CheckinSummary, type EgressReceipt, type Severity, type SummaryItem } from './api.ts'
import { canShare, missingSeverities, type ShareFlow, type SharePhase, type ShareState } from './shareFlow.ts'
import { needsRestart, shareErrorMessage, summaryErrorMessage } from './messages.ts'
import {
  formatLocalTime,
  itemLabel,
  NOTHING_TO_REPORT,
  onsetSentence,
  receiptStatusText,
  severityQuestion,
  severityText,
  SEVERITY_WORDS,
  sharedPartsText,
} from './summaryText.ts'
import { AlertIcon, CheckIcon, HourglassIcon } from './Icons.tsx'

type HeadingRef = RefObject<HTMLHeadingElement | null>

export interface ShareViewProps {
  state: ShareState
  onChoose: (termCode: string, severity: Severity) => void
  onShare: () => void
  onNotNow: () => void
  onBack: () => void
  onRetryLoad: () => void
  onRestart: () => void
  headingRef?: HeadingRef
}

/** Which page is showing; focus moves to its heading only when this changes. */
function pageOf(phase: SharePhase): string {
  if (phase === 'sending') return 'review'
  if (phase === 'load-failed') return 'loading'
  return phase
}

export function ShareScreen({ flow, onRestart }: { flow: ShareFlow; onRestart: () => void }) {
  const state = useSyncExternalStore(flow.subscribe, flow.getState)
  const heading = useRef<HTMLHeadingElement>(null)
  const page = pageOf(state.phase)

  // Keyboard and screen-reader users land on each new page's heading.
  useEffect(() => {
    heading.current?.focus()
  }, [page])

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
      return state.receipt ? <ReceiptPage receipt={state.receipt} headingRef={headingRef} /> : null
    case 'not-shared':
      return <NotSharedPage onBack={props.onBack} headingRef={headingRef} />
    default:
      return state.summary ? <SummaryPage {...props} summary={state.summary} /> : null
  }
}

function LoadingPage({ state, headingRef, onRetryLoad, onRestart, onNotNow }: ShareViewProps) {
  const error = state.failure?.error
  const failed = state.phase === 'load-failed'
  return (
    <main className="screen">
      <p className="progress">End of check-in</p>
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        Your summary
      </h1>
      <p className="status" role="status" aria-live="polite">
        {!failed && (
          <>
            <HourglassIcon className="icon" />
            <span>Putting your summary together…</span>
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
                Start again
              </button>
            ) : (
              <button type="button" className="button button--primary" onClick={onRetryLoad}>
                Try again
              </button>
            )}
          </div>
          <button type="button" className="button button--secondary not-now" onClick={onNotNow}>
            Not now
          </button>
        </>
      )}
    </main>
  )
}

function SummaryPage(props: ShareViewProps & { summary: CheckinSummary }) {
  const { state, summary, headingRef, onChoose, onShare, onNotNow, onRestart } = props
  const sending = state.phase === 'sending'
  const missing = missingSeverities(state)
  const enabled = canShare(state)
  const error = state.failure?.error
  // Codes the runtime needs a severity for but that are not in the item list (should not happen; never hide one).
  const orphanNeeds = state.needs.filter((code) => !summary.items.some((item) => item.term_code === code))

  return (
    <main className="screen">
      <p className="progress">End of check-in</p>
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        Your summary
      </h1>
      {summary.shared && <p className="note">You have already shared this check-in.</p>}

      <section className="summary" aria-labelledby="told-heading">
        <h2 id="told-heading" className="subtitle">
          What you told me
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
          <p>
            {summary.unanswered_questions === 1
              ? '1 question had no answer. That is fine.'
              : `${summary.unanswered_questions} questions had no answer. That is fine.`}
          </p>
        )}
      </section>

      <WhatWillBeShared summary={summary} />

      {state.failure && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{shareErrorMessage(error)}</p>
          {needsRestart(error) && (
            <button type="button" className="button button--primary" onClick={onRestart}>
              Start again
            </button>
          )}
        </div>
      )}

      <p className="status" role="status" aria-live="polite" id="share-hint">
        {sending ? (
          <>
            <HourglassIcon className="icon" />
            <span>Sharing…</span>
          </>
        ) : missing.length > 0 ? (
          <span>Choose how bad each problem is, then tap Share this.</span>
        ) : null}
      </p>

      {/* Nothing is sent before this tap (PV-04). */}
      <button
        type="button"
        className="button button--primary button--huge"
        aria-disabled={!enabled}
        aria-describedby="share-hint"
        onClick={() => enabled && onShare()}
      >
        {sending ? 'Sharing…' : 'Share this'}
      </button>
      <button
        type="button"
        className="button button--secondary not-now"
        aria-disabled={sending}
        onClick={() => !sending && onNotNow()}
      >
        Not now
      </button>
    </main>
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
        <strong>{item.label}</strong> <span className="tag">For review</span>
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
        <p>How bad: {severityText(item.severity)}</p>
      )}
      <p>{onsetSentence(item.onset)}</p>
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
      <p className="choice__picked">{chosen ? `You chose: ${SEVERITY_WORDS[chosen]}` : 'Not chosen yet'}</p>
    </fieldset>
  )
}

function WhatWillBeShared({ summary }: { summary: CheckinSummary }) {
  const [showExact, setShowExact] = useState(false)
  const { share } = summary
  return (
    <section className="share-box" aria-labelledby="share-heading">
      <h2 id="share-heading" className="subtitle">
        What will be shared
      </h2>
      <p>
        <strong>Who gets it:</strong> {share.destination}
      </p>
      <p>
        <strong>Only coded answers:</strong> no name, no words you said, no recording.
      </p>
      {summary.items.length === 0 && <p>It tells them you had no new problems.</p>}
      <ul className="parts">
        {sharedPartsText(share.fields).map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
      <button
        type="button"
        className="button button--secondary"
        aria-expanded={showExact}
        aria-controls="exact-record"
        onClick={() => setShowExact((shown) => !shown)}
      >
        {showExact ? 'Hide exactly what is sent' : 'Show exactly what is sent'}
      </button>
      {showExact && (
        <div className="exact" id="exact-record">
          <p>
            <strong>Sent with:</strong> <span className="mono">{`${share.method} ${share.url}`}</span>
          </p>
          <h3 className="subtitle subtitle--small">Field names ({share.fields.length})</h3>
          <ul className="mono fields">
            {share.fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
          <h3 className="subtitle subtitle--small">The record</h3>
          {share.record ? (
            <pre className="mono record">{JSON.stringify(share.record, null, 2)}</pre>
          ) : (
            <p>
              The record is completed with your answers to “How bad” when you tap Share this. The receipt then shows
              its fingerprint.
            </p>
          )}
        </div>
      )}
    </section>
  )
}

function ReceiptPage({ receipt, headingRef }: { receipt: EgressReceipt; headingRef?: HeadingRef }) {
  const { status } = receipt
  const time =
    status === 'queued'
      ? { label: 'Sent at', value: 'Not yet: it is waiting for the internet' }
      : receipt.sent_at
        ? { label: status === 'failed' ? 'Tried at' : 'Sent at', value: formatLocalTime(receipt.sent_at) }
        : null
  return (
    <main className="screen">
      <p className="progress">Receipt</p>
      <div className={`receipt-head receipt-head--${status}`}>
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
      {status === 'failed' && (
        <p className="lead">The safety team's service did not accept this record. Please tell your helper.</p>
      )}

      <dl className="receipt">
        <div>
          <dt>{status === 'queued' ? 'Will be sent to' : 'Sent to'}</dt>
          <dd>{receipt.destination}</dd>
        </div>
        {time && (
          <div>
            <dt>{time.label}</dt>
            <dd>{time.value}</dd>
          </div>
        )}
        <div>
          <dt>Record number</dt>
          <dd className="mono">{receipt.record_id}</dd>
        </div>
        {status === 'failed' && receipt.response_code !== null && (
          <div>
            <dt>Answer from the service</dt>
            <dd>Code {receipt.response_code}</dd>
          </div>
        )}
        <div>
          <dt>{status === 'queued' ? 'What will be sent' : 'What was sent'}: coded answers only</dt>
          <dd>
            <ul className="mono fields">
              {receipt.fields_sent.map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ul>
          </dd>
        </div>
        <div>
          <dt>Fingerprint</dt>
          <dd>
            <p className="mono fingerprint">{receipt.payload_sha256}</p>
            <p className="note">
              This code is a fingerprint of exactly what {status === 'queued' ? 'will be' : 'was'} sent. It matches the
              entry in this computer's network log.
            </p>
          </dd>
        </div>
      </dl>

      <div className="closing">
        <CheckIcon className="icon icon--large" />
        <p className="closing__text">Thank you, that's all for today.</p>
      </div>
    </main>
  )
}

function NotSharedPage({ onBack, headingRef }: { onBack: () => void; headingRef?: HeadingRef }) {
  return (
    <main className="screen screen--done">
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        Nothing was shared.
      </h1>
      <p className="lead">Thank you, that's all for today.</p>
      <button type="button" className="button button--secondary" onClick={onBack}>
        Go back to my summary
      </button>
    </main>
  )
}
