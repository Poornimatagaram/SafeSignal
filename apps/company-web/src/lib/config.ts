// Set in apps/company-web/.env.local (git-ignored). Demo-grade identity headers only; no secrets.
const env = import.meta.env

export const config = {
  baseUrl: ((env.VITE_COMPANY_SERVICE_URL as string | undefined) ?? 'http://127.0.0.1:8000').replace(/\/$/, ''),
  defaultProgramId: (env.VITE_COMPANY_PROGRAM_ID as string | undefined) ?? 'prog_demo_01',
  actorId: (env.VITE_COMPANY_ACTOR_ID as string | undefined) ?? 'co_demo_analyst',
}

// The three company roles (schema/enums.json). Each call uses the narrowest role it needs.
export type CompanyRole = 'company_reader' | 'company_admin' | 'company_safety'
