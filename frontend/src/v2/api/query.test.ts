import { describe, expect, it } from 'vitest'
import { appendQuery, readScope, scopeParams } from './query'

describe('query strings', () => {
  it('repeats array filters and omits empty values', () => {
    const text = appendQuery('/portfolio/metrics', {
      month: '2025-11-30',
      q: 'M3254',
      l1: ['Super_Division_04', 'Super_Division_02'],
      tier: [1, 4],
      empty: '',
      missing: undefined,
    })
    expect(text).toBe('/portfolio/metrics?month=2025-11-30&q=M3254&l1=Super_Division_04&l1=Super_Division_02&tier=1&tier=4')
  })

  it('reads scope filters back from a URL', () => {
    const params = new URLSearchParams('month=2025-11-30&orgTree=BU&l1=A&l1=B&tier=2&ma=Y')
    expect(readScope(params)).toEqual({
      month: '2025-11-30',
      orgTree: 'BU',
      l1: ['A', 'B'],
      tier: [2],
      ma: 'Y',
    })
    expect(scopeParams(readScope(params)).l1).toEqual(['A', 'B'])
  })
})
