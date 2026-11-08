// Validates a decrypted payload against schema/doctor_payload.json (JSON Schema 2020-12), the contract's source of truth.
import Ajv2020 from 'ajv/dist/2020'
import doctorPayloadSchema from '../../../../schema/doctor_payload.json'
import type { DoctorPayload } from './types'

const ajv = new Ajv2020({ allErrors: true })
const check = ajv.compile<DoctorPayload>(doctorPayloadSchema)

// Error text names the field and rule only, never the value (decrypted content must not leak into logs).
export function validateDoctorPayload(raw: unknown): DoctorPayload {
  if (check(raw)) return raw
  const first = check.errors?.[0]
  throw new Error(`schema: ${first?.instancePath || '/'} ${first?.keyword ?? 'invalid'}`)
}
