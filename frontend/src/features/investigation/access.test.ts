import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CacheEntry } from '../../state/analysisState'
import { accessLabel, actionCopy, investigationAccess, primaryAction } from './access'

const cached: CacheEntry = { kind: 'cached', running: false, at: 1 }
const missing: CacheEntry = { kind: 'not_cached', running: false, at: 1 }
const unknown: CacheEntry = { kind: 'unknown', running: false, at: 1 }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('investigationAccess', () => {
  it('treats a seeded Technology Risk metric as ready and an unseeded one as unavailable', () => {
    expect(investigationAccess({ family: 'technology_risk', id: 'M01', investigationAvailable: true })).toBe('ready')
    expect(investigationAccess({ family: 'technology_risk', id: 'M02', investigationAvailable: false }, cached)).toBe('unavailable')
  })

  it('blocks a Data Quality control that has no snapshot', () => {
    expect(investigationAccess({ family: 'data_quality', id: 'DQ-1', investigationAvailable: true, snapshotUnavailable: true }, missing)).toBe('unavailable')
  })

  it('waits while the Data Quality probe has not answered', () => {
    expect(investigationAccess({ family: 'data_quality', id: 'DQ-1', investigationAvailable: false })).toBe('checking')
    expect(investigationAccess({ family: 'data_quality', id: 'DQ-1', investigationAvailable: false }, unknown)).toBe('checking')
  })

  it('separates a saved result from a control that would start a live run', () => {
    const subject = { family: 'data_quality' as const, id: 'DQ-1', investigationAvailable: false }
    expect(investigationAccess(subject, cached)).toBe('ready')
    expect(investigationAccess(subject, missing)).toBe('not_run')
  })

  it('reports a run in progress ahead of the cache result', () => {
    const subject = { family: 'data_quality' as const, id: 'DQ-1', investigationAvailable: true }
    expect(investigationAccess(subject, { ...cached, running: true })).toBe('running')
  })

  it('reads a saved run id from this browser', () => {
    const store = new Map<string, string>([['ma-dq-run:DQ-9', 'run-1']])
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => store.get(key) ?? null,
    })
    expect(investigationAccess({ family: 'data_quality', id: 'DQ-9', investigationAvailable: false }, missing)).toBe('running')
    expect(investigationAccess({ family: 'technology_risk', id: 'M09', investigationAvailable: false })).toBe('unavailable')
  })
})

describe('primaryAction', () => {
  it('offers Open, Run, or View progress, and nothing when there is no investigation', () => {
    expect(primaryAction('ready')).toEqual({ label: 'Open', variant: 'primary' })
    expect(primaryAction('not_run')).toEqual({ label: 'Run', variant: 'outline' })
    expect(primaryAction('running')).toEqual({ label: 'View progress', variant: 'primary' })
    expect(primaryAction('unavailable')).toBeNull()
    expect(primaryAction('checking')).toBeNull()
  })

  it('uses the longer labels on cards and the detail page', () => {
    expect(actionCopy('ready', 'long')?.label).toBe('Open investigation')
    expect(actionCopy('not_run', 'long')?.label).toBe('Run investigation')
    expect(actionCopy('running', 'long')?.label).toBe('View progress')
  })

  it('names every state for the register column and the export', () => {
    expect(accessLabel('ready')).toBe('Ready')
    expect(accessLabel('not_run')).toBe('Not run')
    expect(accessLabel('running')).toBe('Running')
    expect(accessLabel('unavailable')).toBe('Not available')
    expect(accessLabel('checking')).toBe('Checking')
  })
})
