// Memberships and keys (contract 2.0, ARCHITECTURE.md §2). Admins create the care-team key and grant or revoke members.
import { useState } from 'react'
import { doctorApi } from '../lib/api'
import { DEMO_DOCTORS, doctorName } from '../lib/config'
import { addAndGrant, createOrgKey, revokeMember, type OrgStatus } from '../lib/keys'
import type { DrKey } from '../lib/types'

export function OrgPanel({ me, orgs, onChange }: { me: DrKey; orgs: OrgStatus[]; onChange: () => Promise<void> }) {
  const [copied, setCopied] = useState(false)
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Organizations</h2>
        <button
          onClick={async () => {
            await navigator.clipboard.writeText(me.public_key)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          }}
          className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50"
          title="Give this to your organization's admin so they can grant you access"
        >
          {copied ? 'Copied' : 'Copy my public key'}
        </button>
      </div>
      {orgs.length === 0 && (
        <p className="mt-2 text-sm text-slate-500">
          You are not an active member of any organization. Ask an admin to add you, and give them your public key.
        </p>
      )}
      <ul className="mt-3 space-y-3">
        {orgs.map((o) => (
          <li key={o.org_id} className="rounded border border-slate-100 p-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{o.display_name}</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{o.role}</span>
              <KeyBadge o={o} />
            </div>
            {o.role === 'admin' && <AdminTools me={me} org={o} onChange={onChange} />}
          </li>
        ))}
      </ul>
    </section>
  )
}

function KeyBadge({ o }: { o: OrgStatus }) {
  if (o.hasLocalKey) return <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700">Key in this browser</span>
  if (!o.org_key_registered) return <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-800">No care-team key yet</span>
  if (o.grantMismatch)
    return (
      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-800">
        Access was granted to you in another browser. Copy your public key and ask the admin to grant this browser.
      </span>
    )
  return <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-800">Waiting for a key grant</span>
}

function AdminTools({ me, org, onChange }: { me: DrKey; org: OrgStatus; onChange: () => Promise<void> }) {
  const api = doctorApi(me.doctor_id)
  const others = DEMO_DOCTORS.filter((d) => d.doctor_id !== me.doctor_id)
  const [doctorId, setDoctorId] = useState<string>(others[0]?.doctor_id ?? '')
  const [role, setRole] = useState('attending')
  const [pub, setPub] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const act = async (fn: () => Promise<void>, done: string) => {
    setBusy(true)
    setMsg(null)
    try {
      await fn()
      setMsg({ ok: true, text: done })
      await onChange()
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  if (!org.org_key_registered)
    return (
      <div className="mt-2 text-sm">
        <button
          disabled={busy}
          onClick={() => act(() => createOrgKey(api, me, org.org_id), 'Care-team key created and granted to you.')}
          className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-50"
        >
          Create care-team key
        </button>
        <span className="ml-2 text-xs text-slate-500">Generated here; only the public key is sent.</span>
        {msg && <Msg {...msg} />}
      </div>
    )

  if (!org.hasLocalKey)
    return <p className="mt-2 text-xs text-slate-500">The care-team key was created in another browser; grant yourself from there.</p>

  return (
    <div className="mt-3 space-y-2 text-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">Admin: members</div>
      <div className="flex flex-wrap items-center gap-2">
        <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)} className="rounded border border-slate-300 px-2 py-1">
          {others.map((d) => (
            <option key={d.doctor_id} value={d.doctor_id}>{d.display_name}</option>
          ))}
        </select>
        <select value={role} onChange={(e) => setRole(e.target.value)} className="rounded border border-slate-300 px-2 py-1">
          <option value="attending">attending</option>
          <option value="on_call">on call</option>
          <option value="admin">admin</option>
        </select>
        <input
          value={pub}
          onChange={(e) => setPub(e.target.value)}
          placeholder="Paste their public key"
          className="min-w-64 flex-1 rounded border border-slate-300 px-2 py-1 font-mono text-xs"
        />
        <button
          disabled={busy || !pub.trim()}
          onClick={() => act(async () => { await addAndGrant(api, org.org_id, doctorId, role, pub); setPub('') }, `${doctorName(doctorId)} added and granted.`)}
          className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-50"
        >
          Add and grant
        </button>
        <button
          disabled={busy}
          onClick={() => {
            if (confirm(`Revoke ${doctorName(doctorId)}? They lose access to ${org.display_name}'s records immediately.`))
              act(() => revokeMember(api, org.org_id, doctorId, role), `${doctorName(doctorId)} revoked.`)
          }}
          className="rounded border border-red-300 px-3 py-1 text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          Revoke
        </button>
      </div>
      {msg && <Msg {...msg} />}
    </div>
  )
}

const Msg = ({ ok, text }: { ok: boolean; text: string }) => (
  <p className={`text-xs ${ok ? 'text-emerald-700' : 'text-red-700'}`}>{text}</p>
)
