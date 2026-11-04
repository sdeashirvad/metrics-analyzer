export type EntryTarget = 'legacy' | 'v2' | 'redirect'

const LEGACY_ALIAS = /^\/(dashboard|overview|metrics|investigations|glossary)(\/|$)/

/** Decides which entry a pathname loads. Search and hash stay with the caller. */
export function resolveEntry(pathname: string): EntryTarget {
  if (pathname === '/legacy' || pathname.startsWith('/legacy/')) return 'legacy'
  if (LEGACY_ALIAS.test(pathname)) return 'redirect'
  return 'v2'
}
