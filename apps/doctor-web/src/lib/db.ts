// IndexedDB `sentinel_doctor_view`: one store per table in schema/doctor_view.sql (2.0), keyed by its primary key.
// Decrypted data and private keys live only here and are never sent anywhere.
import type { DrAlert, DrKey, DrOrgKey, DrPatient, DrTimelineEntry } from './types'

const DB_NAME = 'sentinel_doctor_view'
const DB_VERSION = 2 // 2 = contract 2.0 stores; older 1.x data is dropped on upgrade
const STORES: [string, string][] = [
  ['dr_patient', 'patient_ref'],
  ['dr_timeline_entry', 'entry_id'],
  ['dr_alert', 'alert_id'],
  ['dr_key', 'doctor_id'],
  ['dr_org_key', 'org_id'],
  ['dr_sync_state', 'sync_key'],
]

let dbPromise: Promise<IDBDatabase> | null = null

function open(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const d = req.result
      for (const name of [...d.objectStoreNames]) d.deleteObjectStore(name)
      for (const [name, keyPath] of STORES) {
        const s = d.createObjectStore(name, { keyPath })
        if (name === 'dr_timeline_entry') s.createIndex('patient_ref', 'patient_ref')
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return dbPromise
}

function wrap<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function store(name: string, mode: IDBTransactionMode = 'readonly') {
  return (await open()).transaction(name, mode).objectStore(name)
}

const get = async <T,>(name: string, key: string) => (await wrap((await store(name)).get(key))) as T | undefined
const all = async <T,>(name: string) => (await wrap((await store(name)).getAll())) as T[]
const put = async (name: string, value: unknown) => void (await wrap((await store(name, 'readwrite')).put(value)))
const del = async (name: string, key: string) => void (await wrap((await store(name, 'readwrite')).delete(key)))

export const db = {
  // This browser holds exactly one doctor identity (DW-19).
  me: async () => (await all<DrKey>('dr_key'))[0],
  putKey: (k: DrKey) => put('dr_key', k),

  orgKey: (orgId: string) => get<DrOrgKey>('dr_org_key', orgId),
  orgKeys: () => all<DrOrgKey>('dr_org_key'),
  putOrgKey: (k: DrOrgKey) => put('dr_org_key', k),

  async getSince(orgId: string, stream: 'envelopes' | 'alerts') {
    return (await get<{ since: string }>('dr_sync_state', `${orgId}:${stream}`))?.since
  },
  setSince: (orgId: string, stream: 'envelopes' | 'alerts', since: string) =>
    put('dr_sync_state', { sync_key: `${orgId}:${stream}`, since }),

  getPatient: (ref: string) => get<DrPatient>('dr_patient', ref),
  putPatient: (p: DrPatient) => put('dr_patient', p),
  allPatients: () => all<DrPatient>('dr_patient'),

  async putTimelineEntries(entries: DrTimelineEntry[]) {
    if (!entries.length) return
    const tx = (await open()).transaction('dr_timeline_entry', 'readwrite')
    for (const e of entries) tx.objectStore('dr_timeline_entry').put(e)
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  },
  async timelineFor(ref: string): Promise<DrTimelineEntry[]> {
    return wrap((await store('dr_timeline_entry')).index('patient_ref').getAll(ref) as IDBRequest<DrTimelineEntry[]>)
  },

  // Keeps seen_at if the alert is already stored.
  async putAlert(a: DrAlert) {
    const existing = await get<DrAlert>('dr_alert', a.alert_id)
    await put('dr_alert', { ...a, seen_at: existing?.seen_at ?? a.seen_at })
  },
  allAlerts: () => all<DrAlert>('dr_alert'),
  async markAlertSeen(id: string) {
    const a = await get<DrAlert>('dr_alert', id)
    if (a && !a.seen_at) await put('dr_alert', { ...a, seen_at: new Date().toISOString() })
  },

  // Membership revoked (DW-20): drop the org key and everything read through that org.
  async forgetOrg(orgId: string) {
    await del('dr_org_key', orgId)
    await del('dr_sync_state', `${orgId}:envelopes`)
    await del('dr_sync_state', `${orgId}:alerts`)
    for (const a of await all<DrAlert>('dr_alert')) if (a.org_id === orgId) await del('dr_alert', a.alert_id)
    for (const p of await all<DrPatient>('dr_patient')) {
      if (p.org_id !== orgId) continue
      for (const e of await db.timelineFor(p.patient_ref)) await del('dr_timeline_entry', e.entry_id)
      await del('dr_patient', p.patient_ref)
    }
  },

  // Demo reset: wipes everything, including the private keys.
  async wipe() {
    const d = await open()
    d.close()
    dbPromise = null
    await wrap(indexedDB.deleteDatabase(DB_NAME) as unknown as IDBRequest<undefined>)
  },
}
