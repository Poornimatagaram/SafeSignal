// The phone-sized frame every screen sits in: at most 430 px wide and centred. On a wide screen (the demo) it is
// drawn as a phone; on a real phone it is simply the whole screen. The sound controls sit in a bar at the top, so
// they are on every screen and never hidden in a menu: "Mute" / "Unmute" always, and "Stop" while something is being
// read out loud (a question or the summary).
import type { ReactNode } from 'react'
import { MuteToggle, StopButton, type MuteToggleProps } from './SoundControls.tsx'

export interface SoundBarProps extends MuteToggleProps {
  /** A question or the summary is playing: "Stop" shows. */
  playing?: boolean
  onStop?: () => void
}

export const SHELL_CLASS = 'app-shell'

export function Shell({ children, sound }: { children: ReactNode; sound?: SoundBarProps }) {
  return (
    <div className={SHELL_CLASS}>
      <div className="app-shell__viewport">
        {sound && (
          <header className="app-header">
            {sound.playing && sound.onStop && <StopButton onStop={sound.onStop} />}
            <MuteToggle muted={sound.muted} onToggle={sound.onToggle} />
          </header>
        )}
        {children}
      </div>
    </div>
  )
}
