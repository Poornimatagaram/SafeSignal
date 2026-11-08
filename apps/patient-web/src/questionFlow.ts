// The re-ask flow (VC-05) and the question voice, with no React in them (tests/reask.test.ts drives both).
//
// After each answer the runtime says what comes next: ask the SAME question again in simpler words (ask 1), then
// as choices or yes/no (ask 2), or move on. The screen trusts it, but never asks one question more than twice again.
import { MAX_ASK, type Question, type RuntimeClient, type TurnResult } from './api.ts'

export type AfterTurn =
  /** Ask the same question again: show "Let me ask that more simply." and speak `question` right away (no tap). */
  | { kind: 'reask'; question: Question }
  /** Today's flow: show what was heard, then "Next question". */
  | { kind: 'answered' }
  /** Given up after the re-asks: "That's okay, let's move on.", then the next question. */
  | { kind: 'move-on' }

export function afterTurn(question: Question, result: TurnResult): AfterTurn {
  const next = result.next
  if (next.action === 'reask') {
    // Guard: never past ask 2, and never back to the same or an earlier wording (that would loop).
    if (question.ask >= MAX_ASK || next.ask <= question.ask || next.ask > MAX_ASK) return { kind: 'move-on' }
    return { kind: 'reask', question: { ...question, ask: next.ask, text: next.text } }
  }
  return next.unanswered ? { kind: 'move-on' } : { kind: 'answered' }
}

export interface QuestionVoice {
  /** True when this wording is already fetched (no "getting ready" wait). */
  has(question: Question, slow: boolean): boolean
  /**
   * Fetch (once) and play the question at its current wording (`question.ask`). `canPlay` is checked after the
   * fetch: a stale question or a patient who started answering is never talked over. Resolves true when played.
   */
  speak(question: Question, slow: boolean, canPlay?: () => boolean): Promise<boolean>
  /** Forget fetched audio (on a new question). */
  clear(): void
}

export function createQuestionVoice(
  client: Pick<RuntimeClient, 'getQuestionAudio'>,
  play: (audio: Blob) => Promise<void>,
): QuestionVoice {
  const cache = new Map<string, Blob>() // question audio only, for "Hear it again"
  const key = (question: Question, slow: boolean) => `${question.index}:${question.ask}:${slow}`

  return {
    has: (question, slow) => cache.has(key(question, slow)),

    async speak(question, slow, canPlay = () => true) {
      const k = key(question, slow)
      let audio = cache.get(k)
      if (!audio) {
        audio = await client.getQuestionAudio(question.index, question.ask, slow)
        if (!canPlay()) return false
        cache.set(k, audio)
      }
      if (!canPlay()) return false
      await play(audio)
      return true
    },

    clear: () => cache.clear(),
  }
}
