// Company portal: reads the service's company endpoints only. Each program's data loads on selection.
// Layout (D-092): thin top bar, centered statement and this week's figures, a sticky centered section switcher,
// and each section as a centered heading over rounded tiles.
import { useEffect, useMemo, useState } from 'react'
import { api, type CohortWeeklyRow, type CompletionRow, type Document, type ProgramsResponse, type TermsResponse } from './lib/api'
import { config } from './lib/config'
import { pct, weeksOf } from './lib/data'
import { Nav } from './components/Nav'
import { Check, ChevronRight, Group, Lock, NoMic, NoText } from './components/icons'
import Signals from './views/Signals'
import Completion from './views/Completion'
import Survey from './views/Survey'
import Program from './views/Program'

const TABS = [
  { id: 'signals', label: 'Side effects', title: 'Side effects by cohort.',
    blurb: 'The share of reporting patients with each side effect, against the week before.', role: 'Any company role' },
  { id: 'completion', label: 'Check-ins', title: 'Check-ins.',
    blurb: 'How many due check-ins patients completed, and how they answered.', role: 'Any company role' },
  { id: 'survey', label: 'Survey', title: 'Survey.',
    blurb: 'Questions and cadence for each cohort. Devices use a new version from their next check-in.', role: 'Publishing needs company_admin' },
  { id: 'program', label: 'Program & export', title: 'Program and export.',
    blurb: 'Cohorts and the trials behind them, public documents and pseudonymized exports.', role: 'Export needs company_safety' },
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
    // A section link always lands on the section, even when it is already the current one.
    const show = () => document.getElementById('content')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    const on = () => { setTab(tabFromHash(location.hash)); requestAnimationFrame(show) }
    const onClick = (e: MouseEvent) => {
      const a = (e.target as Element).closest?.('a[href^="#/"]')
      if (a && a.getAttribute('href') === location.hash) show()
    }
    addEventListener('hashchange', on)
    document.addEventListener('click', onClick)
    return () => { removeEventListener('hashchange', on); document.removeEventListener('click', onClick) }
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

      <header className="hero">
        <div className="wrap hero-inner">
          <h1 className="hero-title">{program?.drug_name ?? 'Company portal'}</h1>
          <p className="hero-tagline">Every side effect. By drug version. Week over week.</p>
          <p className="hero-lede">
            Patients check in by voice at home. Their device codes what they say into label terms, and you get counts by cohort.
            You never see names, words or audio.
          </p>
          <div className="hero-actions">
            <a className="btn primary lg" href="#/signals">View side effects</a>
            <a className="more" href="#/program">Program and export<ChevronRight /></a>
          </div>
          {program && (
            <p className="hero-meta">
              {versions.length} cohorts · {enrolled.toLocaleString()} enrolled
              {program.source_trial && <> · Grounded in {program.source_trial}</>}
            </p>
          )}
        </div>

        <section className="wrap week" aria-label="This week">
          <p className="week-head"><span className="live"><i />Live</span>{sum?.week ? `This week · ${sum.week}` : 'This week'}</p>
          {sum ? (
            <div className="figures">
              <a className="figure" href="#/signals">
                <span className="figure-value">{sum.reporting.toLocaleString()}</span>
                <span className="figure-label">patients reporting</span>
              </a>
              <a className="figure" href="#/completion">
                <span className="figure-value">{pct(sum.completion)}</span>
                <span className="figure-label">check-in completion</span>
              </a>
              <a className="figure" href="#/signals">
                <span className="figure-value">{sum.offLabel || 'None'}</span>
                <span className="figure-label">{sum.offLabel ? `${sum.offLabel === 1 ? 'side effect' : 'side effects'} reported but not on the label` : 'side effects outside the label'}</span>
              </a>
            </div>
          ) : (
            <p className="figures-empty">{error ? 'No data while the service is unreachable.' : 'Loading this week…'}</p>
          )}
        </section>
      </header>

      <div className="switcher">
        <nav className="seg seg-lg" aria-label="Sections">
          {TABS.map((t) => (
            <a key={t.id} href={`#/${t.id}`} aria-current={tab === t.id ? 'page' : undefined}>{t.label}</a>
          ))}
        </nav>
      </div>

      <main className="wrap body" id="content">
        {(() => {
          const t = TABS.find((x) => x.id === tab)!
          return (
            <div className="section-head">
              <h2>{t.title}</h2>
              <p>{t.blurb}</p>
              <p className="role">{t.role}</p>
            </div>
          )
        })()}
        {error && <div className="banner" role="alert">{error}</div>}
        {loading && !error && <div className="skeleton" aria-label="Loading" />}
        {data && program && (
          <div key={`${programId}-${tab}`} className="tab-body">
            {tab === 'signals' && <Signals rows={data.weekly} versions={versions} terms={data.terms} />}
            {tab === 'completion' && <Completion rows={data.completion} versions={versions} />}
            {tab === 'survey' && <Survey versions={versions} />}
            {tab === 'program' && <Program program={program} documents={data.documents} />}
          </div>
        )}
      </main>

      <section className="guarantee" aria-labelledby="never">
        <div className="wrap">
          <h2 id="never">What this portal can never see.</h2>
          <p className="guarantee-lede">Records are coded on the patient's device before anything is sent. The company receives counts, not people.</p>
          <ul className="tiles">
            <li className="tile"><NoText /><span>No names, contact details or free text</span></li>
            <li className="tile"><NoMic /><span>No transcripts or audio</span></li>
            <li className="tile"><Group /><span>No group smaller than 5 patients</span></li>
            <li className="tile"><Lock /><span>Coded, pseudonymized records only</span></li>
          </ul>
        </div>
      </section>

      <footer className="wrap foot">
        <span className="brand-sm">SafeSignal</span>
        <span>{programs?.company?.note ?? ''}</span>
        <span className="mono">{config.baseUrl}</span>
      </footer>
      {toast && <div className="toast" role="status"><Check />{toast}</div>}
    </>
  )
}
