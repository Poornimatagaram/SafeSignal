// Language-ready (owner spec): every word on every screen lives in src/strings.ts. This checks the file covers every
// screen, and scans every component for text written straight into it (which a translation would miss).
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { DEFAULT_LOCALE, S, STRINGS, t, type Strings } from '../src/strings.ts'

const SRC = fileURLToPath(new URL('../src', import.meta.url))
const COMPONENTS = readdirSync(SRC).filter((name) => name.endsWith('.tsx'))

/** Every leaf of the strings object, with its path: strings, and functions called with sample arguments. */
function leaves(value: unknown, path: string[] = []): Array<{ path: string; text: unknown }> {
  if (typeof value === 'string') return [{ path: path.join('.'), text: value }]
  if (typeof value === 'function') {
    // Words with numbers ("Question 2 of 5") or with names ("Change my care team"): one of these fits each one.
    const fn = value as (...a: unknown[]) => unknown
    const tries = [Array(value.length).fill(2), Array(value.length).fill('Sample'), [2, 'Sample', 'x', 'y']]
    for (const args of tries) {
      try {
        return [{ path: path.join('.'), text: fn(...args) }]
      } catch {
        // try the next kind of sample
      }
    }
    return [{ path: path.join('.'), text: undefined }]
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, child]) => leaves(child, [...path, key]))
  }
  return [{ path: path.join('.'), text: value }]
}

describe('src/strings.ts', () => {
  it('has a section for every screen and for the shared plain words and messages', () => {
    for (const screen of ['home', 'checkin', 'summary', 'receipt', 'consent', 'setup', 'networkLog', 'errors', 'plain']) {
      expect(S).toHaveProperty(screen)
    }
  })

  it('every entry gives non-empty words', () => {
    const all = leaves(S)
    expect(all.length).toBeGreaterThan(250)
    const empty = all.filter(({ text }) => typeof text !== 'string' || text.trim() === '')
    expect(empty).toEqual([])
  })

  it('is structured for more languages: English by default, picked with t()', () => {
    expect(DEFAULT_LOCALE).toBe('en')
    expect(Object.keys(STRINGS)).toContain('en')
    expect(t()).toBe(STRINGS.en)
    expect(t('en')).toBe(S)
    // Another language has to fill in the same shape (a compile-time check; this line only has to type-check).
    const sameShape: Strings = STRINGS.en
    expect(sameShape).toBe(S)
  })
})

/** Text a component holds itself instead of taking it from src/strings.ts. */
function hardCodedText(file: string, text = readFileSync(join(SRC, file), 'utf8')): string[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const found: string[] = []
  // Attributes a person reads or hears.
  const SPOKEN_ATTRIBUTES = new Set(['aria-label', 'aria-description', 'title', 'alt', 'placeholder', 'label', 'question'])
  // Words in a sentence: a capital letter, then lower-case letters, then a space and more words ("Hear it again").
  const PROSE = /[A-Z][a-z]+[ ,.?!:…’'][^]*[a-z]/

  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && /[A-Za-z]/.test(node.text)) {
      found.push(`text: ${node.text.trim()}`)
    } else if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
      const name = node.name.getText(source)
      if (SPOKEN_ATTRIBUTES.has(name) && /[A-Za-z]/.test(node.initializer.text)) {
        found.push(`${name}="${node.initializer.text}"`)
      }
    } else if (
      (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
      !ts.isImportDeclaration(node.parent) &&
      !ts.isJsxAttribute(node.parent) &&
      PROSE.test(node.text)
    ) {
      found.push(`string: ${node.text}`)
    } else if (ts.isTemplateExpression(node)) {
      // Class names are lower-case; words for people start with a capital ("Question 1 of 5").
      const parts = [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(' ')
      if (/\b[A-Z][a-z]+\b/.test(parts)) found.push(`template: ${node.getText(source)}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

describe('no hard-coded words in components', () => {
  it('scans every component', () => {
    expect(COMPONENTS).toEqual(
      expect.arrayContaining([
        'App.tsx',
        'HomeScreen.tsx',
        'CheckinChat.tsx',
        'ShareScreen.tsx',
        'ConsentScreen.tsx',
        'SetupScreen.tsx',
        'NetworkLogScreen.tsx',
      ]),
    )
  })

  it.each(COMPONENTS)('%s takes all its words from src/strings.ts', (file) => {
    expect(hardCodedText(file)).toEqual([])
  })

  it('the scan finds words written straight into a component', () => {
    const sample = [
      'export const A = () => (',
      '  <p title="Hello there" aria-label={S.x}>',
      '    Hear it again {"Share this"} {`Question ${n} of ${m}`} <span className="button button--primary" />',
      '  </p>',
      ')',
    ].join('\n')
    expect(hardCodedText('sample.tsx', sample)).toEqual([
      'title="Hello there"',
      'text: Hear it again',
      'string: Share this',
      'template: `Question ${n} of ${m}`',
    ])
  })
})
