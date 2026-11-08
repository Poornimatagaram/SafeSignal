import { describe, expect, it } from 'vitest'
import { chooseMimeType, microphoneErrorKind, PREFERRED_MIME_TYPES } from '../src/recorder.ts'
import { symptomText } from '../src/messages.ts'
import { silentWav } from '../src/player.ts'

const supports = (...types: string[]) => (type: string) => types.includes(type)

describe('chooseMimeType', () => {
  it('prefers WebM/Opus first, then MP4', () => {
    expect(PREFERRED_MIME_TYPES).toEqual(['audio/webm;codecs=opus', 'audio/mp4'])
  })

  it('picks WebM/Opus when supported (Chrome, Edge, Firefox)', () => {
    expect(chooseMimeType(supports('audio/webm;codecs=opus', 'audio/mp4'))).toBe('audio/webm;codecs=opus')
  })

  it('picks MP4 when WebM/Opus is not supported (Safari)', () => {
    expect(chooseMimeType(supports('audio/mp4'))).toBe('audio/mp4')
  })

  it('leaves the choice to the browser when neither is supported', () => {
    expect(chooseMimeType(supports('audio/ogg'))).toBeUndefined()
  })

  it('leaves the choice to the browser when MediaRecorder cannot be asked', () => {
    // Node has no MediaRecorder, so the default check is unavailable.
    expect(chooseMimeType()).toBeUndefined()
    expect(chooseMimeType(undefined)).toBeUndefined()
  })

  it('skips a type whose check throws', () => {
    const check = (type: string) => {
      if (type === 'audio/webm;codecs=opus') throw new Error('boom')
      return true
    }
    expect(chooseMimeType(check)).toBe('audio/mp4')
  })
})

describe('microphoneErrorKind', () => {
  it.each([
    ['NotAllowedError', 'blocked'],
    ['SecurityError', 'blocked'],
    ['NotFoundError', 'not-found'],
    ['NotReadableError', 'busy'],
    ['TypeError', 'unsupported'],
    ['SomethingElse', 'failed'],
  ])('maps %s to %s', (name, kind) => {
    expect(microphoneErrorKind({ name })).toBe(kind)
  })

  it('handles a rejection that is not an error object', () => {
    expect(microphoneErrorKind('nope')).toBe('failed')
  })
})

describe('symptomText', () => {
  it('shows the label and the severity in plain words', () => {
    expect(symptomText({ term_code: 'SE_RASH', label: 'Rash', severity: 'moderate' })).toBe('Rash, moderate')
  })

  it('shows only the label when severity is unknown', () => {
    expect(symptomText({ term_code: 'SE_RASH', label: 'Rash', severity: null })).toBe('Rash')
  })
})

describe('silentWav', () => {
  it('builds a valid PCM WAV header in memory', async () => {
    const blob = silentWav(100, 8000)
    expect(blob.type).toBe('audio/wav')
    const bytes = new Uint8Array(await blob.arrayBuffer())
    const text = (start: number, end: number) => String.fromCharCode(...bytes.slice(start, end))
    expect(text(0, 4)).toBe('RIFF')
    expect(text(8, 12)).toBe('WAVE')
    expect(text(36, 40)).toBe('data')
    expect(bytes.length).toBe(44 + 800 * 2)
  })
})
