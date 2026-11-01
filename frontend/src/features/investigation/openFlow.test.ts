import { describe, expect, it } from 'vitest'
import { investigationAction, phaseAfterProbe, showsGenerationLoader } from './openFlow'

describe('phaseAfterProbe', () => {
  it('shows the saved result after a cache hit', () => {
    expect(phaseAfterProbe('hit')).toBe('retrieving')
  })

  it('may submit a run only after a confirmed miss', () => {
    expect(phaseAfterProbe('miss')).toBe('starting')
  })

  it('keeps an unavailable check retryable and does not treat it as a miss', () => {
    expect(phaseAfterProbe('unavailable')).toBe('failed')
    expect(phaseAfterProbe('unavailable')).not.toBe('starting')
  })
})

describe('showsGenerationLoader', () => {
  it('waits until the service has accepted the run', () => {
    expect(showsGenerationLoader('checking')).toBe(false)
    expect(showsGenerationLoader('retrieving')).toBe(false)
    expect(showsGenerationLoader('starting')).toBe(false)
    expect(showsGenerationLoader('running')).toBe(true)
  })
})

describe('investigationAction', () => {
  it('blocks another submission while a run is executing', () => {
    expect(investigationAction({ executing: true, resumable: true }).kind).toBe('disabled')
  })

  it('resumes an existing operation instead of starting one', () => {
    expect(investigationAction({ executing: false, resumable: true })).toEqual({
      label: 'Resume this investigation',
      kind: 'resume',
    })
  })

  it('asks before starting a new investigation', () => {
    expect(investigationAction({ executing: false, resumable: false }).kind).toBe('confirm-new')
  })
})
