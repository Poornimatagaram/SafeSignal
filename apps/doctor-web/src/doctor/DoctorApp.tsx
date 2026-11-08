// The doctor's app (DW-29): one home page (hero, alerts, summary, patients, history, privacy, questions),
// the detailed view per patient, a guide, and Admin & access. Mounted only on doctor routes,
// so other pages never load keys or sync.
import { useEffect, useMemo, useState } from 'react'
import { IdentityPicker } from '../components/IdentityPicker'
import { useDoctorData } from '../lib/useDoctorData'
import { useViewMode } from '../lib/viewMode'
import { Clinic } from './Clinic'
import { AdminPage } from './AdminPage'
import { FullRecord, Guide } from './FullRecord'
import { Hero } from './home/Hero'
import { AlertsCard, SummaryStep, SymptomChart, TermCards } from './home/Live'
import { nameFor } from './model'
import { Compare, Connect, Faq, Footer, Privacy, Promise, Step, WhoIsToldTable } from './home/Static'
import { Check, Logo } from './icons'
import { Nav } from './Nav'
import { parseDoctorRoute, recordHref, type DoctorRoute } from './routes'
import { Workspace } from './Workspace'

const SECTION_IDS = ['how', 'alerts', 'summary', 'patients', 'history', 'privacy', 'questions']

export function DoctorApp() {
  const data = useDoctorData()
  const [route, setRoute] = useState<DoctorRoute>(() => parseDoctorRoute(location.hash))
  const [orgFilter, setOrgFilter] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [section, setSection] = useState<string | null>(null)
  const view = useViewMode()

  useEffect(() => {
    const on = () => setRoute(parseDoctorRoute(location.hash))
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 2600)
    return () => clearTimeout(t)
  }, [toast])

  const inOrg = <T extends { org_id: string }>(x: T) => !orgFilter || x.org_id === orgFilter
  const rows = useMemo(() => data.patients.filter((r) => inOrg(r.patient)), [data.patients, orgFilter]) // eslint-disable-line react-hooks/exhaustive-deps
  const gone = useMemo(() => data.noLongerShared.filter((r) => inOrg(r.patient)), [data.noLongerShared, orgFilter]) // eslint-disable-line react-hooks/exhaustive-deps
  const alerts = useMemo(() => data.alerts.filter(inOrg), [data.alerts, orgFilter]) // eslint-disable-line react-hooks/exhaustive-deps
  const all = [...data.patients, ...data.noLongerShared]
  const openRef = route.view === 'patient' ? route.ref : null
  const focus = [...rows, ...gone].find((r) => r.patient_ref === openRef) ?? rows[0]
  const home = route.view === 'list' || route.view === 'patient'

  // Patient route: show that patient's page; other views open at the top.
  useEffect(() => {
    if (route.view === 'patient' && view.mode === 'clinic') {
      if (innerWidth < 980) setTimeout(() => document.querySelector('.cl-pane')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60)
    } else if (route.view === 'patient') setTimeout(() => document.getElementById('patients')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60)
    else if (!home) scrollTo({ top: 0 })
  }, [route, home, view.mode])

  // Section highlight in the top bar, and the gentle reveal of cards as they scroll in.
  useEffect(() => {
    if (!home || !('IntersectionObserver' in window)) return
    const sec = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setSection(e.target.id)), { rootMargin: '-45% 0px -50% 0px' })
    SECTION_IDS.forEach((id) => { const el = document.getElementById(id); if (el) sec.observe(el) })
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const rev = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); rev.unobserve(e.target) } }), { rootMargin: '0px 0px -8% 0px' })
    if (!reduce) document.querySelectorAll('.reveal').forEach((el) => { if (el.getBoundingClientRect().top > innerHeight) rev.observe(el) })
    return () => { sec.disconnect(); rev.disconnect() }
  }, [home, data.me, rows.length, view.mode])

  if (data.me === undefined) return <div className="boot" aria-busy="true" />
  if (data.me === null)
    return (
      <div className="wrap identity">
        <div className="brand" style={{ justifyContent: 'center' }}><Logo /><span>Safe<b>Signal</b></span></div>
        <IdentityPicker onPick={data.chooseIdentity} />
      </div>
    )

  const unseen = alerts.filter((a) => !a.seen_at).length
  const detailHref = focus ? recordHref(focus.patient_ref) : '#/guide'
  const orgName = (id: string) => data.orgs.find((o) => o.org_id === id)?.display_name ?? 'your care team'
  const syncNote = data.syncing ? 'Syncing…' : data.lastSync ? `Synced ${new Date(data.lastSync).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}. Decrypted only in this browser; no audio or transcripts ever reach it.` : 'Not synced yet. Decrypted only in this browser.'
  const recordRow = route.view === 'record' ? all.find((r) => r.patient_ref === route.ref) : undefined

  return (
    <>
      <Nav
        doctorId={data.me.doctor_id}
        orgs={data.orgs}
        orgFilter={orgFilter}
        setOrgFilter={setOrgFilter}
        unseen={unseen}
        syncing={data.syncing}
        onSync={async () => { await data.refresh(); setToast('Synced') }}
        detailHref={detailHref}
        activeSection={home ? section : route.view === 'record' || route.view === 'guide' ? 'detail' : null}
        onToast={setToast}
        view={view.mode}
        onView={(v) => {
          view.choose(v)
          setToast(v === 'clinic' ? 'Clinic view: only what you need each day' : 'Guided view: the full tour')
          if (!home) location.hash = '#/'
          scrollTo({ top: 0 })
        }}
      />
      {(data.error || data.rejections.length > 0) && (
        <div className="wrap" style={{ marginTop: 16 }}>
          <p role="alert" className="banner" style={{ background: 'var(--coral-tint)' }}>
            {data.error ?? `${data.rejections.length} check-in(s) failed the safety checks and are not shown.`}
          </p>
        </div>
      )}
      {home && view.mode === 'clinic' && (
        <Clinic data={data} rows={rows} gone={gone} alerts={alerts} openRef={openRef} syncNote={syncNote} orgName={orgName} onToast={setToast} />
      )}
      {home && view.mode === 'guided' && (
        <main id="home">
          <Hero rows={rows} focus={focus} syncNote={syncNote} />
          <Connect to="how" />
          <Step
            id="how" no={1} noStyle={{ background: 'var(--coral-tint)', color: 'var(--coral-ink)' }}
            eyebrow="Their words. Your terms." title="Patients speak at home." accent="You read label terms."
            lede="The patient's device matches everyday words to the drug label's terms. Only the terms, severity and onset are sent to you."
            aside={<TermCards />}
          >
            <a className="btn btn-ghost" href="#/guide">See the field meanings</a>
          </Step>
          <Connect to="alerts" />
          <Step
            id="alerts" band="butter" no={2} noStyle={{ background: 'var(--mild)', color: '#2d2725' }}
            eyebrow="Urgent first. Always." title="Alerts sort themselves." accent="Escalated by the rules."
            lede="Severe symptoms and missed check-ins reach you within a minute. A patient who stays silent climbs from level 1 to level 3."
            aside={<AlertsCard data={data} alerts={alerts} nameOf={nameFor(all)} onToast={setToast} />}
          >
            {data.orgs.map((o) => (
              <span key={o.org_id} className="chip"><span style={{ width: 8, height: 8, borderRadius: '50%', background: o.hasLocalKey ? 'var(--good)' : 'var(--mild)' }} />{o.display_name} · {o.role.replace('_', ' ')}</span>
            ))}
          </Step>
          <Connect to="summary" />
          <SummaryStep focus={focus} alerts={alerts} />
          <Workspace rows={rows} gone={gone} alerts={alerts} openRef={openRef} orgName={orgName} />
          <Promise />
          <section className="wrap" id="history">
            <div className="ws-head reveal">
              <div><p className="kicker">History</p><h2>See the trend, not just the day.</h2></div>
              <p className="lede">Three weeks of check-ins at a glance, and exactly who hears about each alert.</p>
            </div>
            <div className="charts">
              <SymptomChart rows={rows.length ? rows : gone} />
              <WhoIsToldTable />
            </div>
          </section>
          <Privacy />
          <Compare rows={[...rows, ...gone]} />
          <Faq guideHref="#/guide" />
        </main>
      )}
      {route.view === 'record' && (
        <main>
          {recordRow ? (
            <FullRecord data={data} row={recordRow} />
          ) : (
            <section className="wrap d-hero">
              <h1>This patient isn't in this browser.</h1>
              <p className="lede">They may not share with your care team, or this browser hasn't synced their check-ins yet.</p>
              <div className="pp-actions"><a className="btn btn-coral" href="#/">Back to overview</a></div>
            </section>
          )}
        </main>
      )}
      {route.view === 'guide' && <main><Guide firstRef={focus?.patient_ref} /></main>}
      {route.view === 'admin' && <main><AdminPage data={data} /></main>}
      {route.view === 'patient' && !all.some((r) => r.patient_ref === route.ref) && (
        <div className="toast" role="status">This patient isn't in this browser. Showing your other patients.</div>
      )}
      <Footer detailHref={detailHref} />
      {toast && <div className="toast" role="status"><Check />{toast}</div>}
    </>
  )
}
