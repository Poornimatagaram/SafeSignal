// Static privacy checks over the app source (Scoping Doc 15.4, 26.12). These tests live outside src/ so the
// forbidden words below never appear in the code they scan.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SRC = join(ROOT, 'src')
const RUNTIME_DEFAULT = 'http://127.0.0.1:8001'

function filesUnder(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? filesUnder(path) : [path]
  })
}

const sources = [...filesUnder(SRC), join(ROOT, 'index.html')].map((path) => ({
  file: relative(ROOT, path),
  text: readFileSync(path, 'utf8'),
}))

/** The one file allowed to touch sessionStorage: it remembers "sound off" for this browser session, nothing else. */
const SOUND_SETTING = join('src', 'soundSetting.ts')

const FORBIDDEN: Array<[string, RegExp]> = [
  // Web Speech API: Chrome sends the audio to the cloud; browser voices may be cloud voices.
  ['SpeechRecognition', /speechrecognition/i],
  ['webkitSpeechRecognition', /webkitspeechrecognition/i],
  ['speechSynthesis', /speechsynthesis/i],
  // No patient words kept in the browser.
  ['localStorage', /localstorage/i],
  ['sessionStorage', /sessionstorage/i],
  ['indexedDB', /indexeddb/i],
  ['document.cookie', /document\s*\.\s*cookie/i],
  // No beacons or side channels.
  ['sendBeacon', /sendbeacon/i],
  ['XMLHttpRequest', /xmlhttprequest/i],
  ['WebSocket', /websocket/i],
  ['EventSource', /eventsource/i],
]

describe('src/ privacy rules', () => {
  it('scans a non-empty source tree', () => {
    expect(sources.length).toBeGreaterThan(3)
  })

  it.each(FORBIDDEN)('never uses %s', (name, pattern) => {
    const hits = sources
      .filter(({ file }) => !(name === 'sessionStorage' && file === SOUND_SETTING))
      .filter(({ text }) => pattern.test(text))
      .map(({ file }) => file)
    expect(hits).toEqual([])
  })

  it('sessionStorage holds only the sound setting: one key, "1" or "0"', () => {
    const text = sources.find(({ file }) => file === SOUND_SETTING)!.text
    expect(text).toContain("export const MUTED_KEY = 'patient-web.muted'")
    const writes = [...text.matchAll(/setItem\(([^)]*)\)/g)].map((m) => m[1])
    expect(writes).toEqual(["MUTED_KEY, muted ? '1' : '0'"])
    expect(text).not.toMatch(/localstorage/i)
  })

  it('contains no absolute http(s) URL except the runtime default', () => {
    const urls = sources.flatMap(({ file, text }) =>
      [...text.matchAll(/https?:\/\/[^\s'"`<>)]*/gi)].map((match) => ({ file, url: match[0] })),
    )
    const others = urls.filter(({ url }) => url.replace(/\/$/, '') !== RUNTIME_DEFAULT)
    expect(others).toEqual([])
  })

  it('makes network requests only from the API client', () => {
    const callers = sources.filter(({ text }) => /\bfetch\s*\(/.test(text)).map(({ file }) => file)
    expect(callers).toEqual([join('src', 'api.ts')])
  })
})
