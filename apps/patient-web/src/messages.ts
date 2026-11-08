// Every message the patient may see when something goes wrong, in plain words.
import { RuntimeError, type NotedSymptom } from './api.ts'
import { MicrophoneError } from './recorder.ts'

export const RUNTIME_DOWN =
  'The check-in helper on this computer is not running. Please ask your helper to start it, then try again.'

const SOMETHING_WRONG = 'Something went wrong. Please try again.'

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
      default:
        return SOMETHING_WRONG
    }
  }
  return SOMETHING_WRONG
}

/** For problems loading the next question. */
export function questionErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
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
