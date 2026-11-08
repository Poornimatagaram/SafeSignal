// Which message the patient sees when something goes wrong. The words themselves live in src/strings.ts.
import { RuntimeError, type NotedSymptom } from './api.ts'
import { MicrophoneError } from './recorder.ts'
import { S } from './strings.ts'

const E = S.errors

export const RUNTIME_DOWN = E.runtimeDown

const SOMETHING_WRONG = E.somethingWrong

/** The runtime no longer knows this check-in (for example it was restarted). */
export const SESSION_LOST = E.sessionLost

/** True when the only way forward is to start a new check-in. */
export function needsRestart(error: unknown): boolean {
  return error instanceof RuntimeError && (error.kind === 'session-not-found' || error.kind === 'already-shared')
}

/** For problems opening today's check-in. */
export function startErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    if (error.kind === 'runtime-down') return RUNTIME_DOWN
    if (error.kind === 'questions-missing') return E.start.questionsMissing
  }
  return E.start.other
}

/** For problems putting together the end-of-check-in summary. Nothing has been shared. */
export function summaryErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    if (error.kind === 'runtime-down') return RUNTIME_DOWN
    if (error.kind === 'session-not-found') return SESSION_LOST
  }
  return E.summary
}

/** For problems after the "Share this" tap. Sharing again never sends twice. */
export function shareErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    switch (error.kind) {
      case 'runtime-down':
        return E.share.runtimeDown
      case 'needs-severity':
        return E.share.needsSeverity
      case 'record-refused':
        return E.share.recordRefused
      case 'already-shared':
        return E.share.alreadyShared
      case 'session-not-found':
        return SESSION_LOST
      default:
        break
    }
  }
  return E.share.other
}

/** For problems while recording or sending an answer. */
export function answerErrorMessage(error: unknown): string {
  if (error instanceof MicrophoneError) {
    switch (error.kind) {
      case 'blocked':
        return E.microphone.blocked
      case 'not-found':
        return E.microphone.notFound
      case 'busy':
        return E.microphone.busy
      case 'unsupported':
        return E.microphone.unsupported
      case 'failed':
        return E.microphone.failed
    }
  }
  if (error instanceof RuntimeError) {
    switch (error.kind) {
      case 'runtime-down':
        return RUNTIME_DOWN
      case 'speech-unavailable':
        return E.answer.speechUnavailable
      case 'not-understood':
        return E.answer.notUnderstood
      case 'empty-audio':
        return E.answer.emptyAudio
      case 'too-large':
        return E.answer.tooLarge
      case 'bad-format':
        return E.answer.badFormat
      case 'forbidden':
        return E.answer.forbidden
      case 'session-not-found':
        return SESSION_LOST
      case 'already-shared':
        return E.answer.alreadyShared
      default:
        return SOMETHING_WRONG
    }
  }
  return SOMETHING_WRONG
}

/** For a change to the summary that did not go through (VC-08). */
export function correctionErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    if (error.kind === 'correction-not-understood') return E.correction.notUnderstood
    if (error.kind === 'correction-used') return E.correction.used
    if (error.kind === 'session-not-found') return SESSION_LOST
  }
  if (error instanceof MicrophoneError || error instanceof RuntimeError) {
    if (error instanceof RuntimeError && error.kind === 'not-understood') return E.correction.notUnderstoodShort
    return answerErrorMessage(error)
  }
  return E.correction.other
}

/** For problems reading the summary out loud; it is still on screen. */
export function summaryVoiceMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
  if (error instanceof DOMException && error.name === 'NotAllowedError') return E.summaryVoice.tapToHear
  return E.summaryVoice.other
}

/** For problems loading the next question. */
export function questionErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
  if (error instanceof RuntimeError && error.kind === 'questions-missing') return startErrorMessage(error)
  return E.question
}

/** For problems speaking the question; the question is still on screen. */
export function voiceErrorMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
  if (error instanceof DOMException && error.name === 'NotAllowedError') return E.questionVoice.tapToHear
  return E.questionVoice.other
}

/** "Rash, moderate": the symptom in plain words, with its severity when known. Never a cause. */
export function symptomText(symptom: NotedSymptom): string {
  return S.plain.symptom(symptom.label, symptom.severity ?? null)
}

/** For problems loading "Who I share with". */
export function consentLoadMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
  return E.consentLoad
}

/** For a switch change that did not go through. */
export function consentChangeMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    if (error.kind === 'runtime-down') return RUNTIME_DOWN
    if (error.kind === 'consent-unavailable') return E.consentUnavailable
  }
  return E.consentChange
}

/** For "Save and send" on the setup page: the runtime's own plain reason when it refused (422). */
export function setupSaveMessage(error: unknown): string {
  if (error instanceof RuntimeError) {
    if (error.kind === 'runtime-down') return RUNTIME_DOWN
    if (error.kind === 'setup-refused') return error.detail ?? E.setupRefused
  }
  return E.setupSave
}

/** For problems reading "What this computer sent". Reading it never sends anything. */
export function networkLogMessage(error: unknown): string {
  if (error instanceof RuntimeError && error.kind === 'runtime-down') return RUNTIME_DOWN
  return E.networkLog
}
