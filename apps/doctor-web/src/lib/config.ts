// Set in apps/doctor-web/.env.local (git-ignored). Demo IDs come from schema/demo_fixtures.json.
const env = import.meta.env

export const config = {
  baseUrl: ((env.VITE_DOCTOR_SERVICE_URL as string | undefined) ?? 'http://127.0.0.1:8000').replace(/\/$/, ''),
  caregiverId: (env.VITE_DOCTOR_CAREGIVER_ID as string | undefined) ?? 'cg_7e21c9a4',
  caregiverPatientLabel: (env.VITE_DOCTOR_CAREGIVER_PATIENT_LABEL as string | undefined) ?? 'Walter',
  pollMs: Number(env.VITE_DOCTOR_POLL_MS ?? 10000),
}

// Demo doctors (schema/demo_fixtures.json → doctors). Only IDs and display names; patient profiles are not bundled.
export const DEMO_DOCTORS = [
  { doctor_id: 'dr_3a7f10b2', display_name: 'Dr. Shah' },
  { doctor_id: 'dr_b29c4e71', display_name: 'Dr. Patel' },
  { doctor_id: 'dr_c71e0f9a', display_name: 'Dr. Rivera' },
  { doctor_id: 'dr_d4a8e2b6', display_name: 'Dr. Okafor' },
] as const

export const doctorName = (id: string) => DEMO_DOCTORS.find((d) => d.doctor_id === id)?.display_name ?? id
