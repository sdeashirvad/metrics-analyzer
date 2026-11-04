import { appendQuery, scopeParams, type QueryParams } from './api/query'
import type { ActiveFilters, ContextRequest, ScopeFilters } from './api/types'

export function scopeKey(filters: ScopeFilters): string {
  return appendQuery('', scopeParams(filters)) || 'default'
}

export function scopedTo(path: string, filters: ScopeFilters, extra?: QueryParams): string {
  return appendQuery(path, { ...scopeParams(filters), ...extra })
}

/** Ids and filters only. Rendered context text stays on the server. */
export function contextScope(filters: ScopeFilters, extra?: { metricId?: string; eonId?: string }): ContextRequest['scope'] {
  const partial: Partial<ActiveFilters> = {}
  if (filters.month) partial.month = filters.month
  if (filters.l1?.length) partial.l1 = filters.l1
  if (filters.l2?.length) partial.l2 = filters.l2
  if (filters.legalEntity?.length) partial.legalEntity = filters.legalEntity
  if (filters.tier?.length) partial.tier = filters.tier
  if (filters.risk?.length) partial.risk = filters.risk
  if (filters.lifecycle?.length) partial.lifecycle = filters.lifecycle
  if (filters.ma) partial.ma = filters.ma
  return {
    month: filters.month,
    metricId: extra?.metricId,
    eonId: extra?.eonId,
    filters: Object.keys(partial).length ? partial : undefined,
  }
}
