// What Walter sees at the end of the check-in: the summary, the "Share this" gate and the receipt.
// Rendered to static HTML (no browser needed); taps are covered by tests/approval.test.ts.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { RuntimeError } from '../src/api.ts'
import { INITIAL_SHARE_STATE, type ShareState } from '../src/shareFlow.ts'
import { ShareView } from '../src/ShareScreen.tsx'
import {
  formatLocalTime,
  onsetSentence,
  onsetText,
  receiptStatusText,
  severityQuestion,
  severityText,
  sharedPartsText,
} from '../src/summaryText.ts'
import {
  FIELDS,
  RECEIPT_FAILED,
  RECEIPT_QUEUED,
  RECEIPT_SENT,
  SUMMARY_EMPTY,
  SUMMARY_NEEDS_SEVERITY,
  SUMMARY_READY,
} from './fixtures.ts'

const noop = () => undefined

function render(patch: Partial<ShareState>): string {
  const state: ShareState = { ...INITIAL_SHARE_STATE, ...patch }
  return renderToStaticMarkup(
    <ShareView
      state={state}
      onChoose={noop}
      onShare={noop}
      onNotNow={noop}
      onBack={noop}
      onRetryLoad={noop}
      onRestart={noop}
    />,
  )
}

/** The visible text of rendered HTML. */
function textOf(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
}

/** The opening tag of the button whose label is `label`. */
function buttonTag(html: string, label: string): string {
  const match = [...html.matchAll(/<button[^>]*>(.*?)<\/button>/g)].find((m) => textOf(m[1]).trim() === label)
  if (!match) throw new Error(`no button "${label}"`)
  return match[0].slice(0, match[0].indexOf('>') + 1)
}

describe('summary and approval screen', () => {
  const needs = { phase: 'review' as const, summary: SUMMARY_NEEDS_SEVERITY, needs: ['SE_RASH'] }

  it('shows each item in plain words, for review, never as a cause', () => {
    const text = textOf(render(needs))
    expect(text).toContain('Rash For review')
    expect(text).toContain('Started 1 to 3 days ago')
    expect(text).toContain('Fatigue For review')
    expect(text).toContain('How bad: Mild')
    expect(text).toContain('Start not known')
    expect(text).not.toMatch(/caus|because of|due to|side effect/i)
  })

  it('asks how bad each item with no severity is, and keeps Share this disabled until chosen', () => {
    const html = render(needs)
    const text = textOf(html)
    expect(text).toContain('How bad is the rash?')
    expect(text).toContain('Not chosen yet')
    for (const label of ['Mild', 'Moderate', 'Severe']) expect(buttonTag(html, label)).toContain('aria-pressed="false"')
    expect(buttonTag(html, 'Share this')).toContain('aria-disabled="true"')
    expect(text).toContain('Choose how bad each problem is, then tap Share this.')
  })

  it('shows the choice in words and enables Share this once every severity is chosen', () => {
    const html = render({ ...needs, chosen: { SE_RASH: 'severe' } })
    expect(textOf(html)).toContain('You chose: Severe')
    expect(html).toMatch(/<button[^>]*aria-pressed="true"[^>]*>.*?Severe<\/button>/)
    expect(buttonTag(html, 'Share this')).toContain('aria-disabled="false"')
  })

  it('enables Share this straight away when nothing is missing', () => {
    const html = render({ phase: 'review', summary: SUMMARY_READY })
    expect(buttonTag(html, 'Share this')).toContain('aria-disabled="false"')
    expect(buttonTag(html, 'Not now')).toContain('aria-disabled="false"')
    expect(textOf(html)).toContain('How bad: Moderate')
  })

  it('says when there is nothing to report, and that sharing says so', () => {
    const text = textOf(render({ phase: 'review', summary: SUMMARY_EMPTY }))
    expect(text).toContain('You did not report any new problems.')
    expect(text).toContain('It tells them you had no new problems.')
    expect(text).toContain('1 question had no answer.')
  })

  it('explains what will be shared, hiding the exact record behind a toggle', () => {
    const html = render({ phase: 'review', summary: SUMMARY_READY })
    const text = textOf(html)
    expect(text).toContain('Who gets it: Drug company safety team (Sentinel service)')
    expect(text).toContain('no name, no words you said, no recording')
    expect(text).toContain('A random code instead of your name')
    expect(buttonTag(html, 'Show exactly what is sent')).toContain('aria-expanded="false"')
    expect(text).not.toContain('pt_4b82d0c6') // the record JSON shows only after the toggle
  })

  it('disables every control while sharing', () => {
    const html = render({ ...needs, phase: 'sending', chosen: { SE_RASH: 'mild' } })
    expect(buttonTag(html, 'Sharing…')).toContain('aria-disabled="true"')
    expect(buttonTag(html, 'Not now')).toContain('aria-disabled="true"')
    expect(buttonTag(html, 'Moderate')).toContain('aria-disabled="true"')
  })

  it('shows a plain message when the runtime still needs a severity (409)', () => {
    const failure = { error: new RuntimeError('needs-severity', 409, ['SE_RASH']) }
    const text = textOf(render({ ...needs, failure }))
    expect(text).toContain('Please choose how bad each problem is, then tap Share this again.')
  })

  it('offers to start again when the check-in is gone', () => {
    const failure = { error: new RuntimeError('session-not-found', 404) }
    const html = render({ phase: 'load-failed', failure })
    expect(textOf(html)).toContain('This check-in is no longer open on this computer.')
    expect(buttonTag(html, 'Start again')).toBeTruthy()
    expect(buttonTag(html, 'Not now')).toBeTruthy()
  })
})

describe('receipt screen (PV-05)', () => {
  it('shows status, destination, local time, every field sent and the full fingerprint', () => {
    const html = render({ phase: 'receipt', summary: SUMMARY_READY, receipt: RECEIPT_SENT })
    const text = textOf(html)
    expect(text).toContain('Shared')
    expect(text).toContain('Sent to Drug company safety team (Sentinel service)')
    expect(text).toContain(`Sent at ${formatLocalTime(RECEIPT_SENT.sent_at ?? '')}`)
    for (const field of FIELDS) expect(text).toContain(field)
    expect(html).toContain(`<p class="mono fingerprint">${RECEIPT_SENT.payload_sha256}</p>`)
    expect(text).toContain('rec_7f3c9a1e')
    expect(text).toContain("Thank you, that's all for today.")
  })

  it('says a queued record is kept on this device and sent later', () => {
    const text = textOf(render({ phase: 'receipt', summary: SUMMARY_READY, receipt: RECEIPT_QUEUED }))
    expect(text).toContain('Saved on this device; it will be sent when you are back online')
    expect(text).toContain('Will be sent to Drug company safety team')
    expect(text).toContain('Not yet')
  })

  it('says a refused record was not accepted', () => {
    const text = textOf(render({ phase: 'receipt', summary: SUMMARY_READY, receipt: RECEIPT_FAILED }))
    expect(text).toContain('Not accepted')
    expect(text).toContain('Code 422')
  })
})

describe('not now', () => {
  it('says nothing was shared and offers a way back', () => {
    const html = render({ phase: 'not-shared', summary: SUMMARY_READY })
    expect(textOf(html)).toContain('Nothing was shared.')
    expect(buttonTag(html, 'Go back to my summary')).toBeTruthy()
  })
})

describe('plain words', () => {
  it.each([
    ['today', 'today'],
    ['1_3_days', '1 to 3 days ago'],
    ['4_7_days', '4 to 7 days ago'],
    ['over_7_days', 'more than a week ago'],
    ['unknown', 'start not known'],
    [null, 'start not known'],
  ])('onset %s is "%s"', (onset, words) => {
    expect(onsetText(onset)).toBe(words)
  })

  it('builds the onset sentence', () => {
    expect(onsetSentence('today')).toBe('Started today')
    expect(onsetSentence(null)).toBe('Start not known')
  })

  it('names severities and asks about them', () => {
    expect(severityText('moderate')).toBe('Moderate')
    expect(severityText(null)).toBe('Not known')
    expect(severityQuestion('Rash')).toBe('How bad is the rash?')
    expect(severityQuestion('Shortness of breath')).toBe('How bad is the shortness of breath?')
  })

  it('explains every field the runtime sends, and flags any it cannot explain', () => {
    expect(sharedPartsText(FIELDS)).not.toContain('Other coded answers (see the exact list)')
    expect(sharedPartsText([...FIELDS, 'new_field'])).toContain('Other coded answers (see the exact list)')
    expect(sharedPartsText(['iso_week'])).toEqual(['The week of this check-in, not the day'])
  })

  it('names each receipt status', () => {
    expect(receiptStatusText('sent')).toBe('Shared')
    expect(receiptStatusText('queued')).toBe('Saved on this device; it will be sent when you are back online')
    expect(receiptStatusText('failed')).toBe('Not accepted')
  })

  it('shows the send time in local time', () => {
    const shown = formatLocalTime('2026-11-08T14:03:12Z', 'en-US', 'America/New_York')
    expect(shown).toContain('November 8, 2026')
    expect(shown).toMatch(/9:03/)
    expect(formatLocalTime('not a time')).toBe('not a time')
  })
})
