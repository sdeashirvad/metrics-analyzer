import type { MetricFamily } from '../../backend/contracts/types'
import type { CacheEntry } from '../../state/analysisState'

export type InvestigationAccess = 'ready' | 'not_run' | 'running' | 'unavailable' | 'checking'

export interface AccessSubject {
  family: MetricFamily
  id: string
  investigationAvailable: boolean
  snapshotUnavailable?: boolean
}

const RUN_PREFIX = 'ma-dq-run:'

export function investigationAccess(item: AccessSubject, cache?: CacheEntry): InvestigationAccess {
  if (item.family === 'technology_risk') return item.investigationAvailable ? 'ready' : 'unavailable'
  if (item.snapshotUnavailable) return 'unavailable'
  if (cache?.running || hasSavedRun(item.id)) return 'running'
  if (!cache || cache.kind === 'unknown') return 'checking'
  if (cache.kind === 'cached') return 'ready'
  return 'not_run'
}

export function accessLabel(access: InvestigationAccess): string {
  if (access === 'ready') return 'Ready'
  if (access === 'not_run') return 'Not run'
  if (access === 'running') return 'Running'
  if (access === 'unavailable') return 'Not available'
  return 'Checking'
}

export function accessRank(access: InvestigationAccess): number {
  if (access === 'ready') return 0
  if (access === 'running') return 1
  if (access === 'not_run') return 2
  if (access === 'checking') return 3
  return 4
}

/** Sub-line under "Not run". `label` is the stored timing phrase, when one exists. */
export function liveRunNote(label: string | null): string {
  if (!label) return 'Live run'
  return `${label.charAt(0).toLowerCase()}${label.slice(1)} · live run`
}

export function primaryAction(access: InvestigationAccess): { label: 'Open' | 'Run' | 'View progress'; variant: 'primary' | 'outline' } | null {
  if (access === 'ready') return { label: 'Open', variant: 'primary' }
  if (access === 'not_run') return { label: 'Run', variant: 'outline' }
  if (access === 'running') return { label: 'View progress', variant: 'primary' }
  return null
}

export function actionCopy(
  access: InvestigationAccess,
  length: 'short' | 'long',
): { label: string; variant: 'primary' | 'outline' } | null {
  const action = primaryAction(access)
  if (!action || length === 'short') return action
  if (access === 'ready') return { label: 'Open investigation', variant: 'primary' }
  if (access === 'not_run') return { label: 'Run investigation', variant: 'outline' }
  return action
}

function hasSavedRun(id: string): boolean {
  if (typeof sessionStorage === 'undefined') return false
  try {
    return Boolean(sessionStorage.getItem(`${RUN_PREFIX}${id}`))
  } catch {
    return false
  }
}
