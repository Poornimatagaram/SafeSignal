// Push-to-talk recording with MediaRecorder. The recording lives in memory only and is handed to the caller,
// which sends it to the local runtime and nowhere else.
//
// There is no silence detection on purpose (VC-03): long pauses never end the answer, only the patient's tap does.

/** Preferred recording formats, best first. If none is supported, the browser's default is used. */
export const PREFERRED_MIME_TYPES = ['audio/webm;codecs=opus', 'audio/mp4'] as const

/** The first supported preferred format, or undefined to let the browser choose. */
export function chooseMimeType(isTypeSupported: ((type: string) => boolean) | undefined = browserTypeCheck()): string | undefined {
  if (!isTypeSupported) return undefined
  return PREFERRED_MIME_TYPES.find((type) => {
    try {
      return isTypeSupported(type)
    } catch {
      return false
    }
  })
}

function browserTypeCheck(): ((type: string) => boolean) | undefined {
  if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') return undefined
  return (type) => MediaRecorder.isTypeSupported(type)
}

export type MicrophoneErrorKind = 'blocked' | 'not-found' | 'busy' | 'unsupported' | 'failed'

export class MicrophoneError extends Error {
  readonly kind: MicrophoneErrorKind

  constructor(kind: MicrophoneErrorKind) {
    super(`microphone error: ${kind}`)
    this.name = 'MicrophoneError'
    this.kind = kind
  }
}

/** Map a getUserMedia rejection to a plain reason. */
export function microphoneErrorKind(error: unknown): MicrophoneErrorKind {
  const name = typeof error === 'object' && error !== null && 'name' in error ? String(error.name) : ''
  switch (name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
    case 'SecurityError':
      return 'blocked'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
    case 'OverconstrainedError':
      return 'not-found'
    case 'NotReadableError':
    case 'TrackStartError':
    case 'AbortError':
      return 'busy'
    case 'TypeError':
      return 'unsupported'
    default:
      return 'failed'
  }
}

export interface ActiveRecording {
  /** Stop recording and release the microphone; resolves with the whole answer as one Blob. */
  stop(): Promise<Blob>
  /** Stop recording, release the microphone and drop what was recorded. */
  cancel(): void
}

function stopTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop()
}

/** Ask for the microphone and start recording. Throws MicrophoneError with a plain reason. */
export async function startRecording(): Promise<ActiveRecording> {
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    throw new MicrophoneError('unsupported')
  }

  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (error) {
    throw new MicrophoneError(microphoneErrorKind(error))
  }

  const mimeType = chooseMimeType()
  let recorder: MediaRecorder
  try {
    recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
  } catch {
    stopTracks(stream)
    throw new MicrophoneError('unsupported')
  }

  let chunks: Blob[] = []
  let cancelled = false
  recorder.ondataavailable = (event) => {
    if (!cancelled && event.data && event.data.size > 0) chunks.push(event.data)
  }

  const finished = new Promise<Blob>((resolve, reject) => {
    recorder.onstop = () => {
      stopTracks(stream)
      const type = recorder.mimeType || mimeType || chunks[0]?.type || ''
      const blob = new Blob(chunks, { type })
      chunks = []
      resolve(blob)
    }
    recorder.onerror = () => {
      stopTracks(stream)
      chunks = []
      reject(new MicrophoneError('failed'))
    }
  })
  // A cancelled recording is never awaited; keep its outcome from surfacing as an unhandled rejection.
  finished.catch(() => undefined)

  try {
    // No timeslice: the whole answer arrives in one dataavailable event just before stop.
    recorder.start()
  } catch {
    stopTracks(stream)
    throw new MicrophoneError('failed')
  }

  return {
    stop() {
      if (recorder.state !== 'inactive') recorder.stop()
      return finished
    },
    cancel() {
      cancelled = true
      chunks = []
      if (recorder.state !== 'inactive') recorder.stop()
      stopTracks(stream)
    },
  }
}
