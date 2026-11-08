// The re-ask flow (VC-05): the same question asked again more simply, spoken without a tap, at most twice, then
// moved on. Driven through the real API client against a mocked runtime, the way the screen drives it.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, type FetchLike, type Question, type TurnNext, type TurnResult } from '../src/api.ts'
import { afterTurn, createQuestionVoice } from '../src/questionFlow.ts'
import { BASE, json, SID } from './fixtures.ts'

const WORDING = [
  'How have you been feeling since yesterday?',
  'Have you felt any different in your body since yesterday?',
  'Since yesterday, do you feel better, the same, or worse?',
]

const QUESTION: Question = { index: 0, total: 3, question_id: 'q1', purpose: 'wellbeing', ask: 0, text: WORDING[0] }

function turn(rating: TurnResult['rating'], next: TurnNext): TurnResult {
  return { transcript: 'well, the garden, you know', symptoms: [], extraction: 'ok', rating, next }
}

const REASK_1 = turn('rambling', { action: 'reask', ask: 1, text: WORDING[1] })
const REASK_2 = turn('off_topic', { action: 'reask', ask: 2, text: WORDING[2] })
const GIVE_UP = turn('no_answer', { action: 'next', unanswered: true })

/** A fake runtime: answers turns from `turns` in order, and records every request. */
function fakeRuntime(turns: TurnResult[]) {
  const requests: { method: string; path: string; ask: string | null }[] = []
  const queue = [...turns]
  const fetchMock = vi.fn<FetchLike>(async (input, init) => {
    const url = new URL(input)
    const method = init?.method ?? 'GET'
    const ask = url.searchParams.get('ask')
    requests.push({ method, path: url.pathname, ask })
    if (method === 'POST' && url.pathname === '/checkin/sessions') return json({ session_id: SID, total: 3 }, 201)
    if (method === 'GET' && url.pathname === '/checkin/question') return json(QUESTION)
    if (method === 'GET' && url.pathname === '/checkin/question/audio') {
      return new Response(new Blob([`wav ask=${ask}`], { type: 'audio/wav' }), { status: 200 })
    }
    if (method === 'POST' && url.pathname === '/checkin/turn') return json(queue.shift())
    return json({ detail: 'not found' }, 404)
  })
  return { client: createRuntimeClient(BASE, fetchMock), requests }
}

/** A fake audio player: records what was played and every unlock (an unlock needs a tap). */
function fakePlayer() {
  const played: string[] = []
  return {
    played,
    unlock: vi.fn(),
    play: vi.fn(async (audio: Blob) => {
      played.push(await audio.text())
    }),
  }
}

describe('re-ask flow (VC-05)', () => {
  it('reask -> reask -> next(unanswered): each wording is fetched with its ask and played without a tap', async () => {
    const runtime = fakeRuntime([REASK_1, REASK_2, GIVE_UP])
    const player = fakePlayer()
    const voice = createQuestionVoice(runtime.client, player.play)
    const recording = new Blob(['x'], { type: 'audio/webm' })

    // The "Start check-in" tap: the only unlock.
    player.unlock()
    const session = await runtime.client.startSession()
    let question = (await runtime.client.getQuestion(0)) as Question
    await voice.speak(question, false)

    const shown: string[] = [question.text]
    const steps: string[] = []
    for (;;) {
      const result = await runtime.client.postTurn(session.session_id, question.question_id, question.ask, recording)
      const step = afterTurn(question, result)
      steps.push(step.kind)
      if (step.kind !== 'reask') break
      question = step.question
      shown.push(question.text)
      await voice.speak(question, false) // what the screen does at once, with no tap in between
    }

    expect(steps).toEqual(['reask', 'reask', 'move-on'])
    expect(shown).toEqual(WORDING)
    expect(question).toMatchObject({ index: 0, question_id: 'q1', ask: 2 })

    const audio = runtime.requests.filter((r) => r.path === '/checkin/question/audio').map((r) => r.ask)
    const turns = runtime.requests.filter((r) => r.path === '/checkin/turn').map((r) => r.ask)
    expect(audio).toEqual(['0', '1', '2'])
    expect(turns).toEqual(['0', '1', '2'])
    expect(player.played).toEqual(['wav ask=0', 'wav ask=1', 'wav ask=2'])
    expect(player.unlock).toHaveBeenCalledTimes(1)
  })

  it('"Hear it again" and "Slower" use the current wording', async () => {
    const runtime = fakeRuntime([REASK_1])
    const player = fakePlayer()
    const voice = createQuestionVoice(runtime.client, player.play)
    const result = await runtime.client.postTurn(SID, 'q1', 0, new Blob(['x']))
    const step = afterTurn(QUESTION, result)
    if (step.kind !== 'reask') throw new Error('expected a re-ask')

    await voice.speak(step.question, false)
    await voice.speak(step.question, false) // Hear it again: from the cache
    await voice.speak(step.question, true) // Slower
    const audio = runtime.requests.filter((r) => r.path === '/checkin/question/audio')
    expect(audio.map((r) => r.ask)).toEqual(['1', '1'])
    expect(player.played).toEqual(['wav ask=1', 'wav ask=1', 'wav ask=1'])
  })

  it('never plays over the patient or a stale question', async () => {
    const runtime = fakeRuntime([])
    const player = fakePlayer()
    const voice = createQuestionVoice(runtime.client, player.play)
    expect(await voice.speak(QUESTION, false, () => false)).toBe(false)
    expect(player.play).not.toHaveBeenCalled()
  })
})

describe('afterTurn', () => {
  const at = (ask: number): Question => ({ ...QUESTION, ask })

  it('moves on as today for a complete answer (and for older runtimes)', () => {
    expect(afterTurn(QUESTION, turn('complete', { action: 'next', unanswered: false }))).toEqual({ kind: 'answered' })
  })

  it('moves on kindly when the runtime gives the question up', () => {
    expect(afterTurn(at(2), GIVE_UP)).toEqual({ kind: 'move-on' })
  })

  it('asks the same question again with the new wording', () => {
    expect(afterTurn(at(1), REASK_2)).toEqual({ kind: 'reask', question: { ...QUESTION, ask: 2, text: WORDING[2] } })
  })

  it('never re-asks more than twice, even if the runtime asks for it', () => {
    expect(afterTurn(at(2), turn('rambling', { action: 'reask', ask: 3, text: 'again?' }))).toEqual({ kind: 'move-on' })
    expect(afterTurn(at(2), REASK_2)).toEqual({ kind: 'move-on' })
    expect(afterTurn(at(1), REASK_1)).toEqual({ kind: 'move-on' }) // same wording again would loop
    expect(afterTurn(at(0), turn('partial', { action: 'reask', ask: 3, text: 'x' }))).toEqual({ kind: 'move-on' })
  })
})

describe('the screen', () => {
  const app = readFileSync(fileURLToPath(new URL('../src/App.tsx', import.meta.url)), 'utf8')

  it('speaks the re-ask right after the answer, with the plain-words lines', () => {
    expect(app).toMatch(/step\.kind === 'reask'[\s\S]{0,400}void speak\(step\.question, false\)/)
    expect(app).toContain('Let me ask that more simply.')
    expect(app).toContain("That's okay, let's move on.")
  })
})
