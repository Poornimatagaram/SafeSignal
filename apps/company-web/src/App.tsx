// Company portal: reads the service's company endpoints only. Each program's data loads on selection.
// Layout follows the doctor view (floating pill nav, hero with a live panel, pill tabs, rounded cards); the look is the company's own (D-091).
import { useEffect, useMemo, useState } from 'react'
import { api, type CohortWeeklyRow, type CompletionRow, type Document, type ProgramsResponse, type TermsResponse } from './lib/api'
import { config } from './lib/config'
import { pct, weeksOf } from './lib/data'
import { Nav } from './components/Nav'
import { Check, ClipboardCheck, Label, Pulse, Shield } from './components/icons'
import Signals from './views/Signals'
import Completion from './views/Completion'
import Survey from './views/Survey'
import Program from './views/Program'

const TABS = [
  { id: 'signals', label: 'Side effects', role: 'reader' },
  { id: 'completion', label: 'Check-ins', role: 'reader' },
  { id: 'survey', label: 'Survey', role: 'admin' },
  { id: 'program', label: 'Program & export', role: 'safety' },
] as const
type Tab = (typeof TABS)[number]['id']
const tabFromHash = (h: string): Tab => (TABS.find((t) => `#/${t.id}` === h)?.id ?? 'signals')

interface ProgramData {
  weekly: CohortWeeklyRow[]
  completion: CompletionRow[]
  terms: TermsResponse | null
  documents: Document[]
}

// The hero's "this week" numbers, from the same rows the tabs draw.
function summarize(d: ProgramData) {
  const week = weeksOf(d.weekly).at(-1) ?? null
  const perCohort = new Map<string, number>()
  for (const r of d.weekly) if (r.iso_week === week) perCohort.set(r.cohort_id, r.reporting_patients)
  const reporting = [...perCohort.values()].reduce((n, x) => n + x, 0)
  const cWeek = weeksOf(d.completion).at(-1) ?? null
  const now = d.completion.filter((r) => r.iso_week === cWeek)
  const completion = now.length ? now.reduce((n, r) => n + r.completion_rate, 0) / now.length : null
  const reported = new Set(d.weekly.map((r) => r.term_code))
  const offLabel = (d.terms?.terms ?? []).filter((t) => reported.has(t.term_code) && !t.known_for_program).length
  return { week, reporting, completion, offLabel }
}

export default function App() {
  const [programs, setPrograms] = useState<ProgramsResponse | null>(null)
  const [programId, setProgramId] = useState(config.defaultProgramId)
  const [data, setData] = useState<ProgramData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>(() => tabFromHash(location.hash))
  const [reload, setReload] = useState(0)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    const on = () => setTab(tabFromHash(location.hash))
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 2600)
    return () => clearTimeout(t)
  }, [toast])

  useEffect(() => {
    api.programs().then(setPrograms, (e: Error) => setError(e.message))
  }, [reload])

  useEffect(() => {
    let live = true
    setData(null)
    setError(null)
    Promise.all([api.cohortsWeekly(programId), api.completion(programId), api.terms(programId).catch(() => null),
      api.documents(programId)])
      .then(([weekly, completion, terms, documents]) => live && setData({ weekly, completion, terms, documents }))
      .catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [programId, reload])

  const program = programs?.programs.find((p) => p.program_id === programId) ?? null
  const versions = useMemo(() => program?.cohorts ?? [], [program])
  const sum = useMemo(() => (data ? summarize(data) : null), [data])
  const loading = !error && (!data || !program)
  const enrolled = versions.reduce((n, c) => n + c.enrolled, 0)

  return (
    <>
      <Nav
        company={programs?.company?.display_name ?? null}
        programs={programs?.programs ?? []}
        programId={programId}
        onProgram={setProgramId}
        loading={loading}
        onRefresh={() => { setReload((n) => n + 1); setToast('Refreshed from the service') }}
        onToast={setToast}
      />

      <section className="wrap hero">
        <div>
          <p className="kicker">{programs?.company?.display_name ?? 'Company portal'} · side-effect monitoring</p>
          <h1>
            <span>Every side effect.</span>
            <span>By drug version.</span>
            <span className="accent">Week over week.</span>
          </h1>
          <p className="lede">
            Patients check in by voice at home. Their device codes what they say into label terms, and you get counts by cohort.
            You never see names, words or audio.
          </p>
          {program && (
            <div className="chips">
              <span className="chip"><b>{program.drug_name}</b></span>
              <span className="chip">{versions.length} cohorts · {enrolled.toLocaleString()} enrolled</span>
              {program.source_trial && <span className="chip">Grounded in {program.source_trial}</span>}
            </div>
          )}
        </div>

        <aside className="panel week-panel" aria-label="This week">
          <div className="panel-head">
            <h3>{sum?.week ? `This week · ${sum.week}` : 'This week'}</h3>
            <span className="live"><i />Live</span>
          </div>
          {sum ? (
            <>
              <a className="stat" href="#/signals">
                <span className="ic" style={{ background: 'var(--accent-tint)', color: 'var(--accent-ink)' }}><Pulse /></span>
                <span><small>Patients reporting</small><b>{sum.reporting.toLocaleString()}</b></span>
              </a>
              <a className="stat" href="#/completion">
                <span className="ic" style={{ background: 'var(--good-tint)', color: 'var(--good)' }}><ClipboardCheck /></span>
                <span><small>Check-in completion</small><b>{pct(sum.completion)}</b></span>
              </a>
              <a className="stat" href="#/signals">
                <span className="ic" style={{ background: 'var(--review-tint)', color: 'var(--review)' }}><Label /></span>
                <span><small>Reported but not on the label</small><b>{sum.offLabel ? `${sum.offLabel} term${sum.offLabel > 1 ? 's' : ''}` : 'None'}</b></span>
              </a>
            </>
          ) : (
            <p className="empty-ok">{error ? 'No data while the service is unreachable.' : 'Loading…'}</p>
          )}
        </aside>
      </section>

      <div className="wrap tab-bar">
        <nav className="tabs" aria-label="Sections">
          {TABS.map((t) => (
            <a key={t.id} href={`#/${t.id}`} aria-current={tab === t.id ? 'page' : undefined}>
              {t.label}<span className="role">{t.role}</span>
            </a>
          ))}
        </nav>
      </div>

      <main className="wrap body">
        {error && <div className="banner" role="alert">{error}</div>}
        {loading && <p className="small">Loading…</p>}
        {data && program && (
          <div key={`${programId}-${tab}`} className="tab-body">
            {tab === 'signals' && <Signals rows={data.weekly} versions={versions} terms={data.terms} />}
            {tab === 'completion' && <Completion rows={data.completion} versions={versions} />}
            {tab === 'survey' && <Survey versions={versions} />}
            {tab === 'program' && <Program program={program} documents={data.documents} />}
          </div>
        )}

        <section className="guarantee">
          <span className="ck"><Shield /></span>
          <div>
            <h3>What this portal can never see.</h3>
            <div className="tiles">
              <span className="tile"><Check />No names, contact details or free text</span>
              <span className="tile"><Check />No transcripts or audio</span>
              <span className="tile"><Check />No group smaller than 5 patients</span>
              <span className="tile"><Check />Coded, pseudonymized records only</span>
            </div>
          </div>
        </section>
      </main>

      <footer className="wrap foot">
        <span className="brand-sm">Safe<b>Signal</b></span>
        <span>{programs?.company?.note ?? ''}</span>
        <span className="mono">{config.baseUrl}</span>
      </footer>
      {toast && <div className="toast" role="status"><Check />{toast}</div>}
    </>
  )
}
