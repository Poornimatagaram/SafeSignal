import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { DISPLAY_NAME } from './config.ts'
import { createRuntimeClient, type CheckinSession, type Question, type TurnResult } from './api.ts'
import { createPlayer, type Player } from './player.ts'
import { startRecording, type ActiveRecording } from './recorder.ts'
import {
  answerErrorMessage,
  needsRestart,
  questionErrorMessage,
  startErrorMessage,
  voiceErrorMessage,
} from './messages.ts'
import { S } from './strings.ts'
import { Shell } from './Shell.tsx'
import { HomeView } from './HomeScreen.tsx'
import { bubblesAfterTurn, ChatThread, type Bubble } from './CheckinChat.tsx'
import { afterTurn, createQuestionVoice } from './questionFlow.ts'
import { createShareFlow, type ShareFlow } from './shareFlow.ts'
import { ShareScreen } from './ShareScreen.tsx'
import { createConsentFlow, type ConsentFlow } from './consentFlow.ts'
import { ConsentScreen } from './ConsentScreen.tsx'
import { createSetupFlow, type SetupFlow } from './setupFlow.ts'
import { SetupScreen } from './SetupScreen.tsx'
import { createNetworkLogFlow, type NetworkLogFlow } from './networkLog.ts'
import { NetworkLogScreen } from './NetworkLogScreen.tsx'
import { AlertIcon, ArrowIcon, HourglassIcon, MicIcon, SlowIcon, SpeakerIcon, StopIcon } from './Icons.tsx'

const C = S.checkin

const client = createRuntimeClient()

/** start -> question (one per survey question) -> share (summary, approval, receipt); start <-> consent <-> setup. */
type Screen = 'start' | 'question' | 'share' | 'consent' | 'setup' | 'network-log'
/** Push-to-talk is a toggle (tap to start, tap to stop): holding a button is hard with a hand tremor. */
type Talk = 'idle' | 'starting' | 'listening' | 'sending'
/**
 * A short kind line above the question: the runtime asked again more simply, or gave the question up (VC-05), or
 * the patient asked to hear it again or more slowly by voice (VC-07).
 */
type Notice = 'reask' | 'move-on' | 'repeat' | 'slower' | null

export default function App() {
  const [screen, setScreen] = useState<Screen>('start')
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  // The summary, approval and receipt; created after the last question. Its share() is the only path to approve.
  const [shareFlow, setShareFlow] = useState<ShareFlow | null>(null)
  const [question, setQuestion] = useState<Question | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<{ index: number; message: string } | null>(null)
  const [talk, setTalk] = useState<Talk>('idle')
  // The transcript lives only in this component's memory, and only until the next question.
  const [reply, setReply] = useState<TurnResult | null>(null)
  const [answerError, setAnswerError] = useState<{ message: string; restart: boolean } | null>(null)
  const [voiceNote, setVoiceNote] = useState<string | null>(null)
  const [voiceLoading, setVoiceLoading] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  // The conversation for the current question only (question, re-asks, Walter's words). Cleared on every question
  // change, like the transcript: Walter's words stay in memory no longer than one question.
  const [thread, setThread] = useState<Bubble[]>([])
  const say = useCallback((...bubbles: Bubble[]) => setThread((shown) => [...shown, ...bubbles]), [])
  // "Who I share with": created when opened from the start screen, disposed when leaving it.
  const [consentFlow, setConsentFlow] = useState<ConsentFlow | null>(null)
  // "Set up who I share with": created when opened from "Who I share with".
  const [setupFlow, setSetupFlow] = useState<SetupFlow | null>(null)
  // "What this computer sent" (PV-06): created when opened from the start screen.
  const [networkLogFlow, setNetworkLogFlow] = useState<NetworkLogFlow | null>(null)

  const session = useRef<CheckinSession | null>(null) // today's check-in; every answer is sent with its id
  const player = useRef<Player | null>(null)
  const recording = useRef<ActiveRecording | null>(null)
  const talkNow = useRef<Talk>('idle')
  // Question audio at its current wording (ask 0, 1 or 2), cached for "Hear it again" and "Slower".
  const voice = useRef(
    createQuestionVoice(client, (audio) => player.current?.play(audio) ?? Promise.resolve()),
  )
  const generation = useRef(0) // bumps on every question change; late results from an old question are dropped
  const mounted = useRef(true)
  const shareFlowNow = useRef<ShareFlow | null>(null) // disposed when leaving the share screen (stops receipt polling)

  const talkButton = useRef<HTMLButtonElement>(null)
  const nextButton = useRef<HTMLButtonElement>(null)

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
      shareFlowNow.current?.dispose()
    }
  }, [])

  // Leaving "Who I share with" stops watching a queued change (the runtime still sends it by itself).
  useEffect(() => () => consentFlow?.dispose(), [consentFlow])
  useEffect(() => () => setupFlow?.dispose(), [setupFlow])

  useEffect(() => () => networkLogFlow?.dispose(), [networkLogFlow])

  const openNetworkLog = () => {
    setNetworkLogFlow(createNetworkLogFlow(client))
    setScreen('network-log')
  }

  const closeNetworkLog = () => {
    setNetworkLogFlow(null)
    setScreen('start')
  }

  const openConsent = () => {
    setConsentFlow(createConsentFlow(client))
    setScreen('consent')
  }

  const openSetup = () => {
    setConsentFlow(null)
    setSetupFlow(createSetupFlow(client))
    setScreen('setup')
  }

  // Back to "Who I share with", loaded again so it shows what was just saved.
  const closeSetup = () => {
    setSetupFlow(null)
    openConsent()
  }

  const closeConsent = () => {
    setConsentFlow(null)
    setScreen('start')
  }

  const speak = useCallback(async (q: Question, slow: boolean) => {
    if (!player.current) return
    const gen = generation.current
    setVoiceNote(null)
    try {
      if (!voice.current.has(q, slow)) setVoiceLoading(true)
      // Never play a stale question, and never over the patient while they are answering.
      await voice.current.speak(q, slow, () => gen === generation.current && talkNow.current === 'idle')
    } catch (error) {
      if (gen === generation.current && mounted.current) setVoiceNote(voiceErrorMessage(error))
    } finally {
      if (gen === generation.current && mounted.current) setVoiceLoading(false)
    }
  }, [])

  const resetForQuestionChange = useCallback(() => {
    generation.current += 1
    voice.current.clear()
    player.current?.stop()
    setQuestion(null)
    setReply(null)
    setNotice(null)
    setThread([])
    setAnswerError(null)
    setVoiceNote(null)
    setVoiceLoading(false)
    setLoadError(null)
    return generation.current
  }, [])

  /** After the last question: show the summary. Nothing is shared until the patient taps "Share this". */
  const finish = useCallback(() => {
    resetForQuestionChange()
    setLoading(false)
    const current = session.current
    if (!current) return
    // The summary is read out loud on the same audio element "Start check-in" unlocked.
    const flow = createShareFlow(client, current.session_id, {
      play: (audio) => player.current?.play(audio) ?? Promise.resolve(),
      stop: () => player.current?.stop(),
    })
    shareFlowNow.current?.dispose()
    shareFlowNow.current = flow
    setShareFlow(flow)
    setScreen('share')
    void flow.load() // GET the summary only
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
        setThread([{ kind: 'question', text: next.text }])
        void speak(next, false)
      } catch (error) {
        if (gen === generation.current && mounted.current) setLoadError({ index, message: questionErrorMessage(error) })
      } finally {
        if (gen === generation.current && mounted.current) setLoading(false)
      }
    },
    [finish, resetForQuestionChange, speak],
  )

  const start = async () => {
    if (starting) return
    // This tap also unlocks audio playback for the rest of the check-in.
    if (!player.current) player.current = createPlayer(setSpeaking)
    player.current.unlock()
    setStartError(null)
    setStarting(true)
    try {
      const opened = await client.startSession()
      if (!mounted.current) return
      session.current = opened
      setScreen('question')
      void loadQuestion(0)
    } catch (error) {
      if (mounted.current) setStartError(startErrorMessage(error))
    } finally {
      if (mounted.current) setStarting(false)
    }
  }

  /** Back to the start screen with a fresh check-in (the runtime lost this one, or it was already shared). */
  const restart = () => {
    recording.current?.cancel()
    recording.current = null
    updateTalk('idle')
    resetForQuestionChange()
    setLoading(false)
    session.current = null
    shareFlowNow.current?.dispose()
    shareFlowNow.current = null
    setShareFlow(null)
    setStartError(null)
    setScreen('start')
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
      setNotice((shown) => (shown === 'repeat' || shown === 'slower' ? null : shown))
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
        setAnswerError({ message: answerErrorMessage(error), restart: false })
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
        const sessionId = session.current?.session_id ?? ''
        const result = await client.postTurn(sessionId, question.question_id, question.ask, audio)
        if (gen !== generation.current || !mounted.current) return
        const step = afterTurn(question, result)
        if (step.kind === 'reask') {
          // Same question, simpler wording: shown and spoken right away (Start already unlocked audio; no tap).
          generation.current += 1
          player.current?.stop()
          updateTalk('idle')
          setReply(null)
          setNotice('reask')
          setQuestion(step.question)
          void speak(step.question, false)
          say(...bubblesAfterTurn(result, step.kind, { text: step.question.text }))
        } else if (step.kind === 'command') {
          // "Say that again" / "Slower": not an answer and not a re-ask. Same wording, same ask; wait for the answer.
          player.current?.stop()
          updateTalk('idle')
          setReply(null)
          setNotice(step.command)
          void speak(step.question, step.slow)
          say(...bubblesAfterTurn(result, step.kind, { text: step.question.text, command: step.command }))
        } else if (step.kind === 'move-on') {
          setNotice('move-on')
          say(...bubblesAfterTurn(result, step.kind))
        } else {
          setNotice(null)
          setReply(result)
          say(...bubblesAfterTurn(result, step.kind))
        }
      } catch (error) {
        if (gen === generation.current && mounted.current) {
          setAnswerError({ message: answerErrorMessage(error), restart: needsRestart(error) })
        }
      } finally {
        if (mounted.current) updateTalk('idle')
      }
    }
    // 'starting' and 'sending': the button is marked disabled; ignore the tap.
  }

  const movingOn = notice === 'move-on'
  // "Next question" is the next step after a heard answer, and after a question given up (VC-05).
  const heard = (reply !== null && reply.transcript.trim() !== '') || movingOn
  const busy = talk !== 'idle'

  // Keyboard users land on the next thing to do.
  useEffect(() => {
    if (screen === 'question' && question && !heard) talkButton.current?.focus({ preventScroll: true })
  }, [screen, question, heard])
  useEffect(() => {
    if (heard) nextButton.current?.focus({ preventScroll: true })
  }, [heard])

  return <Shell>{renderScreen()}</Shell>

  function renderScreen() {
    if (screen === 'start') {
      return (
        <HomeView
          name={DISPLAY_NAME}
          hour={new Date().getHours()}
          starting={starting}
          startError={startError}
          onStart={() => void start()}
          onConsent={openConsent}
          onNetworkLog={openNetworkLog}
        />
      )
    }

    if (screen === 'network-log' && networkLogFlow) {
      return <NetworkLogScreen flow={networkLogFlow} onBack={closeNetworkLog} />
    }

    if (screen === 'consent' && consentFlow) {
      return <ConsentScreen flow={consentFlow} onBack={closeConsent} onSetup={openSetup} />
    }

    if (screen === 'setup' && setupFlow) {
      return <SetupScreen flow={setupFlow} onClose={closeSetup} />
    }

    if (screen === 'share' && shareFlow) {
      return <ShareScreen flow={shareFlow} onRestart={restart} />
    }

    const isLast = question !== null && question.index + 1 >= question.total
    const status: { text: string; icon: ReactNode } | null =
      talk === 'starting'
        ? { text: C.status.micStarting, icon: <HourglassIcon className="icon" /> }
        : talk === 'listening'
          ? { text: C.status.listening, icon: <span className="rec-dot" aria-hidden="true" /> }
          : talk === 'sending'
            ? { text: C.status.sending, icon: <HourglassIcon className="icon" /> }
            : loading
              ? { text: C.status.loading, icon: <HourglassIcon className="icon" /> }
              : voiceLoading
                ? { text: C.status.voiceLoading, icon: <HourglassIcon className="icon" /> }
                : speaking
                  ? { text: C.status.speaking, icon: <SpeakerIcon className="icon" /> }
                  : null

    return (
      <main className="screen screen--chat">
        <h1 className="progress">{question ? C.progress(question.index + 1, question.total) : C.progressNone}</h1>

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
              {C.tryAgain}
            </button>
          </div>
        )}

        {question && <ChatThread bubbles={thread} />}

        {question && voiceNote && <p className="note">{voiceNote}</p>}

        {question && answerError && (
          <div className="alert" role="alert">
            <AlertIcon className="icon" />
            <p>{answerError.message}</p>
            {answerError.restart && (
              <button type="button" className="button button--primary" onClick={restart}>
                {C.startAgain}
              </button>
            )}
          </div>
        )}

        {/* The one action sits at the bottom, always in reach. */}
        <div className="dock">
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
            <div className="voice-controls">
              <button
                type="button"
                className="button button--secondary"
                aria-disabled={busy}
                onClick={() => !busy && void speak(question, false)}
              >
                <SpeakerIcon className="icon" /> {C.hearAgain}
              </button>
              <button
                type="button"
                className="button button--secondary"
                aria-disabled={busy}
                onClick={() => !busy && void speak(question, true)}
              >
                <SlowIcon className="icon" /> {C.slowerButton}
              </button>
            </div>
          )}

          {question && !heard && (
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

          {question && (reply || movingOn) && (
            <button
              type="button"
              ref={nextButton}
              className={`button button--huge ${heard ? 'button--primary' : 'button--secondary'}`}
              aria-disabled={busy}
              onClick={() => !busy && next()}
            >
              {isLast ? C.finish : C.next} <ArrowIcon className="icon" />
            </button>
          )}
        </div>
      </main>
    )
  }
}

function TalkLabel({ talk }: { talk: Talk }) {
  switch (talk) {
    case 'listening':
      return (
        <>
          <StopIcon className="icon icon--large" />
          <span>{C.talk.listening}</span>
        </>
      )
    case 'starting':
      return (
        <>
          <MicIcon className="icon icon--large" />
          <span>{C.talk.starting}</span>
        </>
      )
    case 'sending':
      return (
        <>
          <HourglassIcon className="icon icon--large" />
          <span>{C.talk.sending}</span>
        </>
      )
    default:
      return (
        <>
          <MicIcon className="icon icon--large" />
          <span>{C.talk.idle}</span>
        </>
      )
  }
}

