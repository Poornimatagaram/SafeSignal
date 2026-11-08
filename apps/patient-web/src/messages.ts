// Every message the patient may see when something goes wrong, in plain words.
import { RuntimeError, type NotedSymptom } from './api.ts'
import { MicrophoneError } from './recorder.ts'

export const RUNTIME_DOWN =
  'The check-in helper on this computer is not running. Please ask your helper to start it, then try again.'

const SOMETHING_WRONG = 'Something went wrong. Please try again.'

/** The runtime no longer knows this check-in (for example it was restarted). */
export const SESSION_LOST = 'This check-in is no longer open on this computer. Please start the check-in again.'

/** True when the only way forward is to start a new check-in. */
export function needsRestart(error: unknown): boolean {
  return error instanceof RuntimeError && (error.kind === 'session-not-found' || error.kind === 'already-shared')
}

/** For problems opening today's check-in. */
export function startErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    if (error.kind === 'runtime-down') return RUNTIME_DOWN
    if (error.kind === 'questions-missing') {
      return "Today's questions are not on this computer yet. They are downloaded when this computer is online. Please check the internet connection, then tap Start check-in again."
    }
  }
  return 'I could not start the check-in. Please try again.'
}

/** For problems putting together the end-of-check-in summary. Nothing has been shared. */
export function summaryErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    if (error.kind === 'runtime-down') return RUNTIME_DOWN
    if (error.kind === 'session-not-found') return SESSION_LOST
  }
  return 'I could not put your summary together. Nothing was shared. Please try again.'
}

/** For problems after the "Share this" tap. Sharing again never sends twice. */
export function shareErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    switch (error.kind) {
      case 'runtime-down':
        return 'The check-in helper on this computer is not answering. Please ask your helper to start it, then tap Share this again. It will never be sent twice.'
      case 'needs-severity':
        return 'Please choose how bad each problem is, then tap Share this again.'
      case 'record-refused':
        return 'The privacy check on this computer stopped this record, so nothing was sent. Please tell your helper.'
      case 'already-shared':
        return 'This check-in was already shared. Nothing more was sent.'
      case 'session-not-found':
        return SESSION_LOST
      default:
        break
    }
  }
  return 'Something went wrong. Please tap Share this again. It will never be sent twice.'
}

/** For problems while recording or sending an answer. */
export function answerErrorMessage(error: unknown): string {
  if (error instanceof MicrophoneError) {
    switch (error.kind) {
      case 'blocked':
        return 'The microphone is blocked for this page. Please allow the microphone in the browser, then tap to answer again.'
      case 'not-found':
        return 'No microphone was found. Please check that a microphone is connected, then try again.'
      case 'busy':
        return 'The microphone is being used by another program. Please close that program, then try again.'
      case 'unsupported':
        return 'This browser cannot record your voice. Please use a recent version of Chrome, Edge, Firefox or Safari.'
      case 'failed':
        return 'The recording stopped by itself. Please tap to answer again.'
    }
  }
  if (error instanceof RuntimeError) {
    switch (error.kind) {
      case 'runtime-down':
        return RUNTIME_DOWN
      case 'speech-unavailable':
        return 'The speech helper on this computer is not ready yet, so I cannot understand answers. Please ask your helper to set it up.'
      case 'not-understood':
        return 'Sorry, I could not make out that answer. Please tap and try again.'
      case 'empty-audio':
        return 'I did not hear anything. Please tap the button, speak, then tap again when you are done.'
      case 'too-large':
        return 'That answer was too long to send. Please tap and give a shorter answer.'
      case 'bad-format':
        return 'This browser recorded the answer in a format I cannot use. Please try a recent version of Chrome, Edge, Firefox or Safari.'
      case 'forbidden':
        return 'This screen is not allowed to send answers. Please open it on the same computer as the check-in helper.'
      case 'session-not-found':
        return SESSION_LOST
      case 'already-shared':
        return 'This check-in has already been shared, so no more answers can be added. Please start a new check-in.'
      default:
        return SOMETHING_WRONG
    }
  }
  return SOMETHING_WRONG
}

/** For problems loading the next question. */
export function questionErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
  if (error instanceof RuntimeError && error.kind === 'questions-missing') return startErrorMessage(error)
  return 'I could not load the question. Please try again.'
}

/** For problems speaking the question; the question is still on screen. */
export function voiceErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    return 'Tap “Hear it again” to hear the question.'
  }
  return 'I cannot say the question out loud right now. Please read it on the screen.'
}

/** "Rash, moderate": the symptom in plain words, with its severity when known. Never a cause. */
export function symptomText(symptom: NotedSymptom): string {
  return symptom.severity ? `${symptom.label}, ${symptom.severity}` : symptom.label
}
