import type {
  ControlNote,
  DeskBreakdown,
  AnalysisOperation,
  DqInvestigation,
  DqSummary,
  ExceptionPage,
  ExceptionQuery,
  Frequency,
  Investigation,
  InvestigationSummary,
  MetricDetailResponse,
  MetricListItem,
  MetricListQuery,
  MetricListResponse,
  OrgContribution,
  OverviewQuery,
  OverviewResponse,
  RagStatus,
  RiskApi,
  TrendResponse,
} from '../contracts/types'
import { ApiError } from './errors'

const REQUEST_TIMEOUT_MS = 20_000

function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  if (configured) return configured.replace(/\/$/, '')
  if (import.meta.env.PROD) {
    throw new ApiError(
      'UPSTREAM',
      'This build has no API address. Set VITE_API_BASE_URL to the deployed API before building.',
      0,
    )
  }
  return 'http://localhost:8080/api/v1'
}

function friendlyMessage(status: number, serverMessage: string): string {
  if (status === 429) return 'Two analyses are already running. Wait for one to finish, then try again.'
  if (status >= 500) return 'The service could not complete that request. Try again in a moment.'
  if (status === 404) return serverMessage || 'That item was not found.'
  if (serverMessage && serverMessage.length < 240 && !/traceback|exception|stack|snowflake\.|sql/i.test(serverMessage)) {
    return serverMessage
  }
  return 'That request could not be completed.'
}

const FAMILY_ORDER = ['technology_risk', 'data_quality'] as const
const STATUS_RANK: Record<RagStatus, number> = { red: 0, amber: 1, insufficient_data: 2, green: 3 }

function isDataQuality(metricId: string): boolean {
  return metricId.startsWith('DQ-')
}

async function request<T>(path: string, init?: RequestInit, attempt = 0): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${apiBase()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
    if (!response.ok) {
      let serverMessage = ''
      try {
        const body = (await response.json()) as { message?: string }
        serverMessage = body.message ?? ''
      } catch {
        serverMessage = ''
      }
      if (method === 'GET' && response.status >= 500 && attempt < 1) {
        return request(path, init, attempt + 1)
      }
      const code = response.status === 404 ? 'NOT_FOUND' : response.status >= 500 || response.status === 429 ? 'UPSTREAM' : 'BAD_REQUEST'
      throw new ApiError(code, friendlyMessage(response.status, serverMessage), response.status)
    }
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (method === 'GET' && attempt < 1) return request(path, init, attempt + 1)
    const timedOut = error instanceof DOMException && error.name === 'AbortError'
    throw new ApiError(
      'UPSTREAM',
      timedOut ? 'The request took too long. Try again.' : 'The service could not be reached. Check the connection and try again.',
      0,
    )
  } finally {
    window.clearTimeout(timer)
  }
}

function queryString(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

async function dqList(query: MetricListQuery | undefined): Promise<MetricListResponse> {
  return request(
    `/dq/controls${queryString({
      q: query?.q,
      domain: query?.domain,
      status: query?.status,
      frequency: query?.frequency,
      investigation: query?.investigation,
      page: query?.page ?? 1,
      pageSize: query?.pageSize ?? 25,
    })}`,
  )
}

async function trList(query: MetricListQuery | undefined): Promise<MetricListResponse> {
  return request(
    `/tr/metrics${queryString({
      q: query?.q,
      domain: query?.domain,
      status: query?.status,
      frequency: query?.frequency,
      investigation: query?.investigation,
      page: query?.page ?? 1,
      pageSize: query?.pageSize ?? 25,
    })}`,
  )
}

function sortItems(items: MetricListItem[], byFamily: boolean): MetricListItem[] {
  return [...items].sort((a, b) => {
    if (byFamily && a.family !== b.family) return FAMILY_ORDER.indexOf(a.family) - FAMILY_ORDER.indexOf(b.family)
    const byStatus = STATUS_RANK[a.reading.status] - STATUS_RANK[b.reading.status]
    if (byStatus !== 0) return byStatus
    const aDate = a.reading.breachedOn ?? '9999-99-99'
    const bDate = b.reading.breachedOn ?? '9999-99-99'
    if (aDate !== bDate) return aDate < bDate ? -1 : 1
    return a.metric.id < b.metric.id ? -1 : 1
  })
}

export function getDqSummary(controlId: string): Promise<DqSummary> {
  return request(`/dq/controls/${controlId}/analyses/summary`)
}

export function generateDqSummary(controlId: string, forceRefresh: boolean): Promise<DqSummary | AnalysisOperation> {
  return request(`/dq/controls/${controlId}/analyses`, {
    method: 'POST',
    body: JSON.stringify({ analysisType: 'SUMMARY', forceRefresh }),
  })
}

/** Read-only. 200 when a completed investigation is cached, null on 404. Never starts a run. */
export async function getCachedDqInvestigation(controlId: string): Promise<DqInvestigation | null> {
  try {
    return await request<DqInvestigation>(`/dq/controls/${controlId}/analyses/investigation`)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export function startDqInvestigation(controlId: string, forceRefresh: boolean): Promise<DqInvestigation | AnalysisOperation> {
  return request(`/dq/controls/${controlId}/analyses`, {
    method: 'POST',
    body: JSON.stringify({ analysisType: 'INVESTIGATION', forceRefresh }),
  })
}

export function pollDqInvestigation(controlId: string, runId: string): Promise<AnalysisOperation> {
  return request(`/dq/controls/${controlId}/analyses/operations/${runId}`)
}

export function previewDqInvestigation(controlId: string): Promise<DqInvestigation> {
  return request(`/dq/controls/${controlId}/analyses/preview`)
}

export function activeDqInvestigation(controlId: string): Promise<AnalysisOperation> {
  return request(`/dq/controls/${controlId}/analyses/active`)
}

function isDqInvestigation(value: DqInvestigation | AnalysisOperation): value is DqInvestigation {
  return 'kind' in value && value.kind === 'data_quality'
}

async function waitForInvestigation(controlId: string, runId: string): Promise<DqInvestigation> {
  let delay = 2000
  const started = Date.now()
  while (Date.now() - started < 20 * 60 * 1000) {
    const status = await pollDqInvestigation(controlId, runId)
    if (status.status === 'COMPLETED' && status.result) return status.result
    if (status.status === 'FAILED') throw new ApiError('UPSTREAM', status.message || 'The investigation did not finish.', 502)
    await new Promise((resolve) => setTimeout(resolve, delay))
    delay = Math.min(8000, delay + 500)
  }
  throw new ApiError('UPSTREAM', 'The investigation is still running. Reload this page to check it.', 504)
}

export async function loadDqInvestigation(controlId: string, forceRefresh: boolean): Promise<DqInvestigation> {
  if (!forceRefresh) {
    const active = await activeDqInvestigation(controlId)
    if (active.status === 'RUNNING' && active.runId) return waitForInvestigation(controlId, active.runId)
  }
  const started = await startDqInvestigation(controlId, forceRefresh)
  if (isDqInvestigation(started)) return started
  if (!started.runId) throw new ApiError('UPSTREAM', 'The investigation did not start.', 502)
  return waitForInvestigation(controlId, started.runId)
}

export const api: RiskApi = {
  async getOverview(query?: OverviewQuery): Promise<OverviewResponse> {
    const [tech, dataQuality] = await Promise.all([
      request<Omit<OverviewResponse, 'dataQuality'>>('/tr/overview'),
      request<OverviewResponse['dataQuality']>('/dq/overview'),
    ])
    if (query?.domain) {
      tech.investigations = tech.investigations.filter((item) => item.domain === query.domain)
    }
    return { ...tech, dataQuality }
  },

  async listMetrics(query?: MetricListQuery): Promise<MetricListResponse> {
    if (query?.family === 'technology_risk') return trList(query)
    if (query?.family === 'data_quality') return dqList(query)
    const [tech, dq] = await Promise.all([
      trList({ ...query, family: 'technology_risk', page: 1, pageSize: 100 }),
      dqList({ ...query, page: 1, pageSize: 100 }),
    ])
    const merged = sortItems([...tech.items, ...dq.items], !query?.family)
    const pageSize = Math.max(1, query?.pageSize ?? 25)
    const page = Math.max(1, query?.page ?? 1)
    const frequencies: Frequency[] = (['Daily', 'Weekly', 'Monthly'] as const).filter((value) =>
      merged.some((item) => item.metric.frequency === value),
    )
    return {
      items: merged.slice((page - 1) * pageSize, page * pageSize),
      total: merged.length,
      page,
      pageSize,
      facets: {
        domains: [...new Set([...tech.facets.domains, ...dq.facets.domains])],
        frequencies,
        statuses: ['red', 'amber', 'green', 'insufficient_data'],
        families: ['technology_risk', 'data_quality'],
        domainsByFamily: {
          technology_risk: tech.facets.domainsByFamily.technology_risk,
          data_quality: dq.facets.domainsByFamily.data_quality,
        },
      },
    }
  },

  getMetric(metricId: string): Promise<MetricDetailResponse> {
    if (isDataQuality(metricId)) return request<MetricDetailResponse>(`/dq/controls/${metricId}`)
    return request<MetricDetailResponse>(`/tr/metrics/${metricId}`)
  },

  getTrend(metricId: string): Promise<TrendResponse> {
    if (isDataQuality(metricId)) return request<TrendResponse>(`/dq/controls/${metricId}/trend`)
    return request<TrendResponse>(`/tr/metrics/${metricId}/trend`)
  },

  listInvestigations() {
    return request<{ items: InvestigationSummary[] }>('/tr/investigations')
  },

  getInvestigation(metricId: string): Promise<Investigation | DqInvestigation> {
    if (!isDataQuality(metricId)) return request<Investigation>(`/tr/metrics/${metricId}/investigation`)
    return loadDqInvestigation(metricId, false)
  },

  getOrgContribution(metricId: string): Promise<OrgContribution> {
    return request<OrgContribution>(`/tr/metrics/${metricId}/org`)
  },

  getDeskBreakdown(controlId: string, date?: string): Promise<DeskBreakdown> {
    return request<DeskBreakdown>(`/dq/controls/${controlId}/desks${queryString({ date })}`)
  },

  listExceptions(query?: ExceptionQuery): Promise<ExceptionPage> {
    return request<ExceptionPage>(
      `/dq/controls/${query?.controlId ?? ''}/exceptions${queryString({
        status: query?.status,
        page: query?.page ?? 1,
        pageSize: query?.pageSize ?? 25,
      })}`,
    )
  },

  getControlNotes(controlId: string): Promise<ControlNote> {
    return request<ControlNote>(`/dq/controls/${controlId}/notes`)
  },
}
