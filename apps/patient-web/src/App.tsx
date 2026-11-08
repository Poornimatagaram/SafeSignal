import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { createRuntimeClient, type Question, type TurnResult } from './api.ts'
import { createPlayer, type Player } from './player.ts'
import { startRecording, type ActiveRecording } from './recorder.ts'
import { answerErrorMessage, questionErrorMessage, symptomText, voiceErrorMessage } from './messages.ts'
import { AlertIcon, ArrowIcon, CheckIcon, HourglassIcon, MicIcon, SlowIcon, SpeakerIcon, StopIcon } from './Icons.tsx'

const client = createRuntimeClient()

type Screen = 'start' | 'question' | 'done'
/** Push-to-talk is a toggle (tap to start, tap to stop): holding a button is hard with a hand tremor. */
type Talk = 'idle' | 'starting' | 'listening' | 'sending'

export default function App() {
  const [screen, setScreen] = useState<Screen>('start')
  const [question, setQuestion] = useState<Question | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<{ index: number; message: string } | null>(null)
  const [talk, setTalk] = useState<Talk>('idle')
  // The transcript lives only in this component's memory, and only until the next question.
  const [reply, setReply] = useState<TurnResult | null>(null)
  const [answerError, setAnswerError] = useState<string | null>(null)
  const [voiceNote, setVoiceNote] = useState<string | null>(null)
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [speaking, setSpeaking] = useState(false)

  const player = useRef<Player | null>(null)
  const recording = useRef<ActiveRecording | null>(null)
  const talkNow = useRef<Talk>('idle')
  const audioCache = useRef(new Map<string, Blob>()) // question audio only, for "Hear it again"
  const generation = useRef(0) // bumps on every question change; late results from an old question are dropped
  const mounted = useRef(true)

  const talkButton = useRef<HTMLButtonElement>(null)
  const nextButton = useRef<HTMLButtonElement>(null)
  const doneHeading = useRef<HTMLHeadingElement>(null)

  const updateTalk = useCallback((next: Talk) => {
    talkNow.current = next
    setTalk(next)
  }, [])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      recording.current?.cancel()
      recording.current = null
      player.current?.dispose()
      player.current = null
    }
  }, [])

  const speak = useCallback(async (q: Question, slow: boolean) => {
    const audioPlayer = player.current
    if (!audioPlayer) return
    const gen = generation.current
    const key = `${q.index}:${q.ask}:${slow}`
    setVoiceNote(null)
    try {
      let audio = audioCache.current.get(key)
      if (!audio) {
        setVoiceLoading(true)
        audio = await client.getQuestionAudio(q.index, q.ask, slow)
        if (gen !== generation.current) return
        audioCache.current.set(key, audio)
      }
      // Never play over the patient while they are answering.
      if (talkNow.current !== 'idle') return
      await audioPlayer.play(audio)
    } catch (error) {
      if (gen === generation.current && mounted.current) setVoiceNote(voiceErrorMessage(error))
    } finally {
      if (gen === generation.current && mounted.current) setVoiceLoading(false)
    }
  }, [])

  const resetForQuestionChange = useCallback(() => {
    generation.current += 1
    audioCache.current.clear()
    player.current?.stop()
    setQuestion(null)
    setReply(null)
    setAnswerError(null)
    setVoiceNote(null)
    setVoiceLoading(false)
    setLoadError(null)
    return generation.current
  }, [])

  const finish = useCallback(() => {
    resetForQuestionChange()
    setLoading(false)
    setScreen('done')
  }, [resetForQuestionChange])

  const loadQuestion = useCallback(
    async (index: number) => {
      const gen = resetForQuestionChange()
      setLoading(true)
      try {
        const next = await client.getQuestion(index, 0)
        if (gen !== generation.current || !mounted.current) return
        if (!next) {
          finish()
          return
        }
        setQuestion(next)
        void speak(next, false)
      } catch (error) {
        if (gen === generation.current && mounted.current) setLoadError({ index, message: questionErrorMessage(error) })
      } finally {
        if (gen === generation.current && mounted.current) setLoading(false)
      }
    },
    [finish, resetForQuestionChange, speak],
  )

  const start = () => {
    // This tap also unlocks audio playback for the rest of the check-in.
    if (!player.current) player.current = createPlayer(setSpeaking)
    player.current.unlock()
    setScreen('question')
    void loadQuestion(0)
  }

  const next = () => {
    if (!question) return
    if (question.index + 1 >= question.total) finish()
    else void loadQuestion(question.index + 1)
  }

  const toggleTalk = async () => {
    if (!question) return
    if (talkNow.current === 'idle') {
      player.current?.stop()
      setAnswerError(null)
      setReply(null)
      updateTalk('starting')
      try {
        const active = await startRecording()
        if (!mounted.current) {
          active.cancel()
          return
        }
        recording.current = active
        updateTalk('listening')
      } catch (error) {
        if (!mounted.current) return
        updateTalk('idle')
        setAnswerError(answerErrorMessage(error))
      }
      return
    }

    if (talkNow.current === 'listening') {
      // Only this tap ends the answer: long pauses never do (VC-03).
      const active = recording.current
      recording.current = null
      if (!active) {
        updateTalk('idle')
        return
      }
      updateTalk('sending')
      const gen = generation.current
      try {
        const audio = await active.stop() // also releases the microphone
        const result = await client.postTurn(question.question_id, question.ask, audio)
        if (gen === generation.current && mounted.current) setReply(result)
      } catch (error) {
        if (gen === generation.current && mounted.current) setAnswerError(answerErrorMessage(error))
      } finally {
        if (mounted.current) updateTalk('idle')
      }
    }
    // 'starting' and 'sending': the button is marked disabled; ignore the tap.
  }

  const heard = reply !== null && reply.transcript.trim() !== ''
  const busy = talk !== 'idle'

  // Keyboard users land on the next thing to do.
  useEffect(() => {
    if (screen === 'question' && question && !heard) talkButton.current?.focus({ preventScroll: true })
  }, [screen, question, heard])
  useEffect(() => {
    if (heard) nextButton.current?.focus({ preventScroll: true })
  }, [heard])
  useEffect(() => {
    if (screen === 'done') doneHeading.current?.focus({ preventScroll: true })
  }, [screen])

  if (screen === 'start') {
    return (
      <main className="screen screen--start">
        <h1 className="title">Your daily check-in</h1>
        <p className="lead">I will ask you a few short questions out loud. Answer in your own words.</p>
        <p className="lead">Your voice stays on this computer.</p>
        <button type="button" className="button button--primary button--huge" onClick={start}>
          Start check-in
        </button>
      </main>
    )
  }

  if (screen === 'done') {
    return (
      <main className="screen screen--done">
        <CheckIcon className="icon icon--huge" />
        <h1 className="title" tabIndex={-1} ref={doneHeading}>
          Thank you, that's all for today.
        </h1>
      </main>
    )
  }

  const isLast = question !== null && question.index + 1 >= question.total
  const status: { text: string; icon: ReactNode } | null =
    talk === 'starting'
      ? { text: 'Getting the microphone ready…', icon: <HourglassIcon className="icon" /> }
      : talk === 'listening'
        ? { text: 'I am listening. Take your time; pauses are fine.', icon: <span className="rec-dot" aria-hidden="true" /> }
        : talk === 'sending'
          ? { text: 'Thinking about your answer…', icon: <HourglassIcon className="icon" /> }
          : loading
            ? { text: 'Getting the question…', icon: <HourglassIcon className="icon" /> }
            : voiceLoading
              ? { text: 'Getting the question ready to play…', icon: <HourglassIcon className="icon" /> }
              : speaking
                ? { text: 'Reading the question out loud…', icon: <SpeakerIcon className="icon" /> }
                : null

  return (
    <main className="screen">
      <p className="progress">{question ? `Question ${question.index + 1} of ${question.total}` : 'Daily check-in'}</p>

      {loadError && (
        <div className="alert" role="alert">
          <AlertIcon className="icon" />
          <p>{loadError.message}</p>
          <button
            type="button"
            className="button button--primary"
            autoFocus
            onClick={() => void loadQuestion(loadError.index)}
          >
            Try again
          </button>
        </div>
      )}

      {question && <h1 className="question">{question.text}</h1>}

      {question && (
        <div className="voice-controls">
          <button
            type="button"
            className="button button--secondary"
            aria-disabled={busy}
            onClick={() => !busy && void speak(question, false)}
          >
            <SpeakerIcon className="icon" /> Hear it again
          </button>
          <button
            type="button"
            className="button button--secondary"
            aria-disabled={busy}
            onClick={() => !busy && void speak(question, true)}
          >
            <SlowIcon className="icon" /> Slower
          </button>
        </div>
      )}

      {/* One live region, always present, so screen readers announce every change. */}
      <p className="status" role="status" aria-live="polite">
        {status && (
          <>
            {status.icon}
            <span>{status.text}</span>
          </>
        )}
      </p>

      {question && (
        <>
          {voiceNote && <p className="note">{voiceNote}</p>}

          {reply && <Reply reply={reply} />}

          {answerError && (
            <div className="alert" role="alert">
              <AlertIcon className="icon" />
              <p>{answerError}</p>
            </div>
          )}

          {!heard && (
            <button
              type="button"
              ref={talkButton}
              className={`button talk talk--${talk}`}
              aria-disabled={talk === 'starting' || talk === 'sending'}
              onClick={() => void toggleTalk()}
            >
              <TalkLabel talk={talk} />
            </button>
          )}

          {reply && (
            <button
              type="button"
              ref={nextButton}
              className={`button button--huge ${heard ? 'button--primary' : 'button--secondary'}`}
              aria-disabled={busy}
              onClick={() => !busy && next()}
            >
              {isLast ? 'Finish check-in' : 'Next question'} <ArrowIcon className="icon" />
            </button>
          )}
        </>
      )}
    </main>
  )
}

function TalkLabel({ talk }: { talk: Talk }) {
  switch (talk) {
    case 'listening':
      return (
        <>
          <StopIcon className="icon icon--large" />
          <span>Listening… tap when you're done</span>
        </>
      )
    case 'starting':
      return (
        <>
          <MicIcon className="icon icon--large" />
          <span>Getting ready…</span>
        </>
      )
    case 'sending':
      return (
        <>
          <HourglassIcon className="icon icon--large" />
          <span>Thinking…</span>
        </>
      )
    default:
      return (
        <>
          <MicIcon className="icon icon--large" />
          <span>Tap to answer</span>
        </>
      )
  }
}

function Reply({ reply }: { reply: TurnResult }) {
  const words = reply.transcript.trim()
  return (
    <section className="reply" aria-label="Your answer">
      {words ? (
        <p className="said">
          <strong>You said:</strong> “{words}”
        </p>
      ) : (
        <p className="said">I did not catch any words. Tap to answer again, or go on to the next question.</p>
      )}
      {words && <SymptomNotes reply={reply} />}
    </section>
  )
}

/** Symptoms are shown as noted "for review", never as caused by anything. */
function SymptomNotes({ reply }: { reply: TurnResult }) {
  if (reply.symptoms === null || reply.extraction !== 'ok') {
    return <p className="noted">I could not check this answer for symptoms right now.</p>
  }
  if (reply.symptoms.length === 0) {
    return <p className="noted">No symptoms noted.</p>
  }
  return (
    <div className="noted">
      <p>
        <strong>Noted for review:</strong>
      </p>
      <ul>
        {reply.symptoms.map((symptom, i) => (
          <li key={`${symptom.term_code}-${i}`}>{symptomText(symptom)}</li>
        ))}
      </ul>
    </div>
  )
}
