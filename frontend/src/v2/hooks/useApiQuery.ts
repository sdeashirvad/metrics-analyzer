import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { ApiResult } from '../api/http'
import type { EnvelopeMeta } from '../api/types'

const FRESH_MS = 60_000

interface CacheEntry {
  result: ApiResult<unknown>
  at: number
}

const cache = new Map<string, CacheEntry>()

function freshHit(id: string): ApiResult<unknown> | undefined {
  const hit = cache.get(id)
  return hit && Date.now() - hit.at < FRESH_MS ? hit.result : undefined
}

const staleIds = new Set<string>()
const staleListeners = new Set<() => void>()

function setStale(id: string, value: boolean) {
  if (value === staleIds.has(id)) return
  if (value) staleIds.add(id)
  else staleIds.delete(id)
  staleListeners.forEach((listener) => listener())
}

function subscribeStale(listener: () => void) {
  staleListeners.add(listener)
  return () => staleListeners.delete(listener)
}

/** True while any panel on the page is showing the previous selection's data. */
export function useAnyStale(): boolean {
  return useSyncExternalStore(
    subscribeStale,
    () => staleIds.size > 0,
    () => false,
  )
}

export interface QueryState<T> {
  data: T | undefined
  meta: EnvelopeMeta | undefined
  error: Error | null
  status: 'loading' | 'success' | 'error'
  /** The data belongs to the previous request in the same `keep` group; the new one is still loading. */
  stale: boolean
  retry: () => void
}

export interface QueryOptions {
  /**
   * While a new key loads, keep showing the last result whose `keep` value is the same.
   * Use a value that only matches when the old data still describes the same thing
   * (for example the metric id), so a different entity never shows another's numbers.
   */
  keep?: string
  /** Report retained data to the page-wide "previous selection" notice. Off for refreshes of the same view. */
  announce?: boolean
}

export function useApiQuery<T>(scope: string, key: string, loader: () => Promise<ApiResult<T>>, options?: QueryOptions): QueryState<T> {
  const id = `${scope}|${key}`
  const keep = options?.keep
  const loaderRef = useRef(loader)
  loaderRef.current = loader
  const [state, setState] = useState<{ id: string; result?: ApiResult<T>; error: Error | null }>(() => ({
    id,
    result: freshHit(id) as ApiResult<T> | undefined,
    error: null,
  }))
  const [attempt, setAttempt] = useState(0)
  const last = useRef<{ keep: string; result: ApiResult<T> } | null>(null)

  useEffect(() => {
    let live = true
    const hit = freshHit(id)
    if (hit) {
      setState({ id, result: hit as ApiResult<T>, error: null })
      return () => {
        live = false
      }
    }
    setState({ id, error: null })
    loaderRef.current().then(
      (result) => {
        cache.set(id, { result, at: Date.now() })
        if (live) setState({ id, result, error: null })
      },
      (error: unknown) => {
        if (!live) return
        setState({ id, error: error instanceof Error ? error : new Error('Request failed') })
      },
    )
    return () => {
      live = false
    }
  }, [id, attempt])

  const retry = useCallback(() => {
    cache.delete(id)
    setAttempt((value) => value + 1)
  }, [id])

  const current = state.id === id ? state : { result: freshHit(id) as ApiResult<T> | undefined, error: null }
  if (current.result && keep !== undefined) last.current = { keep, result: current.result }
  const previous = !current.result && !current.error && keep !== undefined && last.current?.keep === keep ? last.current.result : undefined
  const stale = Boolean(previous)
  const announce = options?.announce ?? true

  useEffect(() => {
    if (!announce) return
    setStale(id, stale)
    return () => setStale(id, false)
  }, [id, stale, announce])

  const result = current.result ?? previous
  return {
    data: result?.data,
    meta: result?.meta,
    error: current.error,
    status: current.error ? 'error' : result ? 'success' : 'loading',
    stale,
    retry,
  }
}
