// SE-04: a symptom that started within a week of something new is "marked for review", never described as caused.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { createRuntimeClient, type CheckinSummary, type FetchLike } from '../src/api.ts'
import { INITIAL_SHARE_STATE } from '../src/shareFlow.ts'
import { ShareView } from '../src/ShareScreen.tsx'
import { POSSIBLE_LINK_TEXT, sharedPartsText } from '../src/summaryText.ts'
import { BASE, FIELDS, json, SID, SUMMARY_READY } from './fixtures.ts'

/** Wording that would state a cause. "does not mean one caused the other" is the opposite, so it is allowed. */
const CAUSE_WORDS = /caused by|causes|because of|due to|reaction to|led to|result of|side effect of/i

const RASH = SUMMARY_READY.items[0]
const FLAGGED: CheckinSummary = {
  ...SUMMARY_READY,
  items: [
    { ...RASH, possible_link: true },
    { term_code: 'SE_FATIGUE', label: 'Fatigue', severity: 'mild', onset: 'today', known_side_effect: true, possible_link: false },
  ],
}

function textOf(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
}

const render = (summary: CheckinSummary) => {
  const noop = () => undefined
  return renderToStaticMarkup(
    <ShareView
      state={{ ...INITIAL_SHARE_STATE, phase: 'review', summary }}
      onChoose={noop}
      onShare={noop}
      onNotNow={noop}
      onBack={noop}
      onRetryLoad={noop}
      onRestart={noop}
    />,
  )
}

describe('possible link (SE-04)', () => {
  it('reads possible_link true, false, null and missing (missing or null reads as false)', async () => {
    const items = [
      { ...RASH, possible_link: true },
      { ...RASH, term_code: 'SE_A', possible_link: false },
      { ...RASH, term_code: 'SE_B', possible_link: null },
      { ...RASH, term_code: 'SE_C', possible_link: undefined },
      { ...RASH, term_code: 'SE_D', possible_link: 'yes' },
    ]
    const fetchMock = vi.fn<FetchLike>(async () => json({ ...SUMMARY_READY, items }))
    const summary = await createRuntimeClient(BASE, fetchMock).getSummary(SID)
    expect(summary.items.map((item) => item.possible_link)).toEqual([true, false, false, false, false])
  })

  it('shows the review line only under the flagged item', () => {
    const html = render(FLAGGED)
    const items = [...html.matchAll(/<li class="item">(.*?)<\/li>/g)].map((m) => textOf(m[1]))
    expect(items).toHaveLength(2)
    expect(items[0]).toContain(POSSIBLE_LINK_TEXT)
    expect(items[1]).not.toContain('Marked for review')
    expect(textOf(render(SUMMARY_READY))).not.toContain('Marked for review')
  })

  it('says it in plain words, never as a cause', () => {
    expect(POSSIBLE_LINK_TEXT).toBe(
      'Marked for review: this started within a week of something new you began. That does not mean one caused the other.',
    )
    expect(POSSIBLE_LINK_TEXT).not.toMatch(CAUSE_WORDS)
    expect(textOf(render(FLAGGED))).not.toMatch(CAUSE_WORDS)
    const source = readFileSync(fileURLToPath(new URL('../src/summaryText.ts', import.meta.url)), 'utf8')
    expect(source.match(/'[^']*review[^']*'/g)?.join(' ')).not.toMatch(CAUSE_WORDS)
  })

  it('the plain field list says the symptom flag is whether it is marked for review', () => {
    expect(sharedPartsText(FIELDS).join(' ')).toContain('whether it is marked for review')
  })
})
