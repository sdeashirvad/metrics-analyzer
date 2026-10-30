import type {
  DataQualityAtRisk,
  Investigation,
  InvestigationSummary,
  MetricFamily,
  MetricListItem,
  RagStatus,
  TrendResponse,
} from '../../backend/contracts/types'

export type StatusFilter = RagStatus | 'recovered'

export interface TechQueueItem {
  family: 'technology_risk'
  id: string
  name: string
  domain: string
  status: RagStatus
  item: MetricListItem
  summary: InvestigationSummary | undefined
  investigation: Investigation | undefined
  trend: TrendResponse | undefined
  investigationAvailable: boolean
  recovered: false
}

export interface DqQueueItem {
  family: 'data_quality'
  id: string
  name: string
  domain: string
  status: RagStatus
  control: DataQualityAtRisk
  investigationAvailable: boolean
  recovered: boolean
}

export type QueueItem = TechQueueItem | DqQueueItem

export interface TriageFilters {
  family: MetricFamily | null
  status: StatusFilter | null
  domain: string | null
  investigation: boolean
}

export function matchesFilters(item: QueueItem, filters: TriageFilters): boolean {
  if (filters.family && item.family !== filters.family) return false
  if (filters.domain && item.domain !== filters.domain) return false
  if (filters.investigation && !item.investigationAvailable) return false
  if (filters.status === 'recovered') return item.recovered
  if (item.recovered) return false
  if (filters.status) return item.status === filters.status
  return item.status === 'red' || item.status === 'amber'
}

export function rowId(id: string) {
  return `triage-${id}`
}
