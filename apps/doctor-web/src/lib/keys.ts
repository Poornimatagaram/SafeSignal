// Personal and organization keys (contract 2.0, D-064). Private keys stay in IndexedDB; only public keys and
// sealed (wrapped) org keys are sent. See ARCHITECTURE.md §2.
import type { DoctorApi } from './api'
import { generateKeyPair, isPublicKey, unwrapOrgKey, wrapOrgKey, type KeyPair } from './crypto'
import { db } from './db'
import type { DrKey, OrgMembership } from './types'

const now = () => new Date().toISOString()
const pair = (k: { public_key: string; private_key: string }): KeyPair => ({ publicKey: k.public_key, privateKey: k.private_key })

export interface OrgStatus extends OrgMembership {
  hasLocalKey: boolean
  grantMismatch: boolean // a grant exists but was made for this doctor's key in another browser
}

// First launch: pick the identity and create the personal key pair (DW-19).
export async function createIdentity(doctorId: string): Promise<DrKey> {
  const kp = await generateKeyPair()
  const k: DrKey = { doctor_id: doctorId, public_key: kp.publicKey, private_key: kp.privateKey, created_at: now() }
  await db.putKey(k)
  return k
}

// Register the personal public key on every start (DW-05); key grants are sealed to it.
export async function registerPersonalKey(api: DoctorApi, me: DrKey) {
  await api.registerPublicKey(me.public_key)
}

// Memberships → org keys: unwrap any new key grant; forget orgs this doctor no longer belongs to (DW-20).
export async function refreshOrgs(api: DoctorApi, me: DrKey): Promise<OrgStatus[]> {
  const orgs = await api.orgs()
  const active = new Set(orgs.map((o) => o.org_id))
  for (const k of await db.orgKeys()) if (!active.has(k.org_id)) await db.forgetOrg(k.org_id)

  const out: OrgStatus[] = []
  for (const o of orgs) {
    let local = await db.orgKey(o.org_id)
    if (local && !o.has_key_grant && o.role !== 'admin') {
      await db.forgetOrg(o.org_id) // grant withdrawn
      local = undefined
    }
    let grantMismatch = false
    if (!local && o.has_key_grant) {
      const grant = await api.myKeyGrant(o.org_id)
      try {
        const kp = await unwrapOrgKey(grant.wrapped_key, pair(me))
        await db.putOrgKey({ org_id: o.org_id, public_key: kp.publicKey, private_key: kp.privateKey, obtained_at: now() })
        local = await db.orgKey(o.org_id)
      } catch {
        // The grant was sealed to this doctor's key in another browser (DW-19). Keep the other orgs working.
        grantMismatch = true
      }
    }
    out.push({ ...o, hasLocalKey: !!local, grantMismatch })
  }
  return out
}

// Admin, once per org: create the care-team key here, register its public key, and grant it to yourself.
export async function createOrgKey(api: DoctorApi, me: DrKey, orgId: string) {
  const kp = await generateKeyPair()
  await api.registerOrgKey(orgId, kp.publicKey)
  await db.putOrgKey({ org_id: orgId, public_key: kp.publicKey, private_key: kp.privateKey, obtained_at: now() })
  await api.grantKey(orgId, me.doctor_id, await wrapOrgKey(kp.privateKey, me.public_key))
}

// Admin: add a doctor as an active member and grant them the org key, sealed to their personal public key.
// The public key is pasted by hand (no lookup endpoint yet, DW-18).
export async function addAndGrant(api: DoctorApi, orgId: string, doctorId: string, role: string, memberPublicKey: string) {
  const key = memberPublicKey.trim()
  if (!(await isPublicKey(key))) throw new Error('That is not a 32-byte base64 public key.')
  const org = await db.orgKey(orgId)
  if (!org) throw new Error('This browser does not hold the organization key.')
  await api.setMember(orgId, doctorId, role, 'active')
  await api.grantKey(orgId, doctorId, await wrapOrgKey(org.private_key, key))
}

// Admin: revoke a member; the service deletes their key grant and refuses them from now on.
export async function revokeMember(api: DoctorApi, orgId: string, doctorId: string, role: string) {
  await api.setMember(orgId, doctorId, role, 'revoked')
}
