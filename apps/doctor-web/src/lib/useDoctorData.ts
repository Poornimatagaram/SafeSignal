// React state for the doctor screen: identity, org memberships and keys, per-org sync, rows for the UI.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { doctorApi } from './api'
import { config } from './config'
import { db } from './db'
import { createIdentity, refreshOrgs, registerPersonalKey, type OrgStatus } from './keys'
import { checkinDays, syncOrg, type CheckinDay, type Rejection } from './sync'
import type { DrAlert, DrKey, DrPatient, DrTimelineEntry } from './types'

export interface PatientRow {
  patient_ref: string
  patient: DrPatient
  entries: DrTimelineEntry[]
  days: CheckinDay[]
  unseenAlerts: number
}

export interface DoctorData {
  me: DrKey | null | undefined // undefined while loading, null before the identity is picked
  orgs: OrgStatus[]
  patients: PatientRow[] // shared = 1 (DR-02)
  noLongerShared: PatientRow[] // shared = 0: kept, read-only (D-038)
  alerts: DrAlert[]
  rejections: Rejection[]
  lastSync: string | null
  error: string | null
  syncing: boolean
  chooseIdentity: (doctorId: string) => Promise<void>
  refresh: () => Promise<void>
  markSeen: (alertId: string) => Promise<void>
}

const latestTrend = (r: PatientRow) => [...r.days].reverse().find((d) => d.status !== 'missed')?.trend
const urgent = (a: DrAlert) => a.alert_type === 'severe' || a.alert_type === 'emergency_access' || (a.escalation_level ?? 0) >= 3

export function useDoctorData(): DoctorData {
  const [me, setMe] = useState<DrKey | null | undefined>(undefined)
  const [orgs, setOrgs] = useState<OrgStatus[]>([])
  const [rows, setRows] = useState<PatientRow[]>([])
  const [alerts, setAlerts] = useState<DrAlert[]>([])
  const [rejections, setRejections] = useState<Rejection[]>([])
  const [lastSync, setLastSync] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const busy = useRef(false)
  const registered = useRef(false)

  const load = useCallback(async () => {
    const all = (await db.allAlerts()).sort((a, b) => b.created_at.localeCompare(a.created_at))
    const out: PatientRow[] = []
    for (const p of await db.allPatients()) {
      const entries = await db.timelineFor(p.patient_ref)
      out.push({ patient_ref: p.patient_ref, patient: p, entries, days: checkinDays(entries), unseenAlerts: all.filter((a) => a.patient_ref === p.patient_ref && !a.seen_at).length })
    }
    // Most urgent first (DW-09): unseen severe / level-3 / emergency alert, worsening trend, unseen alerts, name.
    const hot = (r: PatientRow) => (all.some((a) => a.patient_ref === r.patient_ref && !a.seen_at && urgent(a)) ? 1 : 0)
    const worse = (r: PatientRow) => (latestTrend(r) === 'worse' ? 1 : 0)
    out.sort((a, b) => hot(b) - hot(a) || worse(b) - worse(a) || b.unseenAlerts - a.unseenAlerts || a.patient.display_name.localeCompare(b.patient.display_name))
    setRows(out)
    setAlerts(all)
  }, [])

  const refresh = useCallback(async () => {
    const id = await db.me()
    setMe(id ?? null)
    if (!id || busy.current) return
    busy.current = true
    setSyncing(true)
    try {
      const api = doctorApi(id.doctor_id)
      if (!registered.current) {
        await registerPersonalKey(api, id)
        registered.current = true
      }
      const status = await refreshOrgs(api, id)
      setOrgs(status)
      const rejected: Rejection[] = []
      for (const k of await db.orgKeys()) rejected.push(...(await syncOrg(api, k)).rejected)
      if (rejected.length) setRejections((prev) => [...prev, ...rejected].slice(-50))
      setLastSync(new Date().toISOString())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      await load()
      busy.current = false
      setSyncing(false)
    }
  }, [load])

  useEffect(() => {
    load().then(refresh)
    const t = setInterval(refresh, config.pollMs)
    return () => clearInterval(t)
  }, [load, refresh])

  const chooseIdentity = useCallback(async (doctorId: string) => {
    await createIdentity(doctorId)
    registered.current = false
    await refresh()
  }, [refresh])

  const patients = useMemo(() => rows.filter((r) => r.patient.shared === 1), [rows])
  const noLongerShared = useMemo(() => rows.filter((r) => r.patient.shared === 0), [rows])

  return {
    me, orgs, patients, noLongerShared, alerts, rejections, lastSync, error, syncing, chooseIdentity, refresh,
    markSeen: async (id) => {
      await db.markAlertSeen(id)
      await load()
    },
  }
}
