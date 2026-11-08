// Floating top bar: sections, hospital filter (with key status), appearance, Sync now, and the phone menu.
import { useEffect, useRef, useState } from 'react'
import { doctorName } from '../lib/config'
import type { OrgStatus } from '../lib/keys'
import { THEME_LABEL, useTheme, type ThemeMode } from '../lib/theme'
import type { ViewMode } from '../lib/viewMode'
import { Chevron, Logo, Menu, Monitor, Moon, Sun, SyncIcon } from './icons'
import { SECTIONS, keyStatus } from './navModel'
import { goSection } from './routes'

const THEME_ICON: Record<ThemeMode, React.ReactNode> = { light: <Sun />, dark: <Moon />, system: <Monitor /> }
const THEME_HINT: Record<ThemeMode, string> = { light: 'Warm paper, for daylight', dark: 'Low glare, for night shifts', system: 'Follows your device setting' }
const MODES: ThemeMode[] = ['light', 'dark', 'system']

export function Nav(props: {
  doctorId: string | null
  orgs: OrgStatus[]
  orgFilter: string | null
  setOrgFilter: (id: string | null) => void
  unseen: number
  syncing: boolean
  onSync: () => void
  detailHref: string
  activeSection: string | null
  onToast: (msg: string) => void
  view: ViewMode
  onView: (v: ViewMode) => void
}) {
  const { mode, choose } = useTheme()
  const [open, setOpen] = useState<null | 'org' | 'theme' | 'menu'>(null)
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
  const needsSetup = props.orgs.some((o) => !o.hasLocalKey)
  const orgLabel = props.orgFilter ? props.orgs.find((o) => o.org_id === props.orgFilter)?.display_name ?? 'Hospital' : props.orgs.length === 1 ? props.orgs[0].display_name : props.orgs.length ? 'All hospitals' : 'No hospital yet'
  const go = (id: string) => { setOpen(null); goSection(id) }

  return (
    <div className="nav-shell" ref={wrap}>
      <div className="wrap">
        <header className={`nav ${scrolled ? 'scrolled' : ''}`}>
          <a className="brand" href="#/" aria-label="SafeSignal, doctor home" onClick={() => scrollTo({ top: 0 })}>
            <Logo />
            <span>Safe<b>Signal</b></span>
          </a>
          <nav className="nav-links" aria-label="Sections">
            {SECTIONS.map(([id, label]) => (
              <a key={id} href={`#/`} onClick={(e) => { e.preventDefault(); go(id) }} className={props.activeSection === id ? 'on' : ''}>
                {label}
                {id === 'alerts' && props.unseen > 0 && <span className="count">{props.unseen}</span>}
              </a>
            ))}
            <a href={props.detailHref} className={props.activeSection === 'detail' ? 'on' : ''}>Detailed view</a>
          </nav>
          <div className="nav-right">
            <div className="seg mode-seg" role="group" aria-label="View">
              <button type="button" aria-pressed={props.view === 'guided'} title="Full tour: for new doctors and the demo" onClick={() => props.onView('guided')}>Guided</button>
              <button type="button" aria-pressed={props.view === 'clinic'} title="Compact daily view" onClick={() => props.onView('clinic')}>Clinic</button>
            </div>
            <div className="org">
              <button type="button" className="org-btn" aria-haspopup="menu" aria-expanded={open === 'org'} onClick={() => setOpen(open === 'org' ? null : 'org')}>
                <span className="dot" style={{ background: needsSetup ? 'var(--mild)' : 'var(--good)' }} />
                <span className="org-name" title={orgLabel}>{orgLabel}</span>
                <Chevron />
              </button>
              {open === 'org' && (
                <div className="org-menu" role="menu">
                  {props.doctorId && <div className="theme-menu-title">Signed in as {doctorName(props.doctorId)}</div>}
                  {props.orgs.length > 1 && (
                    <button type="button" role="menuitemradio" aria-checked={props.orgFilter === null} onClick={() => { props.setOrgFilter(null); setOpen(null) }}>
                      <strong>All hospitals</strong>
                      <span>Every patient shared with you</span>
                    </button>
                  )}
                  {props.orgs.map((o) => (
                    <button key={o.org_id} type="button" role="menuitemradio" aria-checked={props.orgFilter === o.org_id || props.orgs.length === 1} onClick={() => { props.setOrgFilter(props.orgs.length > 1 ? o.org_id : null); setOpen(null) }}>
                      <strong>{o.display_name}</strong>
                      <span>{o.role.replace('_', ' ')} · {keyStatus(o)}</span>
                    </button>
                  ))}
                  <a className="menu-link" href="#/admin" onClick={() => setOpen(null)}>
                    <strong>Admin &amp; access{needsSetup ? ' · setup needed' : ''}</strong>
                    <span>Care-team keys, members, emergency access</span>
                  </a>
                </div>
              )}
            </div>
            <div className="theme">
              <button
                type="button"
                className="theme-btn"
                aria-haspopup="menu"
                aria-expanded={open === 'theme'}
                aria-label={`Appearance: ${THEME_LABEL[mode]}. Change light or dark mode`}
                title="Change light or dark mode"
                onClick={() => setOpen(open === 'theme' ? null : 'theme')}
              >
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
            <button type="button" className={`btn btn-dark sync ${props.syncing ? 'spinning' : ''}`} onClick={props.onSync} disabled={props.syncing}>
              <SyncIcon />
              <span className="sync-label">{props.syncing ? 'Syncing…' : <><span className="sl-long">Sync now</span><span className="sl-short">Sync</span></>}</span>
            </button>
            <button type="button" className="menu-btn" aria-label="Open menu" aria-expanded={open === 'menu'} onClick={() => setOpen(open === 'menu' ? null : 'menu')}>
              <Menu />
            </button>
          </div>
        </header>
        {open === 'menu' && (
          <div className="mobile-menu">
            <div className="m-theme m-view">
              <span id="m-view-lbl">View</span>
              <div className="m-seg two" role="radiogroup" aria-labelledby="m-view-lbl">
                {(['guided', 'clinic'] as const).map((v) => (
                  <button key={v} type="button" role="radio" aria-checked={props.view === v} onClick={() => { setOpen(null); props.onView(v) }}>
                    {v === 'guided' ? 'Guided' : 'Clinic'}
                  </button>
                ))}
              </div>
            </div>
            {props.view === 'guided' && SECTIONS.map(([id, label]) => (
              <a key={id} href="#/" onClick={(e) => { e.preventDefault(); go(id) }}>{label}{id === 'alerts' && props.unseen > 0 ? ` (${props.unseen})` : ''}</a>
            ))}
            <a href={props.detailHref} onClick={() => setOpen(null)}>Detailed view</a>
            <a href="#/admin" onClick={() => setOpen(null)}>Admin &amp; access{needsSetup ? ' · setup needed' : ''}</a>
            <div className="m-theme">
              <span id="m-theme-lbl">Appearance</span>
              <div className="m-seg" role="radiogroup" aria-labelledby="m-theme-lbl">
                {MODES.map((m) => (
                  <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => pick(m)}>
                    <span className="ti" aria-hidden="true">{THEME_ICON[m]}</span>
                    {THEME_LABEL[m]}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
