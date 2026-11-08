// Shared pieces for the public pages: frame, header, text-size toggle, accordion.
import type { ReactNode } from 'react'
import type { QA } from './content'

export function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-lav p-3 font-soft leading-relaxed text-plum sm:p-4">
      <div className="mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-cream shadow-frame">{children}</div>
    </div>
  )
}

export function Logo() {
  return (
    <a href="#/about" className="soft-focus mr-auto flex items-center gap-2.5 rounded-xl text-plum no-underline">
      <span className="grid h-10 w-10 place-items-center rounded-[0.9rem] bg-plum">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M3 13c2-5 4-5 5.5 0s3.5 5 5.5 0 3.5-5 5-2" stroke="#f5ece3" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </span>
      <span className="font-display text-xl font-bold">SafeSignal</span>
    </a>
  )
}

export function SizeToggle({ big, onToggle }: { big: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={big}
      className={`soft-focus min-h-11 rounded-full px-4 font-extrabold ${big ? 'bg-plum text-white' : 'bg-mauve text-plum'}`}
    >
      {big ? 'Smaller text' : 'Bigger text'}
    </button>
  )
}

export function NavLink(props: { onClick?: () => void; href?: string; children: ReactNode }) {
  const cls = 'soft-focus inline-flex min-h-11 items-center rounded-full px-4 font-bold text-plum no-underline hover:bg-mauve'
  return props.href ? (
    <a href={props.href} className={cls}>{props.children}</a>
  ) : (
    <button type="button" onClick={props.onClick} className={cls}>{props.children}</button>
  )
}

export function Accordion({ items, tone = 'bg-mauve' }: { items: QA[]; tone?: string }) {
  return (
    <div className="flex flex-col gap-2.5">
      {items.map((f) => (
        <details key={f.q} className={`rounded-[1.3rem] ${tone}`}>
          <summary className="soft-focus flex min-h-14 items-center gap-4 rounded-[1.3rem] px-5 py-2 text-[1.05rem] font-extrabold">
            <span className="flex-1">{f.q}</span>
            <svg className="chev flex-none transition-transform" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#583a56" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </summary>
          <p className="m-0 px-5 pb-5">{f.a}</p>
        </details>
      ))}
    </div>
  )
}

export function Footer({ children }: { children?: ReactNode }) {
  return (
    <footer className="flex flex-wrap gap-x-8 gap-y-2 border-t-[1.5px] border-mauve px-7 pb-7 pt-5 text-[0.9rem]">
      {children ?? <span className="font-display font-bold">SafeSignal</span>}
      <span>Built at HACK1984 · demo uses synthetic data only</span>
      <span className="ml-auto">Not a replacement for your doctor. In an emergency, call 911.</span>
    </footer>
  )
}
