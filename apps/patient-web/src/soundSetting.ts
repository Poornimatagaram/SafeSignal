// "Sound off" is remembered for this browser tab only (sessionStorage), never longer, and never anything else: the
// only value ever written is "1" or "0" under one key. This is the one file allowed to touch browser storage
// (tests/privacy.test.ts checks that). Storage can be blocked (private windows): every access is guarded, and the
// sound is then simply on by default.

export const MUTED_KEY = 'patient-web.muted'

/** The parts of Storage this module uses (tests pass a fake one). */
export type SoundStorage = Pick<Storage, 'getItem' | 'setItem'>

function sessionStore(): SoundStorage | null {
  try {
    return globalThis.sessionStorage ?? null
  } catch {
    return null
  }
}

/** True when the patient turned the sound off earlier in this browser session. Default: sound on. */
export function readMuted(storage: SoundStorage | null = sessionStore()): boolean {
  try {
    return storage?.getItem(MUTED_KEY) === '1'
  } catch {
    return false
  }
}

/** Remember the choice for this browser session. Failing to remember it is fine. */
export function saveMuted(muted: boolean, storage: SoundStorage | null = sessionStore()): void {
  try {
    storage?.setItem(MUTED_KEY, muted ? '1' : '0')
  } catch {
    // Storage is blocked or full: the choice still holds until the page is closed.
  }
}
