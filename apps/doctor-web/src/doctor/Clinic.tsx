// Clinic view (DW-32): the compact daily screen for doctors who use SafeSignal every day.
// Alerts queue and patient list on the left, the open patient on the right. Same data as the Guided view.
import { useEffect, useRef, useState } from 'react'
import { alertText } from '../lib/format'
import type { DrAlert } from '../lib/types'
import type { DoctorData, PatientRow } from '../lib/useDoctorData'
import { HistoryGrid } from './HistoryGrid'
import { LevelBars } from './home/Live'
import { ArrowRight, Clock, Search, Warn } from './icons'
import { SEV_VAR, ago, byDay, latestTrend, longDate, nameFor, whoIsTold, windowDates, worstOf } from './model'
import { patientHref, recordHref } from './routes'
import { summarySections } from './summary'

type Filter = 'all' | 'alerts' | 'worse'
const urgent = (a: DrAlert) => a.alert_type === 'severe' || a.alert_type === 'emergency_access' || (a.escalation_level ?? 0) >= 3
const rank = (a: DrAlert) => (urgent(a) ? 100 : 0) + (a.alert_type === 'severe' ? 10 : 0) + (a.escalation_level ?? 0)
const STRIP_H = { mild: 5, moderate: 9, severe: 14 } as const

export function Clinic({ data, rows, gone, alerts, openRef, syncNote, orgName, onToast }: {
  data: DoctorData; rows: PatientRow[]; gone: PatientRow[]; alerts: DrAlert[]; openRef: string | null; syncNote: string; orgName: (id: string) => string; onToast: (m: string) => void
}) {
  const [filter, setFilter] = useState<Filter>('all')
  const [q, setQ] = useState('')
  const [leaving, setLeaving] = useState<string | null>(null)
  const search = useRef<HTMLInputElement>(null)
  const all = [...rows, ...gone]
  const nameOf = nameFor(all)
  const fresh = alerts.filter((a) => !a.seen_at).sort((a, b) => rank(b) - rank(a) || b.created_at.localeCompare(a.created_at))
  const norm = q.trim().toLowerCase().replace(/^pt_/, '')
  const list = rows
    .filter((r) => filter !== 'alerts' || r.unseenAlerts > 0)
    .filter((r) => filter !== 'worse' || latestTrend(byDay(r.entries)) === 'worse')
    .filter((r) => !norm || r.patient.display_name.toLowerCase().includes(norm) || r.patient_ref.slice(3).startsWith(norm))
  const open = all.find((r) => r.patient_ref === openRef) ?? list[0]

  // Keyboard: / to search, j and k to move between patients.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = /input|select|textarea/i.test((document.activeElement as HTMLElement | null)?.tagName ?? '')
      if (e.key === '/' && !typing) { e.preventDefault(); search.current?.focus(); return }
      if (e.key === 'Escape' && document.activeElement === search.current) { search.current?.blur(); return }
      if (typing || (e.key !== 'j' && e.key !== 'k') || !list.length) return
      const i = Math.max(0, list.findIndex((r) => r.patient_ref === open?.patient_ref))
      location.hash = patientHref(list[(i + (e.key === 'j' ? 1 : list.length - 1)) % list.length].patient_ref)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [list, open])

  const markSeen = (id: string) => {
    setLeaving(id)
    setTimeout(() => { data.markSeen(id); setLeaving(null) }, matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 300)
    onToast('Marked seen')
  }

  return (
    <main className="wrap clinic" id="clinic">
      <div className="cl-bar">
        <div>
          <h1 className="cl-title">Today</h1>
          <p className="cl-sub">{fresh.length} new alert{fresh.length === 1 ? '' : 's'} · {rows.length} patient{rows.length === 1 ? '' : 's'} sharing · {syncNote}</p>
        </div>
        <label className="cl-search" htmlFor="cl-q">
          <Search size={16} />
          <input id="cl-q" ref={search} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a patient" aria-label="Find a patient by name or reference" autoComplete="off" />
          <kbd>/</kbd>
        </label>
      </div>
      <div className="cl-grid">
        <div className="cl-left">
          <section className="cl-card" aria-labelledby="cl-alerts-h">
            <div className="cl-h">
              <h2 id="cl-alerts-h">Alerts</h2>
              <span className={`cl-count ${fresh.length ? '' : 'zero'}`}>{fresh.length ? `${fresh.length} new` : 'All seen'}</span>
            </div>
            {fresh.length === 0 && <p className="cl-empty">All caught up. New alerts appear here first.</p>}
            {fresh.map((a) => {
              const now = urgent(a)
              return (
                <div key={a.alert_id} className={`cl-alert ${now ? 'now' : 'watch'} ${leaving === a.alert_id ? 'leaving' : ''}`}>
                  <span className="ic">{now ? <Warn size={15} /> : <Clock size={15} />}</span>
                  <div style={{ minWidth: 0 }}>
                    <div className="t">{alertText(a)}{a.alert_type === 'missed' && <LevelBars n={a.escalation_level ?? 1} />}</div>
                    <div className="m">
                      <a href={patientHref(a.patient_ref)}>{nameOf(a.patient_ref)}</a> · {ago(a.created_at.slice(0, 10))}, {new Date(a.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </div>
                    <details><summary>Who is told</summary><p>{whoIsTold(a)}</p></details>
                  </div>
                  <button type="button" className="cl-mini" onClick={() => markSeen(a.alert_id)}>Mark seen</button>
                </div>
              )
            })}
          </section>
          <section className="cl-card" aria-labelledby="cl-pts-h">
            <div className="cl-h">
              <h2 id="cl-pts-h">Patients</h2>
              <div className="cl-chips" role="group" aria-label="Filter patients">
                {(['all', 'alerts', 'worse'] as Filter[]).map((f) => (
                  <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === 'all' ? 'All' : f === 'alerts' ? 'Alerts' : 'Worse'}</button>
                ))}
              </div>
            </div>
            <div role="listbox" aria-label="Patients">
              {list.map((r) => <Row key={r.patient_ref} r={r} selected={r.patient_ref === open?.patient_ref} />)}
              {list.length === 0 && (
                <p className="cl-empty">
                  {rows.length === 0 ? 'No patient records yet. They appear after the first check-in sealed to your care team.' : `No patient matches${q ? ` “${q}”` : ' this filter'}.`}
                </p>
              )}
            </div>
            {gone.length > 0 && <p className="small cl-keys">No longer shared: {gone.map((r) => <a key={r.patient_ref} href={patientHref(r.patient_ref)} style={{ marginRight: 8 }}>{r.patient.display_name}</a>)}</p>}
            <p className="small cl-keys">Press / to search · j and k to move between patients</p>
          </section>
        </div>
        {open ? <Pane key={open.patient_ref} row={open} alerts={alerts} orgName={orgName} /> : (
          <section className="cl-pane">
            <h2 style={{ fontSize: '1.5rem' }}>No patient open</h2>
            <p className="cl-sub" style={{ marginTop: 8 }}>
              If this browser doesn't hold your care team's key yet, set it up in Admin &amp; access. An emergency hospital opens a history only through emergency access, which is there too.
            </p>
            <div className="pp-actions"><a className="btn btn-coral" href="#/admin">Admin &amp; access <ArrowRight /></a></div>
          </section>
        )}
      </div>
    </main>
  )
}

function Row({ r, selected }: { r: PatientRow; selected: boolean }) {
  const days = byDay(r.entries)
  const trend = latestTrend(days)
  const p = r.patient
  return (
    <a className="cl-row" role="option" aria-selected={selected} href={patientHref(r.patient_ref)}>
      <span className="nm">{p.display_name}</span>
      <span className="right">
        {r.unseenAlerts > 0 && <span className="tagx alert">{r.unseenAlerts} new</span>}
        <span className={`cl-trend ${trend}`}>{trend === 'worse' ? '↗' : trend === 'better' ? '↘' : '→'} {trend}</span>
      </span>
      <span className="sub">{p.age_years} · {p.drug_name} {p.drug_version} · last check-in {ago(p.last_checkin)}{p.shared === 0 ? ' · no longer shared' : ''}</span>
      <span className="cl-strip" aria-hidden="true">
        {windowDates(days).map((d) => {
          const w = days.get(d) ? worstOf(days.get(d)!.symptoms) : null
          return <i key={d} style={w ? { height: STRIP_H[w], background: SEV_VAR[w] } : undefined} />
        })}
      </span>
    </a>
  )
}

function Pane({ row, alerts, orgName }: { row: PatientRow; alerts: DrAlert[]; orgName: (id: string) => string }) {
  const p = row.patient
  const days = byDay(row.entries)
  const last = [...days.values()].pop()
  const symptomFreeLatest = !!p.last_checkin && (!last || p.last_checkin > last.date)
  const mine = alerts.filter((a) => a.patient_ref === row.patient_ref)
  const fresh = mine.filter((a) => !a.seen_at)
  const sections = summarySections(p, row.days, row.entries, mine)
  const summary = [...(sections.find((s) => s.title === 'Check-ins')?.items.slice(0, 2) ?? []), ...(sections.find((s) => s.title === 'For review')?.items ?? [])].slice(0, 4)
  return (
    <section className="cl-pane" aria-labelledby="cl-pane-h">
      <div className="cl-ph">
        <div>
          <h2 id="cl-pane-h">{p.display_name}</h2>
          <p className="meta">{p.age_years} years · {p.drug_name} {p.drug_version} · <span className="mono">{p.patient_ref}</span></p>
        </div>
        <a className="btn btn-ghost" href={recordHref(row.patient_ref)}>Full record <ArrowRight /></a>
      </div>
      {p.shared === 0 && <div className="banner" style={{ background: 'var(--sand)', marginTop: 14 }}>No longer shared: what arrived before stays here, read-only.</div>}
      {fresh.length > 0 && (
        <div className="banner" style={{ background: 'var(--coral-tint)', marginTop: 14 }}>
          <b style={{ color: 'var(--coral-ink)' }}>{fresh.length} new:</b>&nbsp;{fresh.map((a) => alertText(a)).join(' · ')}
        </div>
      )}
      <div className="cl-facts">
        <span>Last check-in <b>{ago(p.last_checkin)}</b></span>
        <span>Trend <b>{latestTrend(days)}</b></span>
        <span>Symptom reports, 21 days <b>{row.days.filter((d) => d.date >= new Date(Date.now() - 21 * 864e5).toISOString().slice(0, 10)).length}</b></span>
        <span>Care team <b>{orgName(p.org_id)}</b></span>
      </div>
      <div className="cl-sec">
        {symptomFreeLatest || !last ? (
          <>
            <h3>Latest check-in{p.last_checkin ? ` · ${longDate(p.last_checkin)}` : ''}</h3>
            <p>{symptomFreeLatest ? 'No symptoms reported at the latest check-in.' : 'No check-in received yet.'}</p>
          </>
        ) : (
          <>
            <h3>Latest report · {longDate(last.date)}</h3>
            <div className="syms2">
              {last.symptoms.map((s) => (
                <span key={s.term} className="symchip">
                  <span className="sev" style={{ background: SEV_VAR[s.severity] }} />
                  {s.term} <small>{s.severity} · {s.onset}</small>
                  {s.forReview && <span className="tagx review">For review</span>}
                  {s.offLabel && <span className="tagx">Not on the drug label</span>}
                </span>
              ))}
            </div>
          </>
        )}
      </div>
      {summary.length > 0 && (
        <div className="cl-sec">
          <h3>Summary · template, no AI</h3>
          <ul className="cl-sum">{summary.map((l) => <li key={l}>{l}</li>)}</ul>
        </div>
      )}
      <HistoryGrid entries={row.entries} />
    </section>
  )
}
