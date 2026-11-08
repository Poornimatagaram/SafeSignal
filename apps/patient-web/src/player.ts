// Plays the question audio that the runtime speaks with local text-to-speech.
// One audio element is reused for the whole check-in: unlocking it inside the "Start check-in" tap lets later
// questions play automatically, even in browsers that only allow sound after a tap on that same element.

export interface Player {
  /** Call inside a tap handler: plays a moment of silence so later playback is allowed. */
  unlock(): void
  /**
   * Play one WAV blob, replacing whatever is playing. Rejects if the browser refuses to play. While muted it plays
   * nothing and resolves at once (nothing ever plays by itself while the sound is off).
   */
  play(audio: Blob): Promise<void>
  /** Stop playback at once and go back to the start (the "Stop" button, or the patient starts answering). */
  stop(): void
  /** Sound off (true) stops anything playing now; sound on never replays anything by itself. */
  setMuted(muted: boolean): void
  isMuted(): boolean
  /** True while a question or the summary is being read out loud ("Stop" shows only then). */
  isPlaying(): boolean
  /** Called with true when playback starts and false when it stops, ends or fails. Returns an unsubscribe. */
  subscribe(listener: (playing: boolean) => void): () => void
  /** Release the element and any object URL. */
  dispose(): void
}

/** The parts of an HTMLAudioElement the player uses (tests pass a fake one). */
export type AudioLike = Pick<
  HTMLAudioElement,
  'play' | 'pause' | 'load' | 'addEventListener' | 'removeAttribute' | 'src' | 'preload' | 'currentTime'
>

export function createPlayer(
  onPlayingChange?: (playing: boolean) => void,
  element: AudioLike = new Audio(),
): Player {
  element.preload = 'auto'
  let objectUrl: string | null = null
  let silent = false
  let muted = false
  let playing = false
  const listeners = new Set<(playing: boolean) => void>()
  if (onPlayingChange) listeners.add(onPlayingChange)

  const setPlaying = (next: boolean) => {
    if (next === playing) return
    playing = next
    for (const listener of [...listeners]) listener(next)
  }

  const setSource = (blob: Blob) => {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    objectUrl = URL.createObjectURL(blob)
    element.src = objectUrl
  }

  const halt = () => {
    element.pause()
    try {
      element.currentTime = 0
    } catch {
      // No media loaded yet: nothing to rewind.
    }
    setPlaying(false)
  }

  element.addEventListener('playing', () => {
    if (!silent && !muted) setPlaying(true)
  })
  for (const event of ['pause', 'ended', 'error', 'emptied'] as const) {
    element.addEventListener(event, () => setPlaying(false))
  }

  return {
    unlock() {
      silent = true
      setSource(silentWav())
      element.play().catch(() => undefined)
    },

    async play(audio) {
      if (muted) return
      silent = false
      element.pause()
      setSource(audio)
      try {
        await element.play()
      } catch (error) {
        // Interrupted by a newer play() or stop(): not a failure.
        if (error instanceof DOMException && error.name === 'AbortError') return
        throw error
      }
    },

    stop: halt,

    setMuted(next) {
      muted = next
      if (muted) halt()
    },

    isMuted: () => muted,

    isPlaying: () => playing,

    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },

    dispose() {
      halt()
      element.removeAttribute('src')
      element.load()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      objectUrl = null
      listeners.clear()
    },
  }
}

/** A short silent 16-bit mono WAV, built in memory (no file, no network). */
export function silentWav(durationMs = 100, sampleRate = 8000): Blob {
  const samples = Math.max(1, Math.round((sampleRate * durationMs) / 1000))
  const dataBytes = samples * 2
  const buffer = new ArrayBuffer(44 + dataBytes)
  const view = new DataView(buffer)
  const ascii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i))
  }
  ascii(0, 'RIFF')
  view.setUint32(4, 36 + dataBytes, true)
  ascii(8, 'WAVE')
  ascii(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  ascii(36, 'data')
  view.setUint32(40, dataBytes, true)
  return new Blob([buffer], { type: 'audio/wav' })
}
