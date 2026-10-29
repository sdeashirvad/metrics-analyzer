import { useCallback, useEffect, useRef, useState } from 'react'

interface Entry {
  data?: unknown
  promise?: Promise<unknown>
}

const cache = new Map<string, Entry>()

export type QueryStatus = 'loading' | 'success' | 'error'

export interface QueryState<T> {
  data: T | undefined
  error: Error | null
  status: QueryStatus
  refreshing: boolean
  retry: () => void
}

interface Settled {
  id: string
  scope: string
  data: unknown
  error: Error | null
}

/**
 * Cached loader. `scope` names the resource a component shows; while a new `key`
 * loads in the same scope the previous data stays visible. Data never crosses scopes.
 */
export function useQuery<T>(scope: string, key: string, loader: () => Promise<T>): QueryState<T> {
  const id = `${scope}|${key}`
  const loaderRef = useRef(loader)
  const [settled, setSettled] = useState<Settled>(() => ({
    id,
    scope,
    data: cache.get(id)?.data,
    error: null,
  }))
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    loaderRef.current = loader
  })

  useEffect(() => {
    let live = true
    const hit = cache.get(id)
    if (hit && 'data' in hit) {
      setSettled({ id, scope, data: hit.data, error: null })
      return
    }
    let promise = hit?.promise
    if (!promise) {
      promise = loaderRef.current()
      cache.set(id, { promise })
      promise.then(
        (data) => cache.set(id, { data }),
        () => cache.delete(id),
      )
    }
    promise.then(
      (data) => {
        if (live) setSettled({ id, scope, data, error: null })
      },
      (err: unknown) => {
        if (!live) return
        setSettled((current) => ({
          id,
          scope,
          data: current.scope === scope ? current.data : undefined,
          error: err instanceof Error ? err : new Error('Request failed'),
        }))
      },
    )
    return () => {
      live = false
    }
  }, [id, scope, attempt])

  const retry = useCallback(() => {
    cache.delete(id)
    setAttempt((value) => value + 1)
  }, [id])

  const cached = cache.get(id)
  const current = settled.id === id
  let data: unknown
  if (current) data = settled.data
  else if (cached && 'data' in cached) data = cached.data
  else if (settled.scope === scope) data = settled.data
  const error = current ? settled.error : null
  const fresh = current ? settled.error == null && settled.data !== undefined : Boolean(cached && 'data' in cached)
  const status: QueryStatus = error && data === undefined ? 'error' : data === undefined ? 'loading' : 'success'

  return {
    data: data as T | undefined,
    error,
    status: error ? 'error' : status,
    refreshing: data !== undefined && !fresh && !error,
    retry,
  }
}
