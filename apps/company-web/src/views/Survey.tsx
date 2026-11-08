// CO-03: edit a cohort's survey and publish it (company_admin). Loads the current version from
// GET /v1/company/cohorts/{id}/survey; devices pick up the new version on their next check-in.
// The service validates against schema/survey_config.json and names failing fields on 422.
import { useEffect, useState } from 'react'
import { api, ApiError, type FieldError, type SurveyConfig, type SurveyResponse } from '../lib/api'
import { versionLabel, type Version } from '../lib/data'

const PURPOSES = ['wellbeing', 'symptom_screen', 'severity', 'onset', 'adherence', 'exposure']
const ASK_LABELS = ['First ask', 'Simpler re-ask', 'Choices or yes/no re-ask']

type Draft = SurveyConfig
const toDraft = (s: SurveyResponse): Draft => ({
  schedule: { every_days: s.schedule.every_days },
  questions: s.questions.map((q) => ({ question_id: q.question_id, purpose: q.purpose, asks: [...q.asks] })),
})

// Mirrors the schema limits so obvious mistakes show before the round trip; the service stays the authority.
function localErrors(d: Draft): string[] {
  const out: string[] = []
  if (!Number.isInteger(d.schedule.every_days) || d.schedule.every_days < 1 || d.schedule.every_days > 30)
    out.push('Check-in cadence must be a whole number of days from 1 to 30.')
  if (d.questions.length < 1 || d.questions.length > 10) out.push('A survey has 1 to 10 questions.')
  d.questions.forEach((q, i) =>
    q.asks.forEach((a, j) => {
      if (a.trim().length < 3 || a.length > 200) out.push(`Question ${i + 1}, ${ASK_LABELS[j].toLowerCase()}: 3 to 200 characters.`)
    }))
  return out
}

export default function Survey({ versions }: { versions: Version[] }) {
  const [cohort, setCohort] = useState(versions[0]?.cohort_id ?? '')
  const [current, setCurrent] = useState<SurveyResponse | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; text: string; errors?: FieldError[] } | null>(null)

  useEffect(() => {
    if (!versions.some((v) => v.cohort_id === cohort)) setCohort(versions[0]?.cohort_id ?? '')
  }, [versions, cohort])

  useEffect(() => {
    if (!cohort) return
    let live = true
    setCurrent(null)
    setDraft(null)
    setResult(null)
    api.survey(cohort).then(
      (s) => { if (live) { setCurrent(s); setDraft(toDraft(s)) } },
      (e: unknown) => { if (live) setResult({ ok: false, text: e instanceof Error ? e.message : String(e) }) })
    return () => { live = false }
  }, [cohort])

  const edit = (f: (d: Draft) => void) => setDraft((d) => { if (!d) return d; const n = structuredClone(d); f(n); return n })
  const problems = draft ? localErrors(draft) : []
  const dirty = !!(draft && current && JSON.stringify(draft) !== JSON.stringify(toDraft(current)))

  async function publish() {
    if (!draft) return
    setBusy(true)
    setResult(null)
    try {
      const r = await api.publishSurvey(cohort, draft)
      setResult({ ok: true, text: `Published version ${r.version} (${r.config_id}). Devices in this cohort use it from their next check-in.` })
      const s = await api.survey(cohort)
      setCurrent(s)
      setDraft(toDraft(s))
    } catch (e) {
      const err = e instanceof ApiError ? e : null
      setResult({ ok: false, text: err && err.status === 403 ? 'Publishing needs the company_admin role.' : (e as Error).message, errors: err?.errors })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <div className="row">
        <label className="small muted" htmlFor="cohort">Cohort</label>
        <select id="cohort" value={cohort} onChange={(e) => setCohort(e.target.value)}>
          {versions.map((v) => <option key={v.cohort_id} value={v.cohort_id}>{versionLabel(v)}</option>)}
        </select>
        {current && <span className="small muted">Live: version {current.version}, published {current.published_at.slice(0, 10)}</span>}
      </div>

      {result && (
        <div className={`banner ${result.ok ? 'ok' : ''}`} role="status">
          {result.text}
          {!!result.errors?.length && <ul>{result.errors.map((e) => <li key={e.field + e.message}><code>{e.field}</code>: {e.message}</li>)}</ul>}
        </div>
      )}

      {draft && (
        <div className="card stack">
          <div className="row">
            <label htmlFor="every">Check in every</label>
            <input id="every" type="number" min={1} max={30} style={{ width: 72 }} value={draft.schedule.every_days}
              onChange={(e) => edit((d) => { d.schedule.every_days = Number(e.target.value) })} />
            <span>day(s)</span>
          </div>
          {draft.questions.map((q, i) => (
            <div className="q" key={q.question_id}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <strong>Question {i + 1} <span className="muted small">({q.question_id})</span></strong>
                <div className="row">
                  <select aria-label={`Purpose of question ${i + 1}`} value={q.purpose}
                    onChange={(e) => edit((d) => { d.questions[i].purpose = e.target.value })}>
                    {PURPOSES.map((p) => <option key={p} value={p}>{p.replace('_', ' ')}</option>)}
                  </select>
                  <button className="btn" disabled={draft.questions.length <= 1}
                    onClick={() => edit((d) => { d.questions.splice(i, 1) })}>Remove</button>
                </div>
              </div>
              {q.asks.map((a, j) => (
                <div key={j}>
                  <label htmlFor={`${q.question_id}-${j}`}>{ASK_LABELS[j]}</label>
                  <textarea id={`${q.question_id}-${j}`} rows={1} maxLength={200} value={a}
                    onChange={(e) => edit((d) => { d.questions[i].asks[j] = e.target.value })} />
                </div>
              ))}
            </div>
          ))}
          <div className="row">
            <button className="btn" disabled={draft.questions.length >= 10} onClick={() => edit((d) => {
              const used = new Set(d.questions.map((x) => x.question_id))
              let n = 1
              while (used.has(`q${n}`)) n++
              d.questions.push({ question_id: `q${n}`, purpose: 'wellbeing', asks: ['', '', ''] })
            })}>Add question</button>
            <span style={{ flex: 1 }} />
            {current && <button className="btn" disabled={!dirty || busy} onClick={() => setDraft(toDraft(current))}>Discard changes</button>}
            <button className="btn primary" disabled={!dirty || busy || problems.length > 0} onClick={publish}>
              {busy ? 'Publishing…' : 'Publish new version'}
            </button>
          </div>
          {problems.length > 0 && <div className="banner"><ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul></div>}
          <p className="small muted" style={{ margin: 0 }}>Questions only: surveys never carry patient data. Publishing uses the company_admin role.</p>
        </div>
      )}
    </div>
  )
}
