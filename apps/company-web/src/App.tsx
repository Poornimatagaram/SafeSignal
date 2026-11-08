// Company portal: reads the service's company endpoints only. Each program's data loads on selection.
import { useEffect, useMemo, useState } from 'react'
import { api, type CohortWeeklyRow, type CompletionRow, type Document, type ProgramsResponse, type TermsResponse } from './lib/api'
import { config } from './lib/config'
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

interface ProgramData {
  weekly: CohortWeeklyRow[]
  completion: CompletionRow[]
  terms: TermsResponse | null
  documents: Document[]
}

export default function App() {
  const [programs, setPrograms] = useState<ProgramsResponse | null>(null)
  const [programId, setProgramId] = useState(config.defaultProgramId)
  const [data, setData] = useState<ProgramData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('signals')
  const [reload, setReload] = useState(0)

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

  return (
    <div className="shell">
      <header className="topbar">
        <h1>{programs?.company?.display_name ?? 'Company portal'}</h1>
        <span className="sub">Side-effect monitoring</span>
        <span className="conn">{config.baseUrl}</span>
      </header>

      <div className="row" style={{ marginBottom: 12 }}>
        <label className="small muted" htmlFor="program">Program</label>
        <select id="program" value={programId} onChange={(e) => setProgramId(e.target.value)}>
          {(programs?.programs ?? [{ program_id: programId, drug_name: programId }]).map((p) => (
            <option key={p.program_id} value={p.program_id}>{p.drug_name}</option>
          ))}
        </select>
        {program?.source_trial && <span className="small muted">Grounded in {program.source_trial}</span>}
        <span style={{ flex: 1 }} />
        <button className="btn" onClick={() => setReload((n) => n + 1)}>Refresh</button>
      </div>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}<span className="role">{t.role}</span>
          </button>
        ))}
      </nav>

      {error && <div className="banner" role="alert">{error}</div>}
      {!error && (!data || !program) && <p className="muted">Loading…</p>}
      {data && program && (
        <main key={programId}>
          {tab === 'signals' && <Signals rows={data.weekly} versions={versions} terms={data.terms} />}
          {tab === 'completion' && <Completion rows={data.completion} versions={versions} />}
          {tab === 'survey' && <Survey versions={versions} />}
          {tab === 'program' && <Program program={program} documents={data.documents} />}
        </main>
      )}
      <footer className="small muted" style={{ marginTop: 32 }}>
        {programs?.company?.note ?? ''} Groups under 5 patients are never shown. The portal sees coded, pseudonymized records only.
      </footer>
    </div>
  )
}
