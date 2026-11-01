import { useEffect, useState } from 'react'
import { getCachedDqInvestigation } from '../backend/services/httpApi'

export type CacheKind = 'cached' | 'not_cached' | 'unknown'

export interface CacheEntry {
  kind: CacheKind
  running: boolean
  at: number
}

const TTL_MS = 60_000
const HINT_KEY = 'ma-dq-cache-hint-v1'
const listeners = new Set<() => void>()
const entries = new Map<string, CacheEntry>()

function emit() {
  for (const listener of listeners) listener()
}

export function getCacheEntry(controlId: string): CacheEntry | undefined {
  return entries.get(controlId)
}

export function subscribeCache(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function put(controlId: string, patch: Partial<CacheEntry>) {
  const previous = entries.get(controlId)
  entries.set(controlId, {
    kind: patch.kind ?? previous?.kind ?? 'unknown',
    running: patch.running ?? previous?.running ?? false,
    at: patch.at ?? Date.now(),
  })
  emit()
}

export function markInvestigationCached(controlId: string) {
  put(controlId, { kind: 'cached', running: false, at: Date.now() })
  rememberCacheHint(controlId, true)
}

export function markInvestigationRunning(controlId: string, running: boolean) {
  const previous = entries.get(controlId)
  put(controlId, { kind: previous?.kind ?? 'unknown', running, at: previous?.at ?? Date.now() })
}

export function rememberCacheHint(controlId: string, cached: boolean) {
  try {
    const raw = localStorage.getItem(HINT_KEY)
    const ids = new Set<string>(raw ? (JSON.parse(raw) as string[]) : [])
    if (cached) ids.add(controlId)
    else ids.delete(controlId)
    localStorage.setItem(HINT_KEY, JSON.stringify([...ids].slice(-40)))
  } catch {
    /* The hint only chooses a loader. The chip never reads it. */
  }
}

export function cacheHint(controlId: string): boolean {
  try {
    const raw = localStorage.getItem(HINT_KEY)
    if (!raw || raw.length > 2000) return false
    const ids = JSON.parse(raw) as unknown
    return Array.isArray(ids) && ids.includes(controlId)
  } catch {
    return false
  }
}

export async function probeInvestigation(controlId: string, force = false): Promise<CacheKind> {
  const current = entries.get(controlId)
  if (!force && current && current.kind !== 'unknown' && Date.now() - current.at < TTL_MS) return current.kind
  try {
    const found = await getCachedDqInvestigation(controlId)
    const kind: CacheKind = found ? 'cached' : 'not_cached'
    put(controlId, { kind, at: Date.now() })
    if (found) rememberCacheHint(controlId, true)
    return kind
  } catch {
    put(controlId, { kind: 'unknown', at: Date.now() })
    return 'unknown'
  }
}

export async function probeInvestigations(controlIds: string[]): Promise<void> {
  const pending = [...new Set(controlIds)].filter((id) => {
    const current = entries.get(id)
    return !current || current.kind === 'unknown' || Date.now() - current.at >= TTL_MS
  })
  let cursor = 0
  async function worker() {
    while (cursor < pending.length) {
      const id = pending[cursor]
      cursor += 1
      await probeInvestigation(id)
    }
  }
  await Promise.all([worker(), worker()])
}

export function useAnalysisCache(controlIds: string[]): (controlId: string) => CacheEntry | undefined {
  const key = controlIds.slice().sort().join(',')
  const [, refresh] = useState(0)
  useEffect(() => subscribeCache(() => refresh((value) => value + 1)), [])
  useEffect(() => {
    if (!key) return
    void probeInvestigations(key.split(','))
  }, [key])
  return getCacheEntry
}
