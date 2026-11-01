import { useEffect, useRef, useState } from 'react'
import type { AnalysisOperation, DqInvestigation } from '../../backend/contracts/types'
import { ApiError } from '../../backend/services/errors'
import { getCachedDqInvestigation, pollDqInvestigation, startDqInvestigation } from '../../backend/services/httpApi'
import { markInvestigationCached, markInvestigationRunning, rememberCacheHint } from '../../state/analysisState'
import { phaseAfterProbe, type CacheProbeOutcome } from './openFlow'
import { estimateFor, recordSample, type EtaEstimate } from '../../state/etaStore'

export type InvestigationPhase = 'checking' | 'retrieving' | 'starting' | 'running' | 'completed' | 'cached' | 'failed'

const STORAGE_PREFIX = 'ma-dq-run:'
const POLL_MS = 2500

function storageKey(metricId: string): string {
  return `${STORAGE_PREFIX}${metricId}`
}

function readRun(metricId: string): string | null {
  try {
    return sessionStorage.getItem(storageKey(metricId))
  } catch {
    return null
  }
}

function writeRun(metricId: string, runId: string) {
  try {
    sessionStorage.setItem(storageKey(metricId), runId)
  } catch {
    /* The run id is also stored in Snowflake. */
  }
}

function clearRun(metricId: string) {
  try {
    sessionStorage.removeItem(storageKey(metricId))
  } catch {
    /* Ignore storage failures. */
  }
}

function isInvestigation(value: DqInvestigation | AnalysisOperation): value is DqInvestigation {
  return 'kind' in value && value.kind === 'data_quality'
}

export function useDqInvestigation(metricId: string, enabled: boolean) {
  const [phase, setPhase] = useState<InvestigationPhase>('checking')
  const [pack, setPack] = useState<DqInvestigation | null>(null)
  const [preview, setPreview] = useState<DqInvestigation | null>(null)
  const [message, setMessage] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [mode, setMode] = useState<'auto' | 'force' | 'check'>('auto')
  const [startedAt, setStartedAt] = useState(() => Date.now())
  const [estimate, setEstimate] = useState<EtaEstimate | null>(null)
  const forceGate = useRef(false)

  useEffect(() => {
    if (!enabled) return
    let stop = false
    let timer = 0

    function sleep(ms: number) {
      return new Promise<void>((resolve) => {
        timer = window.setTimeout(resolve, ms)
      })
    }

    async function watch(runId: string, record: { enabled: boolean; startedAt: number }) {
      let failures = 0
      const started = Date.now()
      while (!stop) {
        if (Date.now() - started > 20 * 60 * 1000) {
          setPhase('failed')
          setMessage('This page stopped checking. Check again to resume the same investigation. That does not start another one.')
          return
        }
        let status: AnalysisOperation
        try {
          status = await pollDqInvestigation(metricId, runId)
          failures = 0
        } catch {
          failures += 1
          if (failures >= 3) {
            setPhase('failed')
            setMessage('The status check failed. Check again to resume the same investigation. That does not start another one.')
            return
          }
          await sleep(POLL_MS)
          continue
        }
        if (stop) return
        if (status.status === 'RUNNING') {
          setPhase('running')
          await sleep(POLL_MS)
          continue
        }
        if (status.status === 'FAILED') {
          clearRun(metricId)
          markInvestigationRunning(metricId, false)
          setPhase('failed')
          setMessage(status.message || 'The investigation did not finish. Run it again to start a new one.')
          try {
            const previous = await getCachedDqInvestigation(metricId)
            if (!stop && previous) setPreview(previous)
          } catch {
            /* The failure message remains. */
          }
          return
        }
        if (status.result) {
          clearRun(metricId)
          if (record.enabled) recordSample('INVESTIGATION', (Date.now() - record.startedAt) / 1000)
          markInvestigationCached(metricId)
          setPack(status.result)
          setPreview(null)
          setPhase('completed')
          return
        }
        setPhase('failed')
        setMessage('The investigation finished without a readable result. Run it again.')
        return
      }
    }

    async function showCached(found: DqInvestigation) {
      markInvestigationCached(metricId)
      setPack(found)
      setPreview(null)
      setPhase('cached')
    }

    async function begin(force: boolean) {
      setEstimate(estimateFor('INVESTIGATION'))
      setStartedAt(Date.now())
      setPhase('starting')
      markInvestigationRunning(metricId, true)
      const started = await startDqInvestigation(metricId, force)
      if (stop) return
      if (isInvestigation(started)) {
        markInvestigationRunning(metricId, false)
        if (started.cached) await showCached(started)
        else {
          markInvestigationCached(metricId)
          setPack(started)
          setPhase('completed')
        }
        return
      }
      if (started.status === 'COMPLETED' && started.result) {
        markInvestigationRunning(metricId, false)
        markInvestigationCached(metricId)
        setPack(started.result)
        setPhase('completed')
        return
      }
      if (started.status !== 'RUNNING' || !started.runId) throw new ApiError('UPSTREAM', 'The investigation did not start.', 502)
      writeRun(metricId, started.runId)
      const origin = Date.now()
      setStartedAt(origin)
      setPhase('running')
      await watch(started.runId, { enabled: true, startedAt: origin })
    }

    async function run() {
      setMessage('')
      if (mode === 'auto') setPack(null)
      try {
        if (mode === 'check') {
          const saved = readRun(metricId)
          if (!saved) {
            setPhase('failed')
            setMessage('That investigation is no longer running. Open it again to see the saved result.')
            return
          }
          setPhase('running')
          setStartedAt(Date.now())
          setEstimate(estimateFor('INVESTIGATION'))
          await watch(saved, { enabled: false, startedAt: Date.now() })
          return
        }
        if (mode !== 'force') {
          const saved = readRun(metricId)
          if (saved) {
            setPhase('running')
            setStartedAt(Date.now())
            setEstimate(estimateFor('INVESTIGATION'))
            await watch(saved, { enabled: false, startedAt: Date.now() })
            return
          }
          setPhase('checking')
          let found: DqInvestigation | null = null
          let outcome: CacheProbeOutcome
          try {
            found = await getCachedDqInvestigation(metricId)
            outcome = found ? 'hit' : 'miss'
          } catch {
            outcome = 'unavailable'
          }
          if (stop) return
          const next = phaseAfterProbe(outcome)
          if (next === 'failed') {
            setPhase('failed')
            setMessage('The saved investigation could not be checked. Try again. This does not start a new one.')
            return
          }
          if (next === 'retrieving' && found) {
            setPhase('retrieving')
            await sleep(400)
            if (stop) return
            await showCached(found)
            return
          }
          rememberCacheHint(metricId, false)
        }
        await begin(mode === 'force')
      } catch (error) {
        if (stop) return
        markInvestigationRunning(metricId, false)
        setPhase('failed')
        setMessage(error instanceof Error ? error.message : 'The investigation request failed.')
      }
    }

    const ownsForce = forceGate.current
    void run().finally(() => {
      if (ownsForce && !stop) forceGate.current = false
    })
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
  }, [attempt, enabled, metricId, mode])

  return {
    phase,
    pack,
    preview,
    message,
    startedAt,
    estimate,
    canResume: phase === 'failed' && Boolean(readRun(metricId)),
    runAgain() {
      if (forceGate.current || readRun(metricId)) {
        if (readRun(metricId)) {
          setMode('check')
          setAttempt((value) => value + 1)
        }
        return
      }
      forceGate.current = true
      setMode('force')
      setAttempt((value) => value + 1)
    },
    checkAgain() {
      setMode('check')
      setAttempt((value) => value + 1)
    },
    retryOpen() {
      setMode('auto')
      setAttempt((value) => value + 1)
    },
  }
}
