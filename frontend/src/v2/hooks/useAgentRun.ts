import { useCallback, useEffect, useRef, useState } from 'react'
import { getRun, retryRun } from '../api/agents'
import { ApiError } from '../api/http'
import type { Run } from '../api/types'
import { nextBackoffMs, POLL_GIVE_UP_MS } from './usePolling'

export interface AgentRunState {
  run: Run | null
  error: Error | null
  connectionLost: boolean
  waiting: boolean
  stopped: boolean
  stopWaiting: () => void
  retry: () => Promise<void>
}

export function useAgentRun(runId: string | null, onTerminal?: (run: Run) => void): AgentRunState {
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [connectionLost, setConnectionLost] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [stopped, setStopped] = useState(false)
  const [overrideId, setOverrideId] = useState<string | null>(null)
  const activeId = overrideId ?? runId
  const onTerminalRef = useRef(onTerminal)
  onTerminalRef.current = onTerminal

  useEffect(() => {
    setOverrideId(null)
    setStopped(false)
    setConnectionLost(false)
    setRun(null)
    setError(null)
  }, [runId])

  useEffect(() => {
    if (!activeId || stopped) {
      setWaiting(false)
      return
    }
    let live = true
    let timer = 0
    let failures = 0
    let failingSince: number | null = null
    let pendingVisible: (() => void) | null = null

    const clearWait = () => {
      window.clearTimeout(timer)
      if (pendingVisible) {
        document.removeEventListener('visibilitychange', pendingVisible)
        pendingVisible = null
      }
    }

    const schedule = (ms: number, poll: () => void) => {
      clearWait()
      const fire = () => {
        if (!live) return
        if (document.visibilityState === 'hidden') {
          pendingVisible = () => {
            if (document.visibilityState !== 'visible') return
            clearWait()
            poll()
          }
          document.addEventListener('visibilitychange', pendingVisible)
          return
        }
        poll()
      }
      timer = window.setTimeout(fire, ms)
    }

    const poll = () => {
      if (!live || !activeId) return
      setWaiting(true)
      getRun(activeId).then(
        (result) => {
          if (!live) return
          failures = 0
          failingSince = null
          setRun(result.data)
          setError(null)
          setWaiting(result.data.status === 'RUNNING')
          if (result.data.status !== 'RUNNING' || result.data.pollAfterMs == null) {
            onTerminalRef.current?.(result.data)
            return
          }
          schedule(Math.max(0, result.data.pollAfterMs), poll)
        },
        (err: unknown) => {
          if (!live) return
          const apiError = err instanceof Error ? err : new Error('Request failed')
          if (apiError instanceof ApiError && apiError.status === 404) {
            setError(apiError)
            setWaiting(false)
            return
          }
          failures += 1
          failingSince ??= Date.now()
          if (Date.now() - failingSince >= POLL_GIVE_UP_MS) {
            setConnectionLost(true)
            setError(apiError)
            setWaiting(false)
            return
          }
          setError(apiError)
          schedule(nextBackoffMs(failures - 1), poll)
        },
      )
    }

    poll()
    return () => {
      live = false
      clearWait()
    }
  }, [activeId, stopped])

  const stopWaiting = useCallback(() => {
    setStopped(true)
    setWaiting(false)
  }, [])

  const retry = useCallback(async () => {
    if (!activeId) return
    const result = await retryRun(activeId)
    setOverrideId(result.data.run.runId)
    setStopped(false)
    setConnectionLost(false)
    setError(null)
  }, [activeId])

  return { run, error, connectionLost, waiting, stopped, stopWaiting, retry }
}
