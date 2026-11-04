import { portfolioUrl } from './config'
import { apiGet, type ApiResult } from './http'
import { appendQuery, scopeParams, type QueryParams } from './query'
import type {
  ApplicationDetail,
  ApplicationHistory,
  ApplicationInvestigation,
  AttributeDistribution,
  ComplianceDistribution,
  DataCoverage,
  DefinitionsData,
  DistributionDimension,
  MetricApplications,
  MetricBreakdown,
  MetricBreakdownDimension,
  MetricInvestigation,
  MetricPreview,
  MetricRegister,
  MetricSummary,
  MetricTrend,
  OrgContribution,
  PortfolioApplications,
  PortfolioFilters,
  PortfolioOverview,
  PortfolioStatus,
  PortfolioTrends,
  ScopeFilters,
  TestingDistribution,
} from './types'

function get<T>(path: string, params?: QueryParams): Promise<ApiResult<T>> {
  return apiGet<T>(portfolioUrl(params ? appendQuery(path, params) : path))
}

export function getStatus(): Promise<ApiResult<PortfolioStatus>> {
  return get('/status')
}

export function getFilters(): Promise<ApiResult<PortfolioFilters>> {
  return get('/filters')
}

export function getDefinitions(): Promise<ApiResult<DefinitionsData>> {
  return get('/definitions')
}

export function getOverview(filters: ScopeFilters = {}): Promise<ApiResult<PortfolioOverview>> {
  return get('/overview', scopeParams(filters))
}

export function getTrends(filters: ScopeFilters = {}): Promise<ApiResult<PortfolioTrends>> {
  const params = scopeParams(filters)
  delete params.month
  return get('/trends', params)
}

export function getComplianceDistribution(filters: ScopeFilters = {}): Promise<ApiResult<ComplianceDistribution>> {
  return get('/distributions/compliance', scopeParams(filters))
}

export function getTestingDistribution(filters: ScopeFilters = {}): Promise<ApiResult<TestingDistribution>> {
  return get('/distributions/testing', { ...scopeParams(filters), series: true })
}

export function getAttributeDistribution(
  dimension: DistributionDimension,
  filters: ScopeFilters = {},
): Promise<ApiResult<AttributeDistribution>> {
  return get(`/distributions/${dimension}`, scopeParams(filters))
}

export function getOrgContribution(
  filters: ScopeFilters = {},
  options: { level?: 1 | 2; parent?: string; sort?: string; page?: number; pageSize?: number } = {},
): Promise<ApiResult<OrgContribution>> {
  const params = scopeParams(filters)
  delete params.l1
  delete params.l2
  return get('/org/contribution', {
    ...params,
    level: options.level,
    parent: options.parent,
    sort: options.sort,
    page: options.page,
    pageSize: options.pageSize,
  })
}

export function getDataCoverage(month?: string): Promise<ApiResult<DataCoverage>> {
  return get('/data-coverage', { month })
}

export function getApplications(
  filters: ScopeFilters = {},
  options: { attention?: string; metricId?: string; q?: string; sort?: string; page?: number; pageSize?: number } = {},
): Promise<ApiResult<PortfolioApplications>> {
  return get('/applications', { ...scopeParams(filters), ...options })
}

export function getMetrics(
  filters: ScopeFilters = {},
  options: {
    q?: string
    hasNonCompliant?: boolean
    denominatorScope?: string[]
    sort?: string
    page?: number
    pageSize?: number
    rag?: string[]
  } = {},
): Promise<ApiResult<MetricRegister>> {
  return get('/metrics', {
    ...scopeParams(filters),
    q: options.q,
    hasNonCompliant: options.hasNonCompliant ? true : undefined,
    denominatorScope: options.denominatorScope,
    rag: options.rag,
    sort: options.sort,
    page: options.page,
    pageSize: options.pageSize,
  })
}

export function getMetricPreview(metricId: string, filters: ScopeFilters = {}): Promise<ApiResult<MetricPreview>> {
  return get(`/metrics/${encodeURIComponent(metricId)}/preview`, scopeParams(filters))
}

export function getMetric(metricId: string, filters: ScopeFilters = {}): Promise<ApiResult<MetricSummary>> {
  return get(`/metrics/${encodeURIComponent(metricId)}`, scopeParams(filters))
}

export function getMetricTrend(metricId: string, filters: ScopeFilters = {}): Promise<ApiResult<MetricTrend>> {
  const params = scopeParams(filters)
  delete params.month
  return get(`/metrics/${encodeURIComponent(metricId)}/trend`, params)
}

export function getMetricBreakdowns(
  metricId: string,
  filters: ScopeFilters = {},
  options: { dimension: MetricBreakdownDimension; level?: 1 | 2; parent?: string; sort?: string; page?: number; pageSize?: number },
): Promise<ApiResult<MetricBreakdown>> {
  return get(`/metrics/${encodeURIComponent(metricId)}/breakdowns`, { ...scopeParams(filters), ...options })
}

export function getMetricApplications(
  metricId: string,
  filters: ScopeFilters = {},
  options: { status?: string[]; q?: string; sort?: string; page?: number; pageSize?: number } = {},
): Promise<ApiResult<MetricApplications>> {
  return get(`/metrics/${encodeURIComponent(metricId)}/applications`, {
    ...scopeParams(filters),
    status: options.status,
    q: options.q,
    sort: options.sort,
    page: options.page,
    pageSize: options.pageSize,
  })
}

export function getApplication(
  eonId: string,
  options: { month?: string; includeOwners?: boolean } = {},
): Promise<ApiResult<ApplicationDetail>> {
  return get(`/applications/${encodeURIComponent(eonId)}`, {
    month: options.month,
    includeOwners: options.includeOwners ? true : undefined,
  })
}

export function getApplicationHistory(eonId: string, metricId?: string): Promise<ApiResult<ApplicationHistory>> {
  return get(`/applications/${encodeURIComponent(eonId)}/history`, { metricId })
}

export interface InvestigationOptions {
  runId?: string
  fallback?: 'precomputed'
  includeOwners?: boolean
  metricId?: string
}

export function getMetricInvestigation(
  metricId: string,
  filters: ScopeFilters = {},
  options: InvestigationOptions = {},
): Promise<ApiResult<MetricInvestigation>> {
  return get(`/investigations/metrics/${encodeURIComponent(metricId)}`, {
    ...scopeParams(filters),
    runId: options.runId,
    fallback: options.fallback,
  })
}

export function getApplicationInvestigation(
  eonId: string,
  filters: ScopeFilters = {},
  options: InvestigationOptions = {},
): Promise<ApiResult<ApplicationInvestigation>> {
  return get(`/investigations/applications/${encodeURIComponent(eonId)}`, {
    month: filters.month,
    metricId: options.metricId,
    includeOwners: options.includeOwners ? true : undefined,
    runId: options.runId,
    fallback: options.fallback,
  })
}
