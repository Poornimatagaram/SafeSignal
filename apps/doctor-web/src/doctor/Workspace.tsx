// DR-02 and DR-01: consented patients (most urgent first) and the open patient's page:
// header, new alerts, facts, latest symptom report and the 21-day history.
import { alertText } from '../lib/format'
import type { DrAlert } from '../lib/types'
import type { PatientRow } from '../lib/useDoctorData'
import { HistoryGrid } from './HistoryGrid'
import { ArrowRight } from './icons'
import { SEV_VAR, ago, byDay, latestTrend, longDate, reporterLabel } from './model'
import { patientHref, recordHref } from './routes'

export function Workspace({ rows, gone, alerts, openRef, orgName }: { rows: PatientRow[]; gone: PatientRow[]; alerts: DrAlert[]; openRef: string | null; orgName: (id: string) => string }) {
  const open = [...rows, ...gone].find((r) => r.patient_ref === openRef) ?? rows[0]
  return (
    <section className="wrap" id="patients" style={{ paddingTop: 112 }}>
      <div className="ws-head reveal">
        <div>
          <p className="kicker">Your patients</p>
          <h2>Consented patients only.</h2>
        </div>
        <p className="lede">Urgent first. You see a patient only while they share their history with your care team.</p>
      </div>
      {rows.length === 0 && gone.length === 0 ? (
        <div className="ppanel" style={{ marginTop: 36 }}>
          <h3 style={{ fontSize: '1.5rem' }}>No patient records yet</h3>
          <p className="lede" style={{ fontSize: '1rem', marginTop: 8 }}>
            Patients appear after their first check-in sealed to your care team arrives. If this browser doesn't hold your care team's key yet, set it up in Admin &amp;
            access. An emergency hospital reads a history only through emergency access, which is there too.
          </p>
          <div className="pp-actions"><a className="btn btn-coral" href="#/admin">Admin &amp; access <ArrowRight /></a></div>
        </div>
      ) : (
        <div className="ws">
          <div className="pcards">
            {rows.map((r) => <PatientCard key={r.patient_ref} r={r} current={r.patient_ref === open?.patient_ref} />)}
            <details className="nls">
              <summary>No longer shared ({gone.length})<span aria-hidden="true">▾</span></summary>
              {gone.length === 0 ? (
                <p>Patients who stop sharing move here. What arrived before stays, read-only; nothing new comes in.</p>
              ) : (
                <div className="pcards" style={{ marginTop: 10 }}>{gone.map((r) => <PatientCard key={r.patient_ref} r={r} current={r.patient_ref === open?.patient_ref} />)}</div>
              )}
            </details>
          </div>
          {open && <PatientPanel key={open.patient_ref} row={open} alerts={alerts.filter((a) => a.patient_ref === open.patient_ref)} orgName={orgName} />}
        </div>
      )}
    </section>
  )
}

function PatientCard({ r, current }: { r: PatientRow; current: boolean }) {
  const p = r.patient
  const trend = latestTrend(byDay(r.entries))
  return (
    <a className="pcard" href={patientHref(r.patient_ref)} aria-current={current ? 'true' : undefined}>
      <div className="top">
        <span className="nm">{p.display_name}</span>
        {r.unseenAlerts > 0 && <span className="tagx alert">{r.unseenAlerts} new alert{r.unseenAlerts > 1 ? 's' : ''}</span>}
      </div>
      <div className="sub">{p.age_years} · {p.drug_name} {p.drug_version} · <span className="mono">{r.patient_ref}</span></div>
      <div className="row">
        <span className="tagx">Last check-in {ago(p.last_checkin)}</span>
        <span className={`tagx ${trend}`}>Trend {trend}</span>
        {p.shared === 0 && <span className="tagx">No longer shared</span>}
      </div>
    </a>
  )
}

function PatientPanel({ row, alerts, orgName }: { row: PatientRow; alerts: DrAlert[]; orgName: (id: string) => string }) {
  const p = row.patient
  const days = byDay(row.entries)
  const last = [...days.values()].pop()
  const symptomFreeLatest = !!p.last_checkin && (!last || p.last_checkin > last.date)
  const fresh = alerts.filter((a) => !a.seen_at)
  return (
    <div className="ppanel" id="ppanel">
      <div className="pp-head">
        <div>
          <h3>{p.display_name}</h3>
          <p className="sub">{p.age_years} years · {p.drug_name} {p.drug_version} · <span className="mono">{p.patient_ref}</span></p>
        </div>
        <a className="btn btn-ghost" href={recordHref(row.patient_ref)}>See full record <ArrowRight /></a>
      </div>
      {p.shared === 0 && (
        <div className="banner" style={{ background: 'var(--sand)', marginTop: 16 }}>
          This patient stopped sharing with your care team. You are seeing what arrived before that; nothing new will come in.
        </div>
      )}
      {fresh.length > 0 && (
        <div className="banner" style={{ background: 'var(--coral-tint)', marginTop: 16 }}>
          <b style={{ color: 'var(--coral-ink)' }}>{fresh.length} new alert{fresh.length > 1 ? 's' : ''}:</b> {fresh.map((a) => alertText(a)).join(' · ')}
        </div>
      )}
      <dl className="kv">
        <div><dt>Last check-in</dt><dd>{ago(p.last_checkin)}</dd></div>
        <div><dt>Trend</dt><dd>{latestTrend(days)}</dd></div>
        <div><dt>Symptom reports, 21 days</dt><dd>{row.days.filter((d) => d.date >= new Date(Date.now() - 21 * 864e5).toISOString().slice(0, 10)).length}</dd></div>
        <div><dt>Care team</dt><dd>{orgName(p.org_id)}</dd></div>
      </dl>
      <div className="latest">
        {symptomFreeLatest || !last ? (
          <>
            <h4>Latest check-in{p.last_checkin ? ` · ${longDate(p.last_checkin)}` : ''}</h4>
            <p style={{ marginTop: 8 }}>{symptomFreeLatest ? 'No symptoms reported at the latest check-in.' : 'No check-in received yet.'}</p>
          </>
        ) : (
          <>
            <h4>Latest symptom report · {longDate(last.date)}</h4>
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
            <p className="small" style={{ marginTop: 10 }}>Answered by {reporterLabel(last.reporter)}. Coded on their phone; no recording or transcript is ever shared.</p>
          </>
        )}
      </div>
      <HistoryGrid entries={row.entries} />
    </div>
  )
}
