// Admin & access (#/admin): memberships and care-team keys, emergency access, and resetting this browser.
import { EmergencyAccess } from '../components/EmergencyAccess'
import { OrgPanel } from '../components/OrgPanel'
import { db } from '../lib/db'
import type { DoctorData } from '../lib/useDoctorData'
import { ArrowLeft } from './icons'

export function AdminPage({ data }: { data: DoctorData }) {
  if (!data.me) return null
  const me = data.me
  return (
    <>
      <section className="wrap d-hero">
        <a className="back" href="#/"><ArrowLeft />Back to overview</a>
        <p className="kicker">Admin &amp; access</p>
        <h1>Keys, members and emergency access.</h1>
        <p className="lede">Private keys are created and kept in this browser. Only public keys and sealed key grants are sent to the service.</p>
      </section>
      <div className="wrap admin-stack">
        <div className="admin-card"><OrgPanel me={me} orgs={data.orgs} onChange={data.refresh} /></div>
        <div className="admin-card"><EmergencyAccess me={me} orgs={data.orgs} /></div>
        <div className="card">
          <h3>Reset this browser</h3>
          <p style={{ marginTop: 6 }}>Removes your identity, every key and every stored record from this browser. Use it after a demo, or before handing the device on.</p>
          <div className="pp-actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={async () => {
                if (!confirm('Wipe this browser: the identity, all keys and all stored records?')) return
                await db.wipe()
                location.hash = '#/'
                location.reload()
              }}
            >
              Reset this browser
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
