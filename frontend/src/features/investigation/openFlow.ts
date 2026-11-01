import type { InvestigationPhase } from './useDqInvestigation'

export type CacheProbeOutcome = 'hit' | 'miss' | 'unavailable'

/** What the screen does after the read-only cache check. A miss is the only path that may submit a run. */
export function phaseAfterProbe(outcome: CacheProbeOutcome): Extract<InvestigationPhase, 'retrieving' | 'starting' | 'failed'> {
  if (outcome === 'hit') return 'retrieving'
  if (outcome === 'miss') return 'starting'
  return 'failed'
}

/** The generation sequence is shown only after a run has been accepted and is still in progress. */
export function showsGenerationLoader(phase: InvestigationPhase): boolean {
  return phase === 'running'
}

export function investigationAction(input: { executing: boolean; resumable: boolean }): {
  label: string
  kind: 'disabled' | 'resume' | 'confirm-new'
} {
  if (input.executing) return { label: 'Investigation running', kind: 'disabled' }
  if (input.resumable) return { label: 'Resume this investigation', kind: 'resume' }
  return { label: 'Run again', kind: 'confirm-new' }
}
