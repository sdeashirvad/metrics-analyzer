import { useCallback, useMemo } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { readScope } from '../api/query'
import type { ScopeFilters } from '../api/types'

export type ParamValue = string | string[] | null

const SCOPE_KEYS = ['month', 'orgTree', 'l1', 'l2', 'legalEntity', 'tier', 'risk', 'lifecycle', 'ma']

export function useScopeFilters() {
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const filters = useMemo(() => readScope(params), [params])

  const replace = useCallback(
    (changes: Record<string, ParamValue>) => {
      const next = new URLSearchParams(params)
      for (const [key, value] of Object.entries(changes)) {
        next.delete(key)
        if (value == null) continue
        const items = Array.isArray(value) ? value : [value]
        for (const item of items) {
          if (item !== '') next.append(key, item)
        }
      }
      setParams(next, { replace: true, preventScrollReset: true, state: location.state })
    },
    [params, setParams, location.state],
  )

  const replaceScope = useCallback(
    (nextFilters: ScopeFilters, extras?: Record<string, ParamValue>) => {
      const changes: Record<string, ParamValue> = {
        month: nextFilters.month ?? null,
        orgTree: null,
        l1: nextFilters.l1 ?? null,
        l2: nextFilters.l2 ?? null,
        legalEntity: nextFilters.legalEntity ?? null,
        tier: nextFilters.tier?.map(String) ?? null,
        risk: nextFilters.risk ?? null,
        lifecycle: nextFilters.lifecycle ?? null,
        ma: nextFilters.ma ?? null,
        page: null,
      }
      if (extras) Object.assign(changes, extras)
      replace(changes)
    },
    [replace],
  )

  return { filters, params, replace, replaceScope, scopeKeys: SCOPE_KEYS }
}
