// Home sections driven by the doctor's own data: term cards, alerts, the pre-visit summary and the history chart.
import { useMemo, useState } from 'react'
import { PreVisitSummary } from '../../components/PreVisitSummary'
import { alertText } from '../../lib/format'
import { TERMS } from '../../lib/terms'
import type { DrAlert } from '../../lib/types'
import type { DoctorData, PatientRow } from '../../lib/useDoctorData'
import { ArrowRight, Check, Clock, Warn } from '../icons'
import { SEV_VAR, ago, byDay, dayNum, daysAgo, reporterLabel, shortDate, whoIsTold, windowDates, worstOf } from '../model'
import { patientHref, recordHref } from '../routes'

/* ---------- Term cards (schema/terms.json) ---------- */
const PALETTE: [string, string][] = [['#fde0d2', '#f6c0aa'], ['#fbedd0', '#f4d58f'], ['#dcefe3', '#b4dcc5'], ['#e6defa', '#cbbef2'], ['#f6e4d4', '#ead0b6'], ['#fde4d9', '#f5c2ae'], ['#e2ecf6', '#bfd3ea']]
const ICONS: Record<string, React.ReactNode> = {
  SE_RASH: <><circle cx="40" cy="40" r="30" fill="#fff" opacity=".55" /><circle cx="30" cy="34" r="5" fill="#e9785a" /><circle cx="46" cy="30" r="4" fill="#ef8a6e" /><circle cx="42" cy="48" r="6" fill="#e06a4a" /><circle cx="54" cy="44" r="3.5" fill="#ef8a6e" /><circle cx="28" cy="50" r="3" fill="#e9785a" /></>,
  SE_PARONYCHIA: <><rect x="24" y="14" width="32" height="54" rx="16" fill="#fff" opacity=".7" /><rect x="29" y="18" width="22" height="22" rx="10" fill="#f0b84a" /><path d="M33 26q7 6 14 0" stroke="#c68a1d" strokeWidth="3" fill="none" strokeLinecap="round" /></>,
  SE_DIARRHEA: <><path d="M40 12c10 16 20 26 20 38a20 20 0 0 1-40 0c0-12 10-22 20-38z" fill="#7cc2a3" /><ellipse cx="33" cy="48" rx="5" ry="8" fill="#fff" opacity=".55" /></>,
  SE_FATIGUE: <><path d="M52 56A24 24 0 1 1 46 14a18 18 0 0 0 6 42z" fill="#9b86e0" /><circle cx="56" cy="22" r="3" fill="#fff" /><circle cx="62" cy="34" r="2" fill="#fff" /></>,
  SE_DRY_SKIN: <><g stroke="#c9906a" strokeWidth="4" strokeLinecap="round"><path d="M40 14v52M18 27l44 26M18 53l44-26" /></g><circle cx="40" cy="40" r="7" fill="#fff" /></>,
  SE_DECREASED_APPETITE: <><path d="M14 40h52a26 26 0 0 1-52 0z" fill="#ef8a6e" /><rect x="10" y="36" width="60" height="7" rx="3.5" fill="#fff" /><path d="M32 30q4-10 0-18M44 30q4-10 0-18" stroke="#fff" strokeWidth="3.5" fill="none" strokeLinecap="round" opacity=".8" /></>,
  SE_STOMATITIS: <><path d="M16 40q24 26 48 0q-24-10-48 0z" fill="#e06a6a" /><path d="M20 40q20 8 40 0" stroke="#fff" strokeWidth="4" fill="none" /><circle cx="34" cy="48" r="3" fill="#fff" /></>,
}
const DEFAULT_ICON = <><circle cx="40" cy="40" r="26" fill="#fff" opacity=".6" /><path d="M20 42h10l5-10 8 18 5-8h12" fill="none" stroke="#e2673f" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" /></>

export function TermCards() {
  const cards = TERMS.filter((t) => t.everyday_words.length >= 2)
  const set = (suffix: string) => cards.map((t, i) => (
    <div key={t.term_code + suffix} className="term-card" style={{ background: `linear-gradient(170deg,${PALETTE[i % PALETTE.length][0]},${PALETTE[i % PALETTE.length][1]})` }}>
      <div className="words">
        Words like<q>{t.everyday_words[0]}</q><q>{t.everyday_words[1]}</q>
      </div>
      <div className="ill"><svg width="84" height="84" viewBox="0 0 80 80" aria-hidden="true">{ICONS[t.term_code] ?? DEFAULT_ICON}</svg></div>
      <div className="label">{t.label_term}</div>
    </div>
  ))
  return (
    <div className="marquee" aria-label="Everyday words and the label terms they map to">
      <div className="track">
        {set('')}
        <div aria-hidden="true" style={{ display: 'contents' }}>{set('-loop')}</div>
      </div>
    </div>
  )
}

/* ---------- Alerts ---------- */
const SHOWN = 5 // most urgent first; the rest behind "Show all"
const rankAlert =(a: DrAlert) => (a.alert_type === 'severe' ? 30 : a.alert_type === 'emergency_access' ? 20 : 0) + (a.escalation_level ?? 0)

export function AlertsCard({ data, alerts, nameOf, onToast }: { data: DoctorData; alerts: DrAlert[]; nameOf: (ref: string) => string; onToast: (m: string) => void }) {
  const [leaving, setLeaving] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const fresh = alerts.filter((a) => !a.seen_at).sort((a, b) => rankAlert(b) - rankAlert(a) || b.created_at.localeCompare(a.created_at))
  const time = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  const day = (iso: string) => ago(iso.slice(0, 10))
  return (
    <div className="panel reveal">
      <div className="panel-head">
        <h3>Your alerts</h3>
        <span className="live"><i />{fresh.length ? `${fresh.length} new` : 'All seen'}</span>
      </div>
      {fresh.length === 0 && <p className="empty-ok">You have seen every alert. New ones appear here first.</p>}
      {(showAll ? fresh : fresh.slice(0, SHOWN)).map((a) => {
        const sev = a.alert_type === 'severe'
        return (
          <div key={a.alert_id} className={`alert-row ${leaving === a.alert_id ? 'leaving' : ''}`}>
            <span className="a-ico" style={{ background: sev ? 'var(--severe)' : 'var(--coral-tint)', color: sev ? '#fff' : 'var(--coral-ink)' }}>{sev ? <Warn /> : <Clock />}</span>
            <div className="a-body">
              <div className="a-title">
                {alertText(a)}
                {a.alert_type === 'missed' && <LevelBars n={a.escalation_level ?? 1} />}
              </div>
              <div className="a-meta">
                <a href={patientHref(a.patient_ref)}>{nameOf(a.patient_ref)}</a> · <span className="mono">{a.patient_ref}</span> · {day(a.created_at)}, {time(a.created_at)}
              </div>
              <div className="a-told">Who is told: {whoIsTold(a)}</div>
            </div>
            <button
              type="button"
              className="seen-btn"
              onClick={() => {
                setLeaving(a.alert_id)
                setTimeout(() => { data.markSeen(a.alert_id); setLeaving(null) }, matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 380)
                onToast('Marked seen')
              }}
            >
              Mark seen
            </button>
          </div>
        )
      })}
      {fresh.length > SHOWN && (
        <button type="button" className="more" style={{ border: 0, background: 'none', padding: 0, marginTop: 14 }} aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>
          {showAll ? 'Show the most urgent only' : `Show all ${fresh.length} new alerts`}
        </button>
      )}
      <p className="check" style={{ marginTop: 16 }}><Check />Alerts are for your review. They never diagnose.</p>
    </div>
  )
}

export function LevelBars({ n }: { n: number }) {
  return (
    <span className="lvl" aria-label={`level ${n} of 3`}>
      {[1, 2, 3].map((k) => <i key={k} className={k <= n ? 'on' : ''} />)}
    </span>
  )
}

/* ---------- Pre-visit summary step ---------- */
export function SummaryStep({ focus, alerts }: { focus: PatientRow | undefined; alerts: DrAlert[] }) {
  return (
    <section className="band mint" id="summary">
      <div className="wrap step">
        <div className="reveal">
          <div className="eyebrow"><span className="step-no" style={{ background: 'var(--good-tint)', color: 'var(--good)' }}>3</span>One patient. One page.</div>
          <h2>Walk in prepared.<br /><span className="accent">The summary is ready.</span></h2>
          <p className="lede" style={{ fontWeight: 600, color: 'var(--ink)' }}>Built from templates. No AI model sees patient data.</p>
          {focus && (
            <div className="actions">
              <a className="btn btn-coral" href={patientHref(focus.patient_ref)}>Open {focus.patient.display_name}'s page <ArrowRight /></a>
            </div>
          )}
          <p className="small" style={{ marginTop: 12 }}>Every line comes from the check-ins stored in this browser.</p>
        </div>
        <div className="reveal">
          {focus ? (
            <PreVisitSummary patient={focus.patient} days={focus.days} entries={focus.entries} alerts={alerts.filter((a) => a.patient_ref === focus.patient_ref)} />
          ) : (
            <div className="panel"><p className="empty-ok">The summary appears once a patient's first check-in arrives.</p></div>
          )}
        </div>
      </div>
    </section>
  )
}

/* ---------- Symptoms per check-in chart ---------- */
export function SymptomChart({ rows }: { rows: PatientRow[] }) {
  const [ref, setRef] = useState<string | undefined>(rows[0]?.patient_ref)
  const row = rows.find((r) => r.patient_ref === ref) ?? rows[0]
  const [tip, setTip] = useState<string | null>(null)
  const geo = useMemo(() => {
    if (!row) return null
    const days = byDay(row.entries)
    const dates = windowDates(days)
    const counts = dates.map((d) => days.get(d)?.symptoms.length ?? 0)
    return { days, dates, max: Math.max(2, ...counts) }
  }, [row])
  if (!row || !geo) return <div className="cbox sand reveal"><p className="cap">Symptoms per check-in · last 21 days</p><p className="empty-ok">No check-ins yet.</p></div>

  const W = 520, H = 250, L = 34, R = 10, T = 22, B = 34, N = geo.dates.length, bw = (W - L - R) / N
  const y = (v: number) => T + (H - T - B) * (1 - v / geo.max)
  const ticks = Array.from({ length: geo.max + 1 }, (_, k) => k)
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
  const describe = (date: string) => {
    const d = geo.days.get(date)
    return d
      ? `${shortDate(date)}: ${d.symptoms.map((s) => `${s.term} (${s.severity}${s.forReview ? ', for review' : ''})`).join(', ')} · answered by ${reporterLabel(d.reporter)}.`
      : `${shortDate(date)}: no symptom report.`
  }

  return (
    <div className="cbox sand reveal">
      <p className="cap">Symptoms per check-in · last 21 days</p>
      <h3>{row.patient.display_name} · {row.patient.drug_name} {row.patient.drug_version}</h3>
      {rows.length > 1 && (
        <div className="seg" role="group" aria-label="Patient">
          {rows.map((r) => (
            <button key={r.patient_ref} type="button" aria-pressed={r.patient_ref === row.patient_ref} onClick={() => { setRef(r.patient_ref); setTip(null) }}>
              {r.patient.display_name}
            </button>
          ))}
        </div>
      )}
      <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Bar chart of symptoms per check-in for ${row.patient.display_name}`} key={row.patient_ref}>
        {ticks.map((v) => (
          <g key={v}>
            <line className="gl" x1={L} x2={W - R} y1={y(v)} y2={y(v)} />
            <text x={L - 10} y={y(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {geo.dates.map((date, i) => {
          const d = geo.days.get(date)
          const n = d?.symptoms.length ?? 0
          const x = L + i * bw + 3, w = bw - 6
          const worst = d ? worstOf(d.symptoms) : null
          const last = i === N - 1
          return (
            <g key={date} className="col" tabIndex={0} role="img" aria-label={describe(date)} onMouseEnter={() => setTip(describe(date))} onFocus={() => setTip(describe(date))} onClick={() => setTip(describe(date))}>
              <rect x={L + i * bw} y={T} width={bw} height={H - T - B} fill="transparent" />
              {n > 0 && worst && (
                <rect className="bar" x={x} y={y(n)} width={w} height={y(0) - y(n)} rx={5} fill={SEV_VAR[worst]}>
                  <animate attributeName="height" from="0" to={y(0) - y(n)} dur={reduce ? '0.01s' : '.6s'} begin={`${i * 0.025}s`} fill="freeze" />
                  <animate attributeName="y" from={y(0)} to={y(n)} dur={reduce ? '0.01s' : '.6s'} begin={`${i * 0.025}s`} fill="freeze" />
                </rect>
              )}
              {d?.symptoms.some((s) => s.forReview) && <circle cx={x + w / 2} cy={y(n) - 9} r={4.5} fill="var(--review)" />}
              {d && d.reporter !== 'self' && <text x={x + w / 2} y={H - B + 28} textAnchor="middle" style={{ fill: 'var(--coral-ink)', fontWeight: 700 }}>C</text>}
              {(i % 5 === 0 || last) && <text x={x + w / 2} y={H - B + 15} textAnchor="middle">{last && date === daysAgo(0) ? 'Today' : dayNum(date)}</text>}
            </g>
          )
        })}
      </svg>
      <p className="chart-tip">{tip ?? 'Point at a bar to read the day.'}</p>
      <div className="legend" style={{ marginTop: 8 }}>
        <span><i style={{ background: 'var(--mild)' }} />Mild</span>
        <span><i style={{ background: 'var(--moderate)' }} />Moderate</span>
        <span><i style={{ background: 'var(--severe)' }} />Severe</span>
        <span><i style={{ background: 'var(--review)', borderRadius: '50%' }} />For review</span>
        <span><b style={{ color: 'var(--coral-ink)' }}>C</b> Caregiver answered</span>
      </div>
      <p className="small" style={{ marginTop: 10 }}>Bar colour is the most severe symptom that day.</p>
      <a className="more" href={recordHref(row.patient_ref)}>Open the full record <ArrowRight /></a>
    </div>
  )
}

