/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PATIENT_RUNTIME_URL?: string
  readonly VITE_PATIENT_DISPLAY_NAME?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
