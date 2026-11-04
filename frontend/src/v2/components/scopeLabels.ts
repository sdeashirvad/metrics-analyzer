import { getFilters } from '../api/portfolio'
import { useApiQuery } from '../hooks/useApiQuery'

/** The structural subset of the shared filters that this module describes. */
export interface DescribableFilters {
  orgTree?: string | null
  l1?: string[]
  l2?: string[]
  legalEntity?: string[]
  tier?: number[]
  risk?: string[]
  lifecycle?: string[]
  ma?: string | null
}

export type LegalEntityNames = Record<string, string>

/**
 * Display name for a legal entity. Only names the catalog confirms are used; an unknown code is shown
 * as it arrived so a source id is never replaced by a guess.
 */
export function legalEntityLabel(code: string, names: LegalEntityNames): string {
  return names[code] ?? code
}

/** Name with the source id kept as secondary text, for places where both help (menus, tooltips). */
export function legalEntityWithCode(code: string, names: LegalEntityNames): string {
  const name = names[code]
  return name && name !== code ? `${name} (${code})` : code
}

/** Catalog-backed legal entity names. Empty until the catalog loads; never fabricated. */
export function useLegalEntityNames(): LegalEntityNames {
  const catalog = useApiQuery('filters', 'catalog', getFilters)
  const names: LegalEntityNames = {}
  for (const item of catalog.data?.legalEntities ?? []) names[item.code] = item.name
  return names
}

/** Short, ordered description of the active filters. Empty when only the default scope applies. */
export function describeFilters(filters: DescribableFilters, names: LegalEntityNames = {}): string[] {
  return [
    filters.orgTree === 'BU' ? 'Bank group' : null,
    ...(filters.l1 ?? []),
    ...(filters.l2 ?? []),
    ...(filters.legalEntity ?? []).map((code) => legalEntityLabel(code, names)),
    ...(filters.tier ?? []).map((tier) => `Tier ${tier}`),
    ...(filters.risk ?? []),
    ...(filters.lifecycle ?? []),
    filters.ma ? `M&A ${filters.ma}` : null,
  ].filter((item): item is string => Boolean(item))
}
