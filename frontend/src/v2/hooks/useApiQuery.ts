import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiResult } from '../api/http'
import type { EnvelopeMeta } from '../api/types'

const FRESH_MS = 60_000

interface CacheEntry {
  result: ApiResult<unknown>
  at: number
}

const cache = new Map<string, CacheEntry>()

export interface QueryState<T> {
  data: T | undefined
  meta: EnvelopeMeta | undefined
  error: Error | null
  status: 'loading' | 'success' | 'error'
  retry: () => void
}

export function useApiQuery<T>(scope: string, key: string, loader: () => Promise<ApiResult<T>>): QueryState<T> {
  const id = `${scope}|${key}`
  const loaderRef = useRef(loader)
  loaderRef.current = loader
  const [state, setState] = useState<{ id: string; result?: ApiResult<T>; error: Error | null }>({ id, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let live = true
    const hit = cache.get(id)
    if (hit && Date.now() - hit.at < FRESH_MS) {
      setState({ id, result: hit.result as ApiResult<T>, error: null })
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

  const current = state.id === id ? state : { result: undefined, error: null }
  return {
    data: current.result?.data,
    meta: current.result?.meta,
    error: current.error,
    status: current.error ? 'error' : current.result ? 'success' : 'loading',
    retry,
  }
}
