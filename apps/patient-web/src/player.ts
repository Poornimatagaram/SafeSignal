// Plays the question audio that the runtime speaks with local text-to-speech.
// One audio element is reused for the whole check-in: unlocking it inside the "Start check-in" tap lets later
// questions play automatically, even in browsers that only allow sound after a tap on that same element.

export interface Player {
  /** Call inside a tap handler: plays a moment of silence so later playback is allowed. */
  unlock(): void
  /** Play one WAV blob, replacing whatever is playing. Rejects if the browser refuses to play. */
  play(audio: Blob): Promise<void>
  /** Stop playback (for example when the patient starts answering). */
  stop(): void
  /** Release the element and any object URL. */
  dispose(): void
}

export function createPlayer(onPlayingChange: (playing: boolean) => void): Player {
  const element = new Audio()
  element.preload = 'auto'
  let objectUrl: string | null = null
  let silent = false

  const setSource = (blob: Blob) => {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    objectUrl = URL.createObjectURL(blob)
    element.src = objectUrl
  }

  element.addEventListener('playing', () => {
    if (!silent) onPlayingChange(true)
  })
  for (const event of ['pause', 'ended', 'error', 'emptied'] as const) {
    element.addEventListener(event, () => onPlayingChange(false))
  }

  return {
    unlock() {
      silent = true
      setSource(silentWav())
      element.play().catch(() => undefined)
    },

    async play(audio) {
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

    stop() {
      element.pause()
    },

    dispose() {
      element.pause()
      element.removeAttribute('src')
      element.load()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      objectUrl = null
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
