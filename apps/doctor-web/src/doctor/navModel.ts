// Top bar data: home sections and how a hospital's key status reads.
import type { OrgStatus } from '../lib/keys'

export const SECTIONS: [string, string][] = [
  ['how', 'How it works'],
  ['patients', 'Patients'],
  ['alerts', 'Alerts'],
  ['privacy', 'Privacy'],
  ['questions', 'Questions'],
]

export function keyStatus(o: OrgStatus): string {
  if (o.hasLocalKey) return 'Key in this browser'
  if (o.grantMismatch) return 'Grant made for another browser'
  if (o.has_key_grant) return 'Key grant waiting'
  return o.org_key_registered ? 'Waiting for a key grant' : 'No care-team key yet'
}
