// "What this computer sent" (PV-06): every request that left this computer, newest first, in plain words.
// `NetworkLogView` only renders state and forwards taps; reading the log sends nothing (src/networkLog.ts).
import { useEffect, useRef, useSyncExternalStore, type RefObject } from 'react'
import { networkLogMessage } from './messages.ts'
import {
  entryKey,
  entryOutcome,
  entryStatus,
  entryWhat,
  NOTHING_SENT,
  ONLY_THESE,
  type NetworkLogFlow,
  type NetworkLogState,
  type OrgContext,
} from './networkLog.ts'
import type { NetworkLogEntry } from './api.ts'
import { formatLocalTime } from './summaryText.ts'
import { S } from './strings.ts'
import { AlertIcon, BackIcon, CheckIcon, HourglassIcon, RefreshIcon } from './Icons.tsx'

const W = S.networkLog

export interface NetworkLogViewProps {
  state: NetworkLogState
  onRefresh: () => void
  onToggle: (key: string) => void
  onBack: () => void
  headingRef?: RefObject<HTMLHeadingElement | null>
}

export function NetworkLogScreen({ flow, onBack }: { flow: NetworkLogFlow; onBack: () => void }) {
  const state = useSyncExternalStore(flow.subscribe, flow.getState)
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    heading.current?.focus()
    void flow.load()
  }, [flow])

  return (
    <NetworkLogView
      state={state}
      headingRef={heading}
      onRefresh={() => void flow.load()}
      onToggle={flow.toggleDetails}
      onBack={onBack}
    />
  )
}

export function NetworkLogView({ state, onRefresh, onToggle, onBack, headingRef }: NetworkLogViewProps) {
  const busy = state.phase === 'loading' || state.refreshing
  return (
    <main className="screen">
      <h1 className="title" tabIndex={-1} ref={headingRef}>
        {W.title}
      </h1>
      <p className="lead">{ONLY_THESE}</p>

      <p className="status" role="status" aria-live="polite">
        {busy && (
          <>
            <HourglassIcon className="icon" />
            <span>{W.loading}</span>
          </>
        )}
      </p>

      {state.failure && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{networkLogMessage(state.failure.error)}</p>
        </div>
      )}

      {state.phase === 'ready' &&
        (state.entries.length === 0 ? (
          <p className="lead">{NOTHING_SENT}</p>
        ) : (
          <ol className="netlog">
            {state.entries.map((entry, i) => {
              const key = entryKey(entry, i)
              return (
                <LogRow
                  key={key}
                  id={key}
                  entry={entry}
                  orgs={state.orgs}
                  open={state.open.includes(key)}
                  onToggle={() => onToggle(key)}
                />
              )
            })}
          </ol>
        ))}

      <button
        type="button"
        className="button button--primary button--huge"
        aria-disabled={busy}
        onClick={() => !busy && onRefresh()}
      >
        <RefreshIcon className="icon" />
        <span>{state.phase === 'load-failed' ? W.tryAgain : W.refresh}</span>
      </button>
      <button type="button" className="button button--secondary button--huge" onClick={onBack}>
        <BackIcon className="icon" />
        <span>{W.back}</span>
      </button>
    </main>
  )
}

function LogRow(props: {
  id: string
  entry: NetworkLogEntry
  orgs: OrgContext | null
  open: boolean
  onToggle: () => void
}) {
  const { id, entry, orgs, open, onToggle } = props
  const outcome = entryOutcome(entry.response_code)
  const detailsId = `${id}-details`
  return (
    <li className="netlog__row">
      <p className="netlog__what">{entryWhat(entry, orgs)}</p>
      <p>{entry.sent_at ? formatLocalTime(entry.sent_at) : W.timeUnknown}</p>
      <p className={`netlog__status netlog__status--${outcome}`}>
        {outcome === 'accepted' ? (
          <CheckIcon className="icon" />
        ) : outcome === 'retry' ? (
          <HourglassIcon className="icon" />
        ) : outcome === 'refused' ? (
          <AlertIcon className="icon" />
        ) : null}
        <span>{entryStatus(entry.response_code)}</span>
      </p>
      <button
        type="button"
        className="button button--secondary"
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={onToggle}
      >
        {open ? W.hideDetails : W.showDetails}
      </button>
      {open && (
        <dl className="netlog__details" id={detailsId}>
          <div>
            <dt>{W.sentWith}</dt>
            <dd className="mono">{`${entry.method} ${entry.url}`}</dd>
          </div>
          {entry.response_code !== null && (
            <div>
              <dt>{W.answerCode}</dt>
              <dd>{entry.response_code}</dd>
            </div>
          )}
          <div>
            <dt>{entry.kind === 'config_fetch' ? W.askedWith : W.fieldNames}</dt>
            <dd>
              {entry.fields_sent.length === 0 ? (
                <p>{W.none}</p>
              ) : (
                <ul className="mono fields">
                  {entry.fields_sent.map((field) => (
                    <li key={field}>{field}</li>
                  ))}
                </ul>
              )}
            </dd>
          </div>
          {entry.payload_sha256 !== '' && (
            <div>
              <dt>{W.fingerprint}</dt>
              <dd className="mono fingerprint">{entry.payload_sha256}</dd>
            </div>
          )}
        </dl>
      )}
    </li>
  )
}
