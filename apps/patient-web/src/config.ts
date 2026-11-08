import { resolveDisplayName } from './displayName.ts'
import { resolveRuntimeUrl } from './runtimeUrl.ts'

/** Base URL of the local patient runtime (`VITE_PATIENT_RUNTIME_URL`, default http://127.0.0.1:8001). */
export const RUNTIME_URL = resolveRuntimeUrl(import.meta.env.VITE_PATIENT_RUNTIME_URL)

/** The name in the greeting (`VITE_PATIENT_DISPLAY_NAME`, default "Walter"). Shown on screen only. */
export const DISPLAY_NAME = resolveDisplayName(import.meta.env.VITE_PATIENT_DISPLAY_NAME)
