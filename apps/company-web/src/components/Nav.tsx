// Floating top bar in the doctor view's style: brand, program picker, appearance, Refresh.
import { useEffect, useRef, useState } from 'react'
import type { ProgramInfo } from '../lib/api'
import { config } from '../lib/config'
import { THEME_LABEL, useTheme, type ThemeMode } from '../lib/theme'
import { Chevron, Logo, Monitor, Moon, Sun, SyncIcon } from './icons'

const THEME_ICON: Record<ThemeMode, React.ReactNode> = { light: <Sun />, dark: <Moon />, system: <Monitor /> }
const THEME_HINT: Record<ThemeMode, string> = { light: 'Warm paper, for daylight', dark: 'Low glare, for late reviews', system: 'Follows your device setting' }
const MODES: ThemeMode[] = ['light', 'dark', 'system']

export function Nav(props: {
  company: string | null
  programs: ProgramInfo[]
  programId: string
  onProgram: (id: string) => void
  loading: boolean
  onRefresh: () => void
  onToast: (msg: string) => void
}) {
  const { mode, choose } = useTheme()
  const [open, setOpen] = useState<null | 'program' | 'theme'>(null)
  const [scrolled, setScrolled] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onScroll = () => setScrolled(scrollY > 20)
    const onDoc = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(null) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(null) }
    addEventListener('scroll', onScroll, { passive: true })
    document.addEventListener('click', onDoc)
    document.addEventListener('keydown', onKey)
    return () => { removeEventListener('scroll', onScroll); document.removeEventListener('click', onDoc); document.removeEventListener('keydown', onKey) }
  }, [])
  const pick = (m: ThemeMode) => {
    choose(m)
    setOpen(null)
    props.onToast(`Appearance: ${THEME_LABEL[m]}${m === 'system' ? ', following your device' : ''}`)
  }
  const current = props.programs.find((p) => p.program_id === props.programId)

  return (
    <div className="nav-shell" ref={wrap}>
      <div className="wrap">
        <header className={`nav ${scrolled ? 'scrolled' : ''}`}>
          <a className="brand" href="#/signals" aria-label="SafeSignal, company portal" onClick={() => scrollTo({ top: 0 })}>
            <Logo />
            <span>Safe<b>Signal</b></span>
          </a>
          <span className="who">{props.company ?? 'Company portal'}</span>
          <div className="nav-right">
            <div className="org">
              <button type="button" className="org-btn" aria-haspopup="menu" aria-expanded={open === 'program'} onClick={() => setOpen(open === 'program' ? null : 'program')}>
                <span className="dot" />
                <span className="org-name" title={current?.label ?? props.programId}>{current?.drug_name ?? 'Program'}</span>
                <Chevron />
              </button>
              {open === 'program' && (
                <div className="org-menu" role="menu" aria-label="Program">
                  <div className="theme-menu-title">Signed in as {config.actorId}</div>
                  {props.programs.map((p) => (
                    <button key={p.program_id} type="button" role="menuitemradio" aria-checked={p.program_id === props.programId}
                      onClick={() => { setOpen(null); if (p.program_id !== props.programId) { props.onProgram(p.program_id); props.onToast(`Program: ${p.drug_name}`) } }}>
                      <strong>{p.drug_name}</strong>
                      <span>{p.cohorts.length} cohorts · {p.source_trial ?? 'synthetic data'}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="theme">
              <button type="button" className="theme-btn" aria-haspopup="menu" aria-expanded={open === 'theme'}
                aria-label={`Appearance: ${THEME_LABEL[mode]}. Change light or dark mode`} title="Change light or dark mode"
                onClick={() => setOpen(open === 'theme' ? null : 'theme')}>
                <span aria-hidden="true">{THEME_ICON[mode]}</span>
                <span className="theme-lbl" aria-hidden="true">{THEME_LABEL[mode]}</span>
                <Chevron className="chev" />
              </button>
              {open === 'theme' && (
                <div className="org-menu theme-menu" role="menu" aria-label="Appearance">
                  <div className="theme-menu-title">Appearance</div>
                  {MODES.map((m) => (
                    <button key={m} type="button" role="menuitemradio" aria-checked={mode === m} onClick={() => pick(m)}>
                      <span className="ti" aria-hidden="true">{THEME_ICON[m]}</span>
                      <span><strong>{THEME_LABEL[m]}</strong><span>{THEME_HINT[m]}</span></span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button type="button" className={`btn btn-dark sync ${props.loading ? 'spinning' : ''}`} onClick={props.onRefresh} disabled={props.loading}>
              <SyncIcon />
              <span className="sync-label">{props.loading ? 'Loading…' : 'Refresh'}</span>
            </button>
          </div>
        </header>
      </div>
    </div>
  )
}
