import { describe, expect, it } from 'vitest'
import { resolveEntry } from './resolveEntry'

describe('resolveEntry', () => {
  it('loads the legacy app on its mount', () => {
    expect(resolveEntry('/legacy')).toBe('legacy')
    expect(resolveEntry('/legacy/')).toBe('legacy')
    expect(resolveEntry('/legacy/metrics/DQ-001')).toBe('legacy')
    expect(resolveEntry('/legacy/architecture')).toBe('legacy')
  })

  it('redirects the old top-level routes', () => {
    expect(resolveEntry('/dashboard')).toBe('redirect')
    expect(resolveEntry('/dashboard/')).toBe('redirect')
    expect(resolveEntry('/overview')).toBe('redirect')
    expect(resolveEntry('/metrics')).toBe('redirect')
    expect(resolveEntry('/metrics/DQ-001')).toBe('redirect')
    expect(resolveEntry('/investigations/DQ-001')).toBe('redirect')
    expect(resolveEntry('/glossary')).toBe('redirect')
  })

  it('keeps V2 routes, including architecture', () => {
    expect(resolveEntry('/')).toBe('v2')
    expect(resolveEntry('/architecture')).toBe('v2')
    expect(resolveEntry('/register')).toBe('v2')
    expect(resolveEntry('/register/M325402')).toBe('v2')
    expect(resolveEntry('/investigate/metrics/M325402')).toBe('v2')
    expect(resolveEntry('/investigate/applications/EON611195')).toBe('v2')
    expect(resolveEntry('/agent')).toBe('v2')
    expect(resolveEntry('/agent/analysis')).toBe('v2')
    expect(resolveEntry('/definitions')).toBe('v2')
    expect(resolveEntry('/legacyfoo')).toBe('v2')
    expect(resolveEntry('/dashboardx')).toBe('v2')
  })
})
