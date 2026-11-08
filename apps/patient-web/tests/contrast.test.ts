// WCAG AA contrast (NF-08) for the colour tokens in src/styles.css: the pairs every screen uses for its words.
// Normal text needs 4.5:1; large text (24 px+, or 18.66 px+ bold) needs 3:1. White on coral is used only for
// button and talk labels, which are all 25 px+ bold, so it is checked against the large-text bar.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const css = readFileSync(fileURLToPath(new URL('../src/styles.css', import.meta.url)), 'utf8')
const root = /:root \{([^}]*)\}/.exec(css)![1]

function token(name: string): string {
  const match = new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`).exec(root)
  if (!match) throw new Error(`no colour token --${name}`)
  return match[1]
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const WHITE = '#ffffff'

describe('colour contrast of the main token pairs', () => {
  it('computes the known ratios (black on white is 21:1)', () => {
    expect(ratio('#000000', WHITE)).toBeCloseTo(21, 5)
    expect(ratio(WHITE, WHITE)).toBeCloseTo(1, 5)
  })

  it.each([
    ['ink', 'cream'],
    ['ink', 'cream-deep'],
    ['ink', 'card'],
    ['ink', 'tint'],
    ['ink', 'alert-bg'],
    ['ink-soft', 'cream'],
    ['ink-soft', 'cream-deep'],
    ['ink-soft', 'card'],
    ['ink-soft', 'tint'],
    ['sage-ink', 'sage'],
    ['ink', 'sage'],
    ['ink', 'coral'],
  ])('--%s on --%s passes AA for normal text (4.5:1)', (fg, bg) => {
    expect(ratio(token(fg), token(bg))).toBeGreaterThanOrEqual(4.5)
  })

  it.each([['coral-deep'], ['coral-press'], ['listening']])(
    'white labels on --%s pass AA for large text (3:1)',
    (bg) => {
      expect(ratio(WHITE, token(bg))).toBeGreaterThanOrEqual(3)
    },
  )

  it('hover and listening surfaces pass even the normal-text bar', () => {
    expect(ratio(WHITE, token('coral-press'))).toBeGreaterThanOrEqual(4.5)
    expect(ratio(WHITE, token('listening'))).toBeGreaterThanOrEqual(4.5)
  })

  it('the focus outline stands out on the page and on coral buttons (3:1 for non-text)', () => {
    expect(ratio(token('focus'), token('cream'))).toBeGreaterThanOrEqual(3)
    expect(ratio(token('focus'), token('cream-deep'))).toBeGreaterThanOrEqual(3)
    expect(ratio(token('focus'), token('coral-deep'))).toBeGreaterThanOrEqual(3)
  })

  it('white text sits on coral only in big bold labels (buttons, talk), never on the light --coral', () => {
    const rules = [...css.replace(/\/\*[^]*?\*\//g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    for (const [, selector, body] of rules) {
      if (!/color:\s*#ffffff/.test(body)) continue
      expect(body).not.toMatch(/background:\s*var\(--coral\)/)
      expect(selector).toMatch(/\.(button--primary|talk|choice__button--on)/)
    }
    // Those labels are 25 px+ and bold: large text.
    const button = /\n\.button \{([^}]*)\}/.exec(css)![1]
    expect(button).toMatch(/font-size:\s*1\.05rem/)
    expect(button).toMatch(/font-weight:\s*700/)
  })
})
