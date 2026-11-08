// Home hero: what this view is, a patient finder, and a day-by-day player of one patient's last 21 days.
import { useEffect, useMemo, useRef, useState } from 'react'
import type { PatientRow } from '../../lib/useDoctorData'
import { ArrowRight, Check, Search } from '../icons'
import { SEV_VAR, byDay, longDate, reporterLabel, windowDates } from '../model'
import { patientHref } from '../routes'

const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches

export function Hero({ rows, focus, syncNote }: { rows: PatientRow[]; focus: PatientRow | undefined; syncNote: string }) {
  return (
    <section className="wrap hero" id="top">
      <div>
        <h1>
          <span>Every check-in.</span>
          <span>Before the visit.</span>
          <span className="accent">In one view.</span>
        </h1>
        <p className="lede">
          Your patients check in by voice at home. Their device turns it into clinical terms and seals it to your care team. You read the history, the alerts and a
          summary before they walk in.
        </p>
        <Finder rows={rows} id="q-hero" placeholder="Name or reference, e.g. Walter" />
        <p className="check hero-note">
          <Check />
          {syncNote}
        </p>
      </div>
      {focus ? <Player key={focus.patient_ref} row={focus} /> : <EmptyPlayer />}
    </section>
  )
}

export function Finder({ rows, id, placeholder, prefix, center }: { rows: PatientRow[]; id: string; placeholder: string; prefix?: string; center?: boolean }) {
  const [q, setQ] = useState('')
  const [msg, setMsg] = useState('')
  const [open, setOpen] = useState(false)
  const norm = q.trim().toLowerCase().replace(/^pt_/, '')
  const hits = norm ? rows.filter((r) => r.patient.display_name.toLowerCase().includes(norm) || r.patient_ref.slice(3).startsWith(norm)) : []
  const openRow = (r: PatientRow) => {
    setOpen(false)
    setMsg('')
    location.hash = patientHref(r.patient_ref)
  }
  return (
    <>
      <form
        className="find"
        autoComplete="off"
        onSubmit={(e) => {
          e.preventDefault()
          if (!norm) return setMsg('Type a name or a reference, for example pt_ and 8 characters.')
          if (!hits.length) return setMsg(`No patient sharing with you matches “${q.trim()}”. Patients appear only while they share with your care team.`)
          openRow(hits[0])
        }}
      >
        <label htmlFor={id}>
          {prefix ? <span className="mono" style={{ color: 'var(--muted)', fontWeight: 500 }}>{prefix}</span> : <span style={{ color: 'var(--muted)' }}><Search /></span>}
          <input id={id} value={q} placeholder={placeholder} aria-label="Find a patient" onChange={(e) => { setQ(e.target.value); setOpen(true) }} onBlur={() => setTimeout(() => setOpen(false), 150)} />
        </label>
        <button className="btn btn-coral" type="submit">
          Open patient <ArrowRight />
        </button>
        {open && hits.length > 0 && (
          <div className="suggest">
            {hits.map((r) => (
              <button key={r.patient_ref} type="button" onMouseDown={(e) => { e.preventDefault(); openRow(r) }}>
                <b>{r.patient.display_name}</b>
                <span className="mono small">{r.patient_ref}</span>
              </button>
            ))}
          </div>
        )}
      </form>
      <p className="find-msg small" aria-live="polite" style={center ? { textAlign: 'center' } : undefined}>{msg}</p>
    </>
  )
}

function Player({ row }: { row: PatientRow }) {
  const days = useMemo(() => byDay(row.entries), [row.entries])
  const dates = useMemo(() => windowDates(days), [days])
  const last = dates.length - 1
  const [i, setI] = useState(() => (reduced() ? last : 0))
  const [playing, setPlaying] = useState(() => !reduced())
  const [tapped, setTapped] = useState(false)
  const t = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (!playing) return
    t.current = window.setInterval(() => setI((x) => (x >= last ? x : x + 1)), 1100)
    return () => clearInterval(t.current)
  }, [playing, last])
  useEffect(() => {
    if (i >= last) setPlaying(false)
  }, [i, last])
  const date = dates[i]
  const d = days.get(date)
  const p = row.patient

  return (
    <div className="player" aria-label={`${p.display_name}'s last 21 days, day by day`}>
      <div className="screen">
        <span className="blob" style={{ width: 220, height: 220, background: '#fbd3c2', right: -60, top: 60 }} />
        <span className="blob" style={{ width: 160, height: 160, background: '#f9e3b8', left: -50, top: 180 }} />
        <div className="pill" style={{ position: 'relative' }}>
          <i>{p.display_name[0]}</i>
          {p.display_name} · {p.age_years} · {p.drug_name} {p.drug_version}
        </div>
        {!tapped && <span className="tap">Tap a day</span>}
        <div style={{ position: 'relative', marginTop: 'auto' }}>
          <div className="day-big">{longDate(date)}</div>
          <div className="day-sub">
            {d ? `${d.status === 'partial' ? 'Partial check-in' : 'Check-in'} · answered by ${reporterLabel(d.reporter)} · trend ${d.trend}` : 'No symptom report this day'}
          </div>
          <div className="syms" key={date}>
            {d ? (
              d.symptoms.map((s, k) => (
                <div key={s.term} className="sym" style={{ animationDelay: `${k * 70}ms` }}>
                  <span className="sev" style={{ background: SEV_VAR[s.severity] }} />
                  {s.term}
                  {s.forReview && <span className="rv" title="For review" />}
                  <small>{s.severity} · {s.onset}</small>
                </div>
              ))
            ) : (
              <div className="none">Nothing was reported.</div>
            )}
          </div>
        </div>
        <div className="controls">
          <button
            type="button"
            className="play"
            aria-label={playing ? 'Pause' : 'Play'}
            onClick={() => {
              if (!playing && i >= last) setI(0)
              setPlaying(!playing)
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              {playing ? (
                <>
                  <rect x="6" y="5" width="4" height="14" rx="1" />
                  <rect x="14" y="5" width="4" height="14" rx="1" />
                </>
              ) : (
                <path d="M7 5v14l12-7z" />
              )}
            </svg>
          </button>
          <div className="scrub" role="group" aria-label="Days">
            {dates.map((x, k) => (
              <button
                key={x}
                type="button"
                aria-label={longDate(x)}
                className={`${days.has(x) ? 'has' : ''} ${k < i ? 'done' : ''} ${k === i ? 'cur' : ''}`}
                onClick={() => { setI(k); setPlaying(false); setTapped(true) }}
              />
            ))}
          </div>
          <span className="tc">{i + 1} / {dates.length}</span>
        </div>
      </div>
    </div>
  )
}

function EmptyPlayer() {
  return (
    <div className="player" aria-label="No check-ins yet">
      <div className="screen">
        <span className="blob" style={{ width: 220, height: 220, background: '#fbd3c2', right: -60, top: 60 }} />
        <div style={{ position: 'relative', marginTop: 'auto' }}>
          <div className="day-big">No check-ins yet</div>
          <div className="day-sub">A patient's last 21 days play here once their first check-in, sealed to your care team, arrives. Use Sync now to check.</div>
        </div>
      </div>
    </div>
  )
}
