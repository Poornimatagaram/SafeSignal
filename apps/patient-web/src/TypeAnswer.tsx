// "Or type your answer": a big text box and a big "Send" under the talk button. A typed answer goes to the runtime
// like a spoken one and comes back the same way. The words live only in this box (React memory) until they are sent;
// they are never put in browser storage.
import { useId } from 'react'
import { MAX_TYPED_ANSWER } from './api.ts'
import { S } from './strings.ts'
import { SendIcon } from './Icons.tsx'

const C = S.checkin

export interface TypeAnswerProps {
  text: string
  onChange: (text: string) => void
  onSend: () => void
  /** An answer is being recorded or sent: nothing can be sent now. */
  busy: boolean
}

/** "Send" works only with words in the box, and never while another answer is on its way or being recorded. */
export function canSendTyped(text: string, busy: boolean): boolean {
  return !busy && text.trim() !== ''
}

export function TypeAnswer({ text, onChange, onSend, busy }: TypeAnswerProps) {
  const id = useId()
  const enabled = canSendTyped(text, busy)
  return (
    <form
      className="type-answer"
      onSubmit={(event) => {
        event.preventDefault()
        if (enabled) onSend()
      }}
    >
      <label htmlFor={id} className="type-answer__label">
        {C.typeLabel}
      </label>
      {/* No spell check: some browsers send the words to an online spell checker. */}
      <textarea
        id={id}
        className="input type-answer__box"
        rows={2}
        maxLength={MAX_TYPED_ANSWER}
        autoComplete="off"
        spellCheck={false}
        value={text}
        onChange={(event) => onChange(event.target.value)}
      />
      <button type="submit" className="button button--primary type-answer__send" aria-disabled={!enabled}>
        <SendIcon className="icon" />
        <span className="button__label">{C.send}</span>
      </button>
    </form>
  )
}
