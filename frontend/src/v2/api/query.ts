import type { ScopeFilters } from './types'

export type QueryValue = string | number | boolean | null | undefined | Array<string | number>
export type QueryParams = Record<string, QueryValue>

export function appendQuery(path: string, params: QueryParams): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value == null || value === '') continue
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== '') search.append(key, String(item))
      }
    } else {
      search.append(key, String(value))
    }
  }
  const text = search.toString()
  return text ? `${path}?${text}` : path
}

export function scopeParams(filters: ScopeFilters = {}): QueryParams {
  return {
    month: filters.month,
    l1: filters.l1,
    l2: filters.l2,
    legalEntity: filters.legalEntity,
    tier: filters.tier,
    risk: filters.risk,
    lifecycle: filters.lifecycle,
    ma: filters.ma,
  }
}

function present(values: string[]): string[] | undefined {
  const next = values.filter((value) => value !== '')
  return next.length ? next : undefined
}

export function readScope(params: URLSearchParams): ScopeFilters {
  // The organisation tree is always business organisation. A leftover bank-group URL is ignored,
  // and its level filters are dropped because those names belong to the other tree.
  const bankGroup = params.get('orgTree') === 'BU'
  const ma = params.get('ma')
  const tier = params
    .getAll('tier')
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item))
  return {
    month: params.get('month') || undefined,
    l1: bankGroup ? undefined : present(params.getAll('l1')),
    l2: bankGroup ? undefined : present(params.getAll('l2')),
    legalEntity: present(params.getAll('legalEntity')),
    tier: tier.length ? tier : undefined,
    risk: present(params.getAll('risk')),
    lifecycle: present(params.getAll('lifecycle')),
    ma: ma === 'Y' || ma === 'N' ? ma : undefined,
  }
}

export function readPositiveInt(params: URLSearchParams, key: string, fallback: number): number {
  const value = Number(params.get(key))
  return Number.isInteger(value) && value > 0 ? value : fallback
}
