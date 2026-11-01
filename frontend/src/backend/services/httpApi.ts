import type {
  ControlNote,
  DeskBreakdown,
  DqInvestigation,
  DqSummary,
  ExceptionPage,
  ExceptionQuery,
  Frequency,
  Investigation,
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
import { api as mockApi } from './mockApi'

const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api/v1').replace(/\/$/, '')

const FAMILY_ORDER = ['technology_risk', 'data_quality'] as const
const STATUS_RANK: Record<RagStatus, number> = { red: 0, amber: 1, insufficient_data: 2, green: 3 }

function isDataQuality(metricId: string): boolean {
  return metricId.startsWith('DQ-')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let message = response.statusText || 'Request failed'
    try {
      const body = (await response.json()) as { message?: string }
      if (body.message) message = body.message
    } catch {
      message = response.statusText || message
    }
    const code = response.status === 404 ? 'NOT_FOUND' : response.status >= 500 ? 'UPSTREAM' : 'BAD_REQUEST'
    throw new ApiError(code, message, response.status)
  }
  return response.json() as Promise<T>
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

export function generateDqSummary(controlId: string, forceRefresh: boolean): Promise<DqSummary> {
  return request(`/dq/controls/${controlId}/analyses`, {
    method: 'POST',
    body: JSON.stringify({ analysisType: 'SUMMARY', forceRefresh }),
  })
}

export const api: RiskApi = {
  async getOverview(query?: OverviewQuery): Promise<OverviewResponse> {
    const [tech, dataQuality] = await Promise.all([mockApi.getOverview(query), request<OverviewResponse['dataQuality']>('/dq/overview')])
    return { ...tech, dataQuality }
  },

  async listMetrics(query?: MetricListQuery): Promise<MetricListResponse> {
    if (query?.family === 'technology_risk') return mockApi.listMetrics(query)
    if (query?.family === 'data_quality') return dqList(query)
    const [tech, dq] = await Promise.all([
      mockApi.listMetrics({ ...query, family: 'technology_risk', page: 1, pageSize: 100 }),
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
    return mockApi.getMetric(metricId)
  },

  getTrend(metricId: string): Promise<TrendResponse> {
    if (isDataQuality(metricId)) return request<TrendResponse>(`/dq/controls/${metricId}/trend`)
    return mockApi.getTrend(metricId)
  },

  listInvestigations() {
    return mockApi.listInvestigations()
  },

  getInvestigation(metricId: string): Promise<Investigation | DqInvestigation> {
    if (!isDataQuality(metricId)) return mockApi.getInvestigation(metricId)
    return request<DqInvestigation>(`/dq/controls/${metricId}/analyses`, {
      method: 'POST',
      body: JSON.stringify({ analysisType: 'INVESTIGATION', forceRefresh: false }),
    })
  },

  getOrgContribution(metricId: string): Promise<OrgContribution> {
    return mockApi.getOrgContribution(metricId)
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
