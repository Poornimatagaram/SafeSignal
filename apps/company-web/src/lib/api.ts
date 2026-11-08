// Company endpoints only (Scoping Doc 26.8): the portal never calls relay, doctor or patient endpoints.
import type { components } from '@sentinel/contract/api'
import { config, type CompanyRole } from './config'

type S = components['schemas']
export type CohortWeeklyRow = S['CohortWeeklyRow']
export type CompletionRow = S['CompletionRow']
export type ProgramsResponse = S['ProgramsResponse']
export type ProgramInfo = S['ProgramInfo']
export type CohortInfo = S['CohortInfo']
export type Document = S['Document']
export type TermsResponse = S['TermsResponse']
export type SurveyResponse = S['SurveyResponse']
export type SurveyPublished = S['SurveyPublished']
export type FieldError = S['FieldError']

// Body of PUT /v1/company/cohorts/{id}/survey (schema/survey_config.json).
export interface SurveyConfig {
  schedule: { every_days: number }
  questions: { question_id: string; purpose: string; asks: string[] }[]
}

export class ApiError extends Error {
  status: number
  errors: FieldError[]
  constructor(status: number, message: string, errors: FieldError[] = []) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

async function call(role: CompanyRole, method: string, path: string, body?: unknown): Promise<Response> {
  let res: Response
  try {
    res = await fetch(config.baseUrl + path, {
      method,
      headers: {
        'X-Role': role,
        'X-Actor-Id': config.actorId,
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, `Cannot reach the service at ${config.baseUrl}. Is it running, and is this page's origin in SENTINEL_ALLOWED_ORIGINS?`)
  }
  if (!res.ok) {
    let detail = res.statusText
    let errors: FieldError[] = []
    try {
      const b = (await res.json()) as S['ErrorBody']
      detail = b.detail || b.error
      errors = b.errors ?? []
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail, errors)
  }
  return res
}

const q = encodeURIComponent
const json = async <T,>(p: Promise<Response>) => (await (await p).json()) as T

export const api = {
  programs: () => json<ProgramsResponse>(call('company_reader', 'GET', '/v1/company/programs')),
  cohortsWeekly: (programId: string) =>
    json<CohortWeeklyRow[]>(call('company_reader', 'GET', `/v1/company/cohorts/weekly?program_id=${q(programId)}`)),
  completion: (programId: string) =>
    json<CompletionRow[]>(call('company_reader', 'GET', `/v1/company/completion?program_id=${q(programId)}`)),
  terms: (programId: string) =>
    json<TermsResponse>(call('company_reader', 'GET', `/v1/company/terms?program_id=${q(programId)}`)),
  documents: (programId: string) =>
    json<Document[]>(call('company_reader', 'GET', `/v1/company/documents?program_id=${q(programId)}`)),
  survey: (cohortId: string) =>
    json<SurveyResponse>(call('company_reader', 'GET', `/v1/company/cohorts/${q(cohortId)}/survey`)),
  publishSurvey: (cohortId: string, survey: SurveyConfig) =>
    json<SurveyPublished>(call('company_admin', 'PUT', `/v1/company/cohorts/${q(cohortId)}/survey`, survey)),
  exportRecords: async (programId: string, format: 'json' | 'csv') =>
    (await call('company_safety', 'GET', `/v1/company/records/export?program_id=${q(programId)}&format=${format}`)).blob(),
}
