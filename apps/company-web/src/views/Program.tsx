// Program context and data access: cohorts and the trial each is grounded in, the program's documents (2.2),
// and CO-07 export (company_safety). The export is pseudonymized: coded symptoms, no names or free text (CO-04).
import { useState } from 'react'
import { api, ApiError, type Document, type ProgramInfo } from '../lib/api'
import { seriesColor } from '../lib/data'

const KIND: Record<string, string> = { protocol: 'Protocol', sap: 'Statistical analysis plan', label: 'FDA label' }

export default function Program({ program, documents }: { program: ProgramInfo; documents: Document[] }) {
  const [busy, setBusy] = useState<'json' | 'csv' | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  async function download(format: 'json' | 'csv') {
    setBusy(format)
    setMsg(null)
    try {
      const blob = await api.exportRecords(program.program_id, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${program.program_id}_records.${format}`
      a.click()
      URL.revokeObjectURL(url)
      setMsg(`Downloaded ${a.download} (${(blob.size / 1024).toFixed(0)} KB).`)
    } catch (e) {
      setMsg(e instanceof ApiError && e.status === 403 ? 'Export needs the company_safety role.' : (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="stack">
      <div className="card">
        <h2>{program.label ?? program.drug_name}</h2>
        <p className="note">
          Population: {program.population ?? '—'}. Cohort rates are grounded in{' '}
          {program.source_url ? <a href={program.source_url} target="_blank" rel="noreferrer">{program.source_trial}</a> : program.source_trial ?? 'synthetic data'}.
        </p>
        <div className="scroll-x">
          <table>
            <thead><tr><th>Cohort</th><th>Version</th><th>Trial arm</th><th>Enrolled</th></tr></thead>
            <tbody>
              {program.cohorts.map((c, i) => (
                <tr key={c.cohort_id}>
                  <td><span className="key" style={{ background: seriesColor(i) }} />{c.label}</td>
                  <td>{c.drug_version}</td>
                  <td style={{ whiteSpace: 'normal', textAlign: 'right' }}>{c.source_arm ?? '—'}</td>
                  <td>{c.enrolled}{c.target_size ? ` / ${c.target_size}` : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2>Documents</h2>
        <p className="note">Public sources for this program. Each opens the original.</p>
        {documents.length ? (
          <div className="docs">
            {documents.map((d) => (
              <div className="doc" key={d.doc_id}>
                <a href={d.source_url} target="_blank" rel="noreferrer">{d.title}</a>
                <span className="tag">{KIND[d.kind ?? ''] ?? d.kind ?? 'Document'}</span>
                <span className="small muted">version {d.version}</span>
              </div>
            ))}
          </div>
        ) : <p className="muted">No documents for this program.</p>}
      </div>

      <div className="card">
        <h2>Export records</h2>
        <p className="note">Pseudonymized check-in records: patient reference, cohort, week, coded symptoms, reporter and input mode. No names, transcripts or audio. CSV has one row per symptom.</p>
        <div className="row">
          <button className="btn primary" disabled={!!busy} onClick={() => download('csv')}>{busy === 'csv' ? 'Preparing…' : 'Download CSV'}</button>
          <button className="btn" disabled={!!busy} onClick={() => download('json')}>{busy === 'json' ? 'Preparing…' : 'Download JSON'}</button>
          <span className="small muted">Uses the company_safety role; every export is written to the access log.</span>
        </div>
        {msg && <p className="small" role="status">{msg}</p>}
      </div>
    </div>
  )
}
