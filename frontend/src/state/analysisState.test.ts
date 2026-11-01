import { describe, expect, it } from 'vitest'
import { getCacheEntry, markInvestigationCached, markInvestigationRunning } from './analysisState'

describe('investigation cache state', () => {
  it('does not claim a cache hit before one is recorded', () => {
    expect(getCacheEntry('DQ-099')).toBeUndefined()
  })

  it('marks a control cached only after a completed result is recorded', () => {
    markInvestigationCached('DQ-099')
    expect(getCacheEntry('DQ-099')?.kind).toBe('cached')
    expect(getCacheEntry('DQ-099')?.running).toBe(false)
  })

  it('keeps a cached control cached while a new run is in progress', () => {
    markInvestigationCached('DQ-098')
    markInvestigationRunning('DQ-098', true)
    expect(getCacheEntry('DQ-098')?.kind).toBe('cached')
    expect(getCacheEntry('DQ-098')?.running).toBe(true)
  })
})
