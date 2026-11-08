// Doctor-layer client: only the calls the doctor brief allows (contract 2.0), plus the caregiver alerts.
import { config } from './config'
import type {
  Alert, EmergencyAccessResult, EmergencyReason, Envelope, KeyGrant, LinkedPatient, MemberState, OrgMembership,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Role = 'doctor' | 'caregiver'

// Error text carries the method, path, status and the service's error code only, never a request body.
async function call<T>(role: Role, actorId: string, method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(config.baseUrl + path, {
    method,
    headers: { 'X-Role': role, 'X-Actor-Id': actorId, ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const code = await res.json().then((j) => j?.error ?? j?.detail?.error ?? '').catch(() => '')
    throw new ApiError(res.status, `${method} ${path} → ${res.status}${code ? ` ${code}` : ''}`)
  }
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

const PAGE = 100
const q = encodeURIComponent
const since = (s?: string) => (s ? `?since=${q(s)}` : '')

// Pages through ?since= on received_at (D-054): oldest first, at most 100 per call.
async function paged<T extends { received_at: string }>(fetchPage: (cursor?: string) => Promise<T[]>, from?: string) {
  const out: T[] = []
  let cursor = from
  for (;;) {
    const page = (await fetchPage(cursor)) ?? []
    out.push(...page)
    if (page.length < PAGE) return out
    cursor = page[page.length - 1].received_at
  }
}

export function doctorApi(me: string) {
  const doc = <T,>(method: string, path: string, body?: unknown) => call<T>('doctor', me, method, path, body)
  const org = (id: string) => `/v1/orgs/${q(id)}`
  return {
    registerPublicKey: (publicKey: string) => doc<unknown>('PUT', `/v1/doctors/${q(me)}/public-key`, { public_key: publicKey }),
    orgs: async () => (await doc<OrgMembership[]>('GET', `/v1/doctors/${q(me)}/orgs`)) ?? [],

    // Admin only
    registerOrgKey: (orgId: string, publicKey: string) => doc<unknown>('PUT', `${org(orgId)}/public-key`, { public_key: publicKey }),
    setMember: (orgId: string, doctorId: string, role: string, status: 'active' | 'revoked') =>
      doc<MemberState>('PUT', `${org(orgId)}/members/${q(doctorId)}`, { role, status }),
    grantKey: (orgId: string, doctorId: string, wrappedKey: string) =>
      doc<unknown>('POST', `${org(orgId)}/key-grants`, { doctor_id: doctorId, wrapped_key: wrappedKey }),

    // Members
    myKeyGrant: (orgId: string) => doc<KeyGrant>('GET', `${org(orgId)}/key-grants/${q(me)}`),
    patients: async (orgId: string) => (await doc<LinkedPatient[]>('GET', `${org(orgId)}/patients`)) ?? [],
    envelopes: (orgId: string, from?: string) =>
      paged((c) => doc<Envelope[]>('GET', `${org(orgId)}/envelopes${since(c)}`), from),
    ack: (orgId: string, envelopeId: string) => doc<unknown>('POST', `${org(orgId)}/envelopes/${q(envelopeId)}/ack`),
    alerts: (orgId: string, from?: string) => paged((c) => doc<Alert[]>('GET', `${org(orgId)}/alerts${since(c)}`), from),
    emergencyAccess: (orgId: string, patientRef: string, reason: EmergencyReason) =>
      doc<EmergencyAccessResult>('POST', `${org(orgId)}/emergency-access`, { patient_ref: patientRef, reason }),
  }
}
export type DoctorApi = ReturnType<typeof doctorApi>

export const caregiverApi = {
  alerts: async () =>
    (await call<Alert[]>('caregiver', config.caregiverId, 'GET', `/v1/caregivers/${q(config.caregiverId)}/alerts`)) ?? [],
}
