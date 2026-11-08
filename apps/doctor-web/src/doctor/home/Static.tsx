// Home sections with fixed content: connectors, how-it-works framing, promise, escalation table, privacy, compare, FAQ, footer.
import { useState } from 'react'
import type { PatientRow } from '../../lib/useDoctorData'
import { ArrowDown, ArrowRight, Check, Logo, Shield } from '../icons'
import { goSection } from '../routes'
import { Finder } from './Hero'

export function Connect({ to }: { to: string }) {
  return (
    <div className="connect">
      <button type="button" className="arrow-btn" aria-label="Next section" onClick={() => goSection(to)}>
        <ArrowDown />
      </button>
    </div>
  )
}

export function Step({ id, band, no, noStyle, eyebrow, title, accent, lede, children, aside }: {
  id: string; band?: 'butter' | 'mint'; no: number; noStyle: React.CSSProperties; eyebrow: string; title: string; accent: string; lede: string; children?: React.ReactNode; aside: React.ReactNode
}) {
  return (
    <section className={`band ${band ?? ''}`} id={id}>
      <div className="wrap step">
        <div className="reveal">
          <div className="eyebrow"><span className="step-no" style={noStyle}>{no}</span>{eyebrow}</div>
          <h2>{title}<br /><span className="accent">{accent}</span></h2>
          <p className="lede">{lede}</p>
          {children && <div className="actions">{children}</div>}
        </div>
        {aside}
      </div>
    </section>
  )
}

export function Promise() {
  return (
    <section className="wrap" style={{ marginTop: 72 }}>
      <div className="promise">
        <div className="pcard2 reveal">
          <span className="ic" style={{ background: 'var(--coral-tint)', color: 'var(--coral-ink)' }}><Shield size={24} /></span>
          <div><small>The promise</small><p><b>The service relays sealed check-ins.</b> It can never open one.</p></div>
        </div>
        <div className="pcard2 reveal">
          <span className="ic" style={{ background: 'var(--good-tint)', color: 'var(--good)' }}><Check size={24} /></span>
          <div><small>Access checks</small><p><b>19 of 19 pass</b> on contract 2.2 (evals/doctor).</p></div>
        </div>
      </div>
      <div className="divider" aria-hidden="true"><Logo size={30} flat /></div>
    </section>
  )
}

const TOLD: [string, boolean[]][] = [
  ['Patient (reminder)', [true, true, false, false]],
  ['Caregiver', [true, true, true, true]],
  ['Care team', [true, true, true, true]],
  ['Emergency contacts', [false, true, false, false]],
]
export function WhoIsToldTable() {
  const [col, setCol] = useState<number | null>(null)
  const heads: [string, string, string][] = [['Missed', 'level 1–2', '#fbedd0'], ['Missed', 'level 3', '#fde0d2'], ['Severe', 'symptom', '#f6cfc8'], ['Emergency', 'access', '#e6defa']]
  return (
    <div className="cbox white reveal">
      <p className="cap">Escalation rules (D-068)</p>
      <h3>Who is told, for each alert</h3>
      <div className="told" onMouseLeave={() => setCol(null)}>
        <table>
          <thead>
            <tr>
              <th />
              {heads.map(([a, b, bg], i) => (
                <th key={i} className="col" style={{ background: bg }} onMouseEnter={() => setCol(i)}>{a}<small>{b}</small></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {TOLD.map(([who, cells]) => (
              <tr key={who}>
                <th className="rowh">{who}</th>
                {cells.map((yes, i) => (
                  <td key={i} className={yes ? 'yes' : 'no'} style={col === i ? { outline: '2px solid var(--coral)' } : undefined} aria-label={yes ? 'told' : 'not told'}>{yes ? '✓' : '—'}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small" style={{ marginTop: 14 }}>
        Level = consecutive missed check-ins, capped at 3. Emergency contacts are only the ones the patient consented to. This app shows the rule; it doesn't receive
        delivery records.
      </p>
    </div>
  )
}

export function Privacy() {
  const tiles: [string, string][] = [
    ['No audio', "Speech is processed on the patient's device."],
    ['No transcripts', 'You get terms, severity and onset.'],
    ['No cloud AI', 'Summaries come from templates.'],
    ['No tracking', 'No analytics, no third-party scripts.'],
  ]
  return (
    <section className="wrap" id="privacy" style={{ marginTop: 28 }}>
      <div className="privacy reveal">
        <div>
          <p className="kicker">Privacy</p>
          <h2>What never reaches this screen.</h2>
          <p className="lede" style={{ marginTop: 12, fontSize: '1rem' }}>Only your care team's key, held in this browser, can open a check-in. Here is everything that stays out.</p>
          <div className="tiles">
            {tiles.map(([b, s]) => (
              <div key={b} className="tile">
                <span className="ok"><Check size={12} /></span>
                <div><b>{b}</b><span>{s}</span></div>
              </div>
            ))}
          </div>
          <p className="small" style={{ marginTop: 16 }}>The record belongs to the care team, so it stays when a doctor leaves.</p>
        </div>
        <div className="art" aria-hidden="true">
          <svg viewBox="0 0 360 300">
            <defs>
              <linearGradient id="pv-env" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff7ef" /><stop offset="1" stopColor="#f3e2d2" /></linearGradient>
              <linearGradient id="pv-flap" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f7a585" /><stop offset="1" stopColor="#e5714b" /></linearGradient>
              <linearGradient id="pv-lock" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ffd877" /><stop offset="1" stopColor="#eab23f" /></linearGradient>
              <linearGradient id="pv-clip" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#a9dcc4" /><stop offset="1" stopColor="#6dbb97" /></linearGradient>
            </defs>
            <ellipse cx="180" cy="270" rx="130" ry="14" fill="#2d2725" opacity=".10" />
            <g transform="rotate(-8 110 150)">
              <rect x="40" y="70" width="120" height="160" rx="18" fill="url(#pv-clip)" />
              <rect x="56" y="96" width="88" height="118" rx="10" fill="#fffdf9" />
              <rect x="80" y="62" width="40" height="18" rx="8" fill="#4c7f6a" />
              <rect x="68" y="114" width="60" height="8" rx="4" fill="#e6d8ca" />
              <rect x="68" y="132" width="44" height="8" rx="4" fill="#e6d8ca" />
              <rect x="68" y="150" width="54" height="8" rx="4" fill="#f2c14e" />
              <rect x="68" y="168" width="36" height="8" rx="4" fill="#ee8a5f" />
              <circle cx="124" cy="190" r="6" fill="#7c62cf" />
            </g>
            <g transform="rotate(6 240 170)">
              <rect x="150" y="110" width="170" height="120" rx="18" fill="url(#pv-env)" stroke="#e7d3c1" strokeWidth="2" />
              <path d="M150 128 235 186 320 128" fill="none" stroke="#e4cdb8" strokeWidth="3" />
              <path d="M152 118q83 70 166 0V112a14 14 0 0 0-14-14H166a14 14 0 0 0-14 14z" fill="url(#pv-flap)" />
              <g transform="translate(212 150)">
                <path d="M10 0v-10a13 13 0 0 1 26 0V0" fill="none" stroke="#b68524" strokeWidth="7" strokeLinecap="round" />
                <rect x="0" y="-2" width="46" height="40" rx="10" fill="url(#pv-lock)" />
                <circle cx="23" cy="14" r="5" fill="#8a5d13" />
                <rect x="21" y="16" width="4" height="10" rx="2" fill="#8a5d13" />
              </g>
            </g>
            <path d="M300 52l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" fill="#f2c14e" />
            <path d="M60 40l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" fill="#ef8262" />
            <circle cx="330" cy="96" r="5" fill="#7cc2a3" />
            <circle cx="36" cy="118" r="4" fill="#7c62cf" />
          </svg>
        </div>
      </div>
      <div className="guarantee reveal">
        <span className="ck"><Check size={24} /></span>
        <div>
          <h3>Emergency access is logged, every time.</h3>
          <p>An emergency hospital the patient chose can open the history only by stating a reason. The caregiver and the care team are told, and nothing stays in that browser after it is closed.</p>
        </div>
      </div>
    </section>
  )
}

export function Compare({ rows }: { rows: PatientRow[] }) {
  const [on, setOn] = useState(true)
  const off = ['Symptoms recalled from memory at the visit', 'Nothing recorded between appointments', 'A patient who goes quiet goes unnoticed', 'A new doctor starts with an empty chart', 'An emergency team knows nothing of recent days']
  const yes = ["Check-ins in label terms, on the trial's schedule", 'A 21-day history and a pre-visit summary', 'Missed check-ins escalate from level 1 to 3', 'The record stays with the care team', 'Emergency access with a logged reason']
  return (
    <section className="wrap" id="compare">
      <div className="compare reveal" data-on={on}>
        <div className="center-head">
          <p className="kicker">Ready for the next visit</p>
          <h2>Turn the signal <span className="accent">on.</span></h2>
          <p className="lede">One side is the gap between visits. The other is a history you can read before the patient sits down.</p>
        </div>
        <div className="cmp">
          <div className="side off"><small>Signal off, between visits</small><ul>{off.map((t) => <li key={t}><i>↓</i>{t}</li>)}</ul></div>
          <button type="button" className="switch" aria-pressed={on} aria-label={on ? 'Signal on. Turn off to compare' : 'Signal off. Turn on'} onClick={() => setOn(!on)}>
            <svg viewBox="0 0 170 190" aria-hidden="true">
              <defs>
                <linearGradient id="sw-b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fbf1e6" /><stop offset="1" stopColor="#e9d9c7" /></linearGradient>
                <linearGradient id="sw-k" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f7a283" /><stop offset="1" stopColor="#df6a43" /></linearGradient>
              </defs>
              <rect x="35" y="40" width="100" height="120" rx="24" fill="url(#sw-b)" />
              <rect x="57" y="58" width="56" height="84" rx="14" fill="#d9c6b2" />
              <rect x="60" y="72" width="50" height="8" rx="4" fill="#7cc2a3" />
              <g className="knob"><rect x="60" y="92" width="50" height="48" rx="12" fill="url(#sw-k)" /><rect x="66" y="96" width="38" height="8" rx="4" fill="#fff" opacity=".35" /></g>
              <g className="spark">
                <path d="M24 50l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="#f2c14e" />
                <path d="M148 34l2.5 6 6 2.5-6 2.5-2.5 6-2.5-6-6-2.5 6-2.5z" fill="#f2c14e" />
                <path d="M136 70l8-10 14-16" fill="none" stroke="#5cc48b" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="20" cy="100" r="3" fill="#ef8262" />
                <circle cx="156" cy="98" r="3" fill="#ef8262" />
              </g>
            </svg>
            <span className="lbl">{on ? 'Signal on · tap to compare' : 'Signal off · tap to turn on'}</span>
          </button>
          <div className="side on"><small>Signal on, with SafeSignal</small><ul>{yes.map((t) => <li key={t}><i>↑</i>{t}</li>)}</ul></div>
        </div>
        <Finder rows={rows} id="q-bottom" placeholder="4b82d0c6, or a name" prefix="pt_" center />
      </div>
    </section>
  )
}

const FAQ: [string, string][] = [
  ["Who can see a patient's history?", "Only doctors in the care team the patient shares with, from a browser that holds that care team's key. An admin grants the key to each member. The service stores sealed envelopes and cannot open them."],
  ['What does “for review” mean?', "The patient's device flagged a possible link between the symptom and the drug. It is a flag for you to look at, never a cause or a diagnosis."],
  ['What does “C” mean in the history?', "The caregiver answered that day's check-in instead of the patient. Partly answered check-ins are marked in the full record."],
  ['Why would a patient show “no longer shared”?', 'The patient stopped sharing with your care team. What arrived before stays here, read-only, and nothing new comes in.'],
  ['What happens at each escalation level?', 'Level 1 is one missed check-in, level 2 is two in a row, level 3 is three or more. Levels 1 and 2 tell the patient, the caregiver and the care team. Level 3 also tells the emergency contacts the patient consented to.'],
  ['Does any AI read patient data?', "No. Speech is processed on the patient's device. The pre-visit summary is built from fixed templates, and nothing is sent to a cloud AI or analytics service."],
  ["Why can't I see my patients in another browser?", "Your personal key lives in this browser. A key grant made for this browser can't be opened in another one. Ask your admin to grant the care-team key again for the new browser."],
  ['When can an emergency hospital read the history?', 'Only a hospital the patient chose at setup, only through emergency access, and only with a stated reason. Each access is logged and the caregiver and care team are told.'],
]
export function Faq({ guideHref }: { guideHref: string }) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <section className="wrap" id="questions">
      <div className="faq">
        <div className="faq-head">
          <p className="kicker">Questions</p>
          <h2 style={{ marginTop: 8 }}>Before you open a record.</h2>
          <p className="lede" style={{ fontSize: '1rem', marginTop: 14 }}>Short answers. The detailed view explains every field.</p>
          <a className="more" href={guideHref}>Read the detailed view <ArrowRight /></a>
        </div>
        <div>
          {FAQ.map(([q, a], i) => (
            <div key={q} className="qa">
              <button type="button" id={`qb${i}`} aria-expanded={open === i} aria-controls={`qa${i}`} onClick={() => setOpen(open === i ? null : i)}>
                <span>{q}</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
              </button>
              <div className="ans" id={`qa${i}`} role="region" aria-labelledby={`qb${i}`}><div><p>{a}</p></div></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export function Footer({ detailHref }: { detailHref: string }) {
  const sec = (id: string, label: string) => (
    <li><a href="#/" onClick={(e) => { e.preventDefault(); goSection(id) }}>{label}</a></li>
  )
  return (
    <footer className="wrap">
      <div className="fcols">
        <div><h4>Doctor view</h4><ul>{sec('patients', 'Your patients')}{sec('alerts', 'Alerts')}{sec('summary', 'Pre-visit summary')}{sec('history', 'History and escalation')}</ul></div>
        <div><h4>Full record</h4><ul><li><a href={detailHref}>Full record</a></li><li><a href="#/guide">Field meanings</a></li><li><a href="#/guide">Screen map</a></li></ul></div>
        <div><h4>Access</h4><ul><li><a href="#/admin">Care-team keys</a></li><li><a href="#/admin">Emergency access</a></li><li><a href="#/caregiver">Caregiver view</a></li></ul></div>
        <div><h4>About this view</h4><ul>{sec('privacy', 'Privacy rules')}{sec('questions', 'Questions')}<li><a href="#/guide">Screen map</a></li></ul></div>
      </div>
      <div className="fbot">
        <a className="brand" href="#/" style={{ fontSize: '1.1rem' }}><Logo size={28} flat /><span>Safe<b>Signal</b></span></a>
        <span className="small">HACK1984 · Side-Effect Sentinel · doctor view. Medical history only; flags are for your review, never a diagnosis.</span>
        <nav><a href="#/" onClick={(e) => { e.preventDefault(); goSection('privacy') }}>Privacy</a><a href="#/guide">Field meanings</a><a href="#/" onClick={(e) => { e.preventDefault(); goSection('questions') }}>Questions</a></nav>
      </div>
    </footer>
  )
}
