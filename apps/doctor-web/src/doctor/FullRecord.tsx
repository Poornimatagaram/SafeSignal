// Screen 3, the detailed view: everything received for one patient, in tabs. Also the guide (#/guide):
// what every field means and a map of every screen.
import { useState } from 'react'
import { alertText, fmtTime } from '../lib/format'
import { REPORTER_LABELS } from '../lib/terms'
import type { DoctorData, PatientRow } from '../lib/useDoctorData'
import { ArrowLeft, Clock, Warn } from './icons'
import { LevelBars } from './home/Live'
import { SEV_VAR, ago, byDay, longDate, whoIsTold } from './model'
import { patientHref, recordHref } from './routes'

type Tab = 'log' | 'alerts' | 'access' | 'fields' | 'map'
const TABS: [Tab, string][] = [['log', 'Check-in log'], ['alerts', 'Alert history'], ['access', 'Sharing and access'], ['fields', 'Field meanings'], ['map', 'Screen map']]

export function FullRecord({ data, row }: { data: DoctorData; row: PatientRow }) {
  const [tab, setTab] = useState<Tab>('log')
  const p = row.patient
  const all = [...data.patients, ...data.noLongerShared]
  return (
    <>
      <section className="wrap d-hero">
        <a className="back" href={patientHref(row.patient_ref)}><ArrowLeft />Back to {p.display_name}</a>
        <p className="kicker">Detailed view</p>
        <h1>{tab === 'fields' ? 'What every field means' : tab === 'map' ? 'Every screen, in order' : `${p.display_name}'s full record`}</h1>
        <p className="lede">{p.age_years} years · {p.drug_name} {p.drug_version} · <span className="mono">{p.patient_ref}</span> · {data.orgs.find((o) => o.org_id === p.org_id)?.display_name ?? 'your care team'}</p>
      </section>
      <div className="wrap">
        <div className="d-bar">
          <nav className="tabs" aria-label="Record sections">
            {TABS.map(([k, label]) => (
              <a key={k} href={recordHref(row.patient_ref)} aria-current={tab === k ? 'page' : 'false'} onClick={(e) => { e.preventDefault(); setTab(k) }}>{label}</a>
            ))}
          </nav>
          {all.length > 1 && (
            <div className="seg" role="group" aria-label="Patient">
              {all.map((r) => (
                <a key={r.patient_ref} href={recordHref(r.patient_ref)} className="seg-a" aria-pressed={r.patient_ref === row.patient_ref}>{r.patient.display_name}</a>
              ))}
            </div>
          )}
        </div>
        <div className="d-body" key={tab + row.patient_ref}>
          {tab === 'log' && <Log row={row} />}
          {tab === 'alerts' && <AlertHistory data={data} row={row} />}
          {tab === 'access' && <Access data={data} row={row} />}
          {tab === 'fields' && <Fields />}
          {tab === 'map' && <ScreenMap />}
        </div>
      </div>
    </>
  )
}

function Log({ row }: { row: PatientRow }) {
  const days = [...byDay(row.entries).values()].reverse()
  return (
    <>
      <div className="tbl">
        <table>
          <thead><tr><th>Date</th><th>Status</th><th>Answered by</th><th>Trend</th><th>Symptoms</th></tr></thead>
          <tbody>
            {days.map((d) => (
              <tr key={d.date}>
                <td><b>{longDate(d.date)}</b><div className="small">{ago(d.date)}</div></td>
                <td>{d.status === 'partial' ? 'Partly answered' : 'Completed'}</td>
                <td>{REPORTER_LABELS[d.reporter]}</td>
                <td><span className={`tagx ${d.trend}`}>{d.trend}</span></td>
                <td>
                  <div className="symlist">
                    {d.symptoms.map((s) => (
                      <div key={s.term} className="sym-line">
                        <span className="sev" style={{ background: SEV_VAR[s.severity] }} />
                        <b>{s.term}</b>
                        <span className="small">{s.severity} · {s.onset}</span>
                        {s.forReview && <span className="tagx review">For review</span>}
                        {s.offLabel && <span className="tagx">Not on the drug label</span>}
                      </div>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
            {days.length === 0 && <tr><td colSpan={5}><span className="small">No check-ins with symptoms yet.</span></td></tr>}
          </tbody>
        </table>
      </div>
      <p className="small" style={{ marginTop: 12 }}>Check-ins with no symptoms count towards "last check-in" but aren't listed here yet.</p>
    </>
  )
}

function AlertHistory({ data, row }: { data: DoctorData; row: PatientRow }) {
  const alerts = data.alerts.filter((a) => a.patient_ref === row.patient_ref)
  return (
    <div className="cards2">
      <div className="panel" style={{ padding: 22 }}>
        <div className="panel-head"><h3>Alert history</h3><span className="small">{alerts.length} alert{alerts.length === 1 ? '' : 's'}</span></div>
        {alerts.length === 0 && <p className="empty-ok">No alerts for this patient.</p>}
        {alerts.map((a) => (
          <div key={a.alert_id} className="alert-row">
            <span className="a-ico" style={{ background: a.alert_type === 'severe' ? 'var(--severe)' : 'var(--coral-tint)', color: a.alert_type === 'severe' ? '#fff' : 'var(--coral-ink)' }}>{a.alert_type === 'severe' ? <Warn /> : <Clock />}</span>
            <div className="a-body">
              <div className="a-title">{alertText(a)}{a.alert_type === 'missed' && <LevelBars n={a.escalation_level ?? 1} />}</div>
              <div className="a-meta">{fmtTime(a.created_at)} · {a.seen_at ? 'seen' : <b style={{ color: 'var(--coral-ink)' }}>new</b>}</div>
              <div className="a-told">Who is told: {whoIsTold(a)}</div>
            </div>
            {!a.seen_at && <button type="button" className="seen-btn" onClick={() => data.markSeen(a.alert_id)}>Mark seen</button>}
          </div>
        ))}
      </div>
      <div className="card">
        <h3>Escalation levels</h3>
        <p style={{ marginTop: 6 }}>A missed check-in is a due check-in whose window closed with nothing received. Levels count missed check-ins in a row.</p>
        <div className="lv">
          <div><b>Level 1</b><p className="small">One missed. Patient reminder, caregiver, care team.</p></div>
          <div><b>Level 2</b><p className="small">Two in a row. The same people, marked urgent.</p></div>
          <div style={{ background: 'var(--coral-tint)' }}><b>Level 3</b><p className="small">Three or more. Also the emergency contacts the patient consented to.</p></div>
        </div>
        <p className="small" style={{ marginTop: 12 }}>Severe symptoms and emergency access tell the caregiver and the care team.</p>
      </div>
    </div>
  )
}

function Access({ data, row }: { data: DoctorData; row: PatientRow }) {
  const p = row.patient
  const org = data.orgs.find((o) => o.org_id === p.org_id)
  return (
    <div className="cards2">
      <div className="card">
        <h3>Care team · {org?.display_name ?? 'your organization'}</h3>
        <ul>
          <li>{p.shared ? 'Sharing is active.' : 'The patient has stopped sharing; what arrived before stays here, read-only.'}</li>
          <li>Your role: {org?.role.replace('_', ' ') ?? 'unknown'}. {org?.hasLocalKey ? 'This browser holds the care-team key.' : 'This browser does not hold the care-team key.'}</li>
          <li>A revoked doctor loses their key grant and sees nothing after the next sync. The record stays with the care team.</li>
        </ul>
      </div>
      <div className="card">
        <h3>Emergency hospital</h3>
        <p style={{ marginTop: 8 }}>A hospital the patient chose for emergencies can open this history only through emergency access, with a stated reason: emergency admission, patient unresponsive, or a level-3 missed check-in escalation. Each use is logged and your care team is told.</p>
      </div>
      <div className="card">
        <h3>Caregiver</h3>
        <p style={{ marginTop: 8 }}>If the patient has a caregiver, they are told that something happened and when. Never the symptoms or the history.</p>
      </div>
      <div className="card">
        <h3>This browser</h3>
        <ul>
          <li>Your personal key and the care-team key live here only.</li>
          <li>Reset this browser (Admin &amp; access) removes every key and record from it.</li>
          <li>Recordings and transcripts never leave the patient's phone.</li>
        </ul>
      </div>
    </div>
  )
}

const FIELDS: [string, string, string[]][] = [
  ['Status', 'Whether the check-in was finished.', ['completed', 'partly answered']],
  ['Trend', "The patient's own sense of how things are going since the last check-in.", ['worse', 'same', 'better', 'unknown']],
  ['Answered by', 'Who answered. Shown as C in the history when it was a caregiver.', ['Patient', 'Caregiver', 'Parent', 'Someone else']],
  ['Severity', 'How bad the symptom is, as reported. Colour and lightness both change, so it reads without colour too.', ['mild', 'moderate', 'severe']],
  ['Started', 'When the symptom began, as reported.', ['today', '1–3 days', '4–7 days', 'over 7 days', 'unknown']],
  ['Term', "The drug label term the patient's everyday words were matched to on their phone.", ['Rash', 'Diarrhea', 'Fatigue', '…']],
  ['For review', 'A possible link between symptom and drug, flagged for you. A flag, never a cause.', ['yes', 'no']],
  ['Not on the drug label', "Not one of the drug label's known side effects, so it needs your review.", ['known', 'not on the label']],
  ['Escalation level', 'Missed due check-ins in a row, capped at 3.', ['1', '2', '3']],
  ['Age', "The patient's age on the check-in date, sent with each check-in.", ['years']],
]
export function Fields() {
  return (
    <div className="gloss">
      {FIELDS.map(([t, d, v]) => (
        <div key={t} className="card">
          <dl><dt>{t}</dt><dd>{d}</dd></dl>
          <div className="vals">{v.map((x) => <span key={x} className="tagx">{x}</span>)}</div>
        </div>
      ))}
    </div>
  )
}

const MAP: [string, [string, string][]][] = [
  ['Home', [
    ['Top bar', 'Sections, hospital filter with key status, appearance (light, dark, system), Sync now'],
    ['Patient finder', 'Find a consented patient by name or reference'],
    ['Day-by-day player', "The open patient's 21 days, played or tapped one at a time"],
    ['Term cards', 'Everyday words and the drug label term they match'],
    ['Alerts', 'New alerts, urgent first, with who is told and Mark seen'],
    ['Pre-visit summary', 'Template summary of the last 21 days'],
    ['Patient list', 'Consented patients, urgent first, and no longer shared'],
    ['Patient page', 'Header, new alerts, facts, latest symptom report, 21-day history grid'],
    ['Symptoms per check-in chart', 'Bars by day, coloured by the most severe symptom'],
    ['Who is told table', 'Recipients for each alert type (D-068)'],
    ['Privacy and emergency promise', 'What never reaches this screen'],
    ['Questions', 'Short answers before you open a record'],
  ]],
  ['Detailed view', [
    ['Check-in log', 'Every check-in with symptoms, newest first'],
    ['Alert history', 'All alerts for the patient, including seen ones, and the level explainer'],
    ['Sharing and access', 'Care team, emergency hospital, caregiver, this browser'],
    ['Field meanings', 'What every value in the record means'],
  ]],
  ['Admin & access', [
    ['Care-team keys', 'Create the key (admin), grant it to members, revoke members'],
    ['Emergency access', 'For an emergency hospital: reason, logged view, nothing kept'],
    ['Reset this browser', 'Remove the identity, all keys and all records'],
  ]],
]
export function ScreenMap() {
  return (
    <div className="map">
      {MAP.map(([h, items]) => (
        <section key={h}>
          <h3>{h}</h3>
          <ol className="map" style={{ margin: 0, padding: 0 }}>
            {items.map(([n, d]) => <li key={n}><div><b>{n}</b><span>{d}</span></div></li>)}
          </ol>
        </section>
      ))}
    </div>
  )
}

export function Guide({ firstRef }: { firstRef?: string }) {
  const [tab, setTab] = useState<'fields' | 'map'>('fields')
  return (
    <>
      <section className="wrap d-hero">
        <a className="back" href="#/"><ArrowLeft />Back to overview</a>
        <p className="kicker">Detailed view</p>
        <h1>{tab === 'fields' ? 'What every field means' : 'Every screen, in order'}</h1>
        <p className="lede">For every patient. {firstRef ? 'Open a patient to see their full record.' : 'Patients appear after their first check-in arrives.'}</p>
      </section>
      <div className="wrap">
        <div className="d-bar">
          <nav className="tabs" aria-label="Guide sections">
            <a href="#/guide" aria-current={tab === 'fields' ? 'page' : 'false'} onClick={(e) => { e.preventDefault(); setTab('fields') }}>Field meanings</a>
            <a href="#/guide" aria-current={tab === 'map' ? 'page' : 'false'} onClick={(e) => { e.preventDefault(); setTab('map') }}>Screen map</a>
            {firstRef && <a href={recordHref(firstRef)}>Full record</a>}
          </nav>
        </div>
        <div className="d-body" key={tab}>{tab === 'fields' ? <Fields /> : <ScreenMap />}</div>
      </div>
    </>
  )
}
