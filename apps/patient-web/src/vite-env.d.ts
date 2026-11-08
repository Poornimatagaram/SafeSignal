/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PATIENT_RUNTIME_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
