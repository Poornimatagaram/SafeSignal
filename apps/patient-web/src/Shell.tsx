// The phone-sized frame every screen sits in: at most 430 px wide and centred. On a wide screen (the demo) it is
// drawn as a phone; on a real phone it is simply the whole screen.
import type { ReactNode } from 'react'

export const SHELL_CLASS = 'app-shell'

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className={SHELL_CLASS}>
      <div className="app-shell__viewport">{children}</div>
    </div>
  )
}
