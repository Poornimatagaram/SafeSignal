// The sound controls: "Mute" / "Unmute" at the top of every screen, and "Stop" beside it while something is being
// read out loud. Both only render; the player (src/player.ts) does the work.
import { S } from './strings.ts'
import { SpeakerIcon, SpeakerOffIcon, StopIcon } from './Icons.tsx'

const N = S.sound

export interface MuteToggleProps {
  muted: boolean
  onToggle: () => void
}

/** Pressed = the sound is off. The word says what a tap does. */
export function MuteToggle({ muted, onToggle }: MuteToggleProps) {
  return (
    <button type="button" className="button button--secondary sound-toggle" aria-pressed={muted} onClick={onToggle}>
      {muted ? <SpeakerOffIcon className="icon" /> : <SpeakerIcon className="icon" />}
      <span className="button__label">{muted ? N.unmute : N.mute}</span>
    </button>
  )
}

/** Shown only while a question or the summary is playing. */
export function StopButton({ onStop }: { onStop: () => void }) {
  return (
    <button type="button" className="button button--secondary" onClick={onStop}>
      <StopIcon className="icon" />
      <span className="button__label">{N.stop}</span>
    </button>
  )
}

/** "Sound is off. Tap Unmute to hear it." after "Repeat" or "Slower" while muted. */
export function SoundOffNote() {
  return (
    <p className="note" role="status">
      {N.offNote}
    </p>
  )
}
