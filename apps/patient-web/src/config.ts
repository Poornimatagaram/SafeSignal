import { resolveRuntimeUrl } from './runtimeUrl.ts'

/** Base URL of the local patient runtime (`VITE_PATIENT_RUNTIME_URL`, default http://127.0.0.1:8001). */
export const RUNTIME_URL = resolveRuntimeUrl(import.meta.env.VITE_PATIENT_RUNTIME_URL)
