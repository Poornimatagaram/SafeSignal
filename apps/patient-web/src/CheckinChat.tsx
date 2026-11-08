// The check-in as a conversation: each question is a bubble from the helper (and is spoken), Walter's answer is his
// own bubble, and a re-ask, "say that again" or "slower" is a bubble too. The thread holds ONE question only: it is
// cleared when the question changes, so Walter's words stay in memory no longer than before (src/App.tsx).
import { useEffect, useRef } from 'react'
import type { TurnResult, VoiceCommand } from './api.ts'
import { symptomText } from './messages.ts'
import { S } from './strings.ts'
import { HelperAvatar } from './Icons.tsx'

export type Bubble =
  /** The question at its current wording (spoken as it appears). */
  | { kind: 'question'; text: string }
  /** "Let me ask that more simply." just before the simpler wording (VC-05). */
  | { kind: 'reask' }
  /** "Saying it again" / "Saying it more slowly" (VC-07). */
  | { kind: 'command'; command: VoiceCommand }
  /** Walter's own words, shown on this screen only. */
  | { kind: 'answer'; words: string }
  /** What was noted from the answer: symptoms for review, never a cause. */
  | { kind: 'noted'; reply: TurnResult }
  /** The answer had no words in it. */
  | { kind: 'no-words' }
  /** "That's okay, let's move on." */
  | { kind: 'move-on' }

const C = S.checkin

export function ChatThread({ bubbles }: { bubbles: readonly Bubble[] }) {
  const end = useRef<HTMLLIElement>(null)
  // The newest bubble stays in view (no smooth scrolling: it can make people feel unwell).
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [bubbles.length])

  // The latest question is the one being asked; earlier wordings stay visible above it.
  const latestQuestion = bubbles.reduce((last, bubble, i) => (bubble.kind === 'question' ? i : last), -1)
  return (
    <ol className="chat" role="log" aria-live="polite" aria-label={C.conversation}>
      {bubbles.map((bubble, i) => (
        <BubbleItem key={i} bubble={bubble} current={i === latestQuestion} />
      ))}
      <li className="chat__end" ref={end} aria-hidden="true" />
    </ol>
  )
}

function BubbleItem({ bubble, current }: { bubble: Bubble; current: boolean }) {
  switch (bubble.kind) {
    case 'question':
      return (
        <li className={`bubble bubble--app bubble--question${current ? ' bubble--current' : ''}`}>
          <HelperAvatar className="bubble__avatar" />
          <p className="question">
            <span className="sr-only">{C.helperSays} </span>
            {bubble.text}
          </p>
        </li>
      )
    case 'reask':
      return (
        <li className="bubble bubble--app bubble--notice">
          <HelperAvatar className="bubble__avatar" />
          <p className="notice">{C.reask}</p>
        </li>
      )
    case 'command':
      return (
        <li className="bubble bubble--app bubble--small">
          <p className="note">{bubble.command === 'slower' ? C.slower : C.repeat}</p>
        </li>
      )
    case 'move-on':
      return (
        <li className="bubble bubble--app bubble--notice">
          <HelperAvatar className="bubble__avatar" />
          <p className="notice">{C.moveOn}</p>
        </li>
      )
    case 'answer':
      return (
        <li className="bubble bubble--me">
          <p className="said">
            <span className="sr-only">{C.youSaid} </span>
            {bubble.words}
          </p>
        </li>
      )
    case 'no-words':
      return (
        <li className="bubble bubble--app">
          <p className="said">{C.noWords}</p>
        </li>
      )
    case 'noted':
      return (
        <li className="bubble bubble--app bubble--noted">
          <SymptomNotes reply={bubble.reply} />
        </li>
      )
  }
}

/** Symptoms are shown as noted "for review", never as caused by anything. */
function SymptomNotes({ reply }: { reply: TurnResult }) {
  if (reply.symptoms === null || reply.extraction !== 'ok') {
    return <p className="noted">{C.notChecked}</p>
  }
  if (reply.symptoms.length === 0) {
    return <p className="noted">{C.noSymptoms}</p>
  }
  return (
    <div className="noted">
      <p>
        <strong>{C.notedForReview}</strong>
      </p>
      <ul>
        {reply.symptoms.map((symptom, i) => (
          <li key={`${symptom.term_code}-${i}`}>{symptomText(symptom)}</li>
        ))}
      </ul>
    </div>
  )
}

/** The bubbles that follow one answer, in order. Walter's words come first, then the helper's reply. */
export function bubblesAfterTurn(
  result: TurnResult,
  step: 'reask' | 'command' | 'move-on' | 'answered',
  next?: { text: string; command?: VoiceCommand },
): Bubble[] {
  const words = result.transcript.trim()
  const out: Bubble[] = words ? [{ kind: 'answer', words }] : []
  switch (step) {
    case 'reask':
      return [...out, { kind: 'reask' }, { kind: 'question', text: next?.text ?? '' }]
    case 'command':
      return next?.command ? [...out, { kind: 'command', command: next.command }] : out
    case 'move-on':
      return [...out, { kind: 'move-on' }]
    case 'answered':
      return words ? [...out, { kind: 'noted', reply: result }] : [{ kind: 'no-words' }]
  }
}
