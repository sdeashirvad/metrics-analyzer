import { afterEach, describe, expect, it } from 'vitest'
import { estimateFromSamples, quantile, readSamples, recordSample } from './etaStore'

describe('estimateFromSamples', () => {
  it('makes no promise before three samples', () => {
    expect(estimateFromSamples([])).toBeNull()
    expect(estimateFromSamples([15, 20])).toBeNull()
  })

  it('uses the middle half and widens it to at least a quarter either side', () => {
    const estimate = estimateFromSamples([10, 15, 20, 25])
    expect(estimate).not.toBeNull()
    if (!estimate) return
    expect(estimate.label.startsWith('Usually about ')).toBe(true)
    expect(estimate.low).toBeLessThan(estimate.high)
    expect(estimate.high - estimate.low).toBeGreaterThanOrEqual(5)
  })

  it('clamps a far outlier once five samples exist', () => {
    const estimate = estimateFromSamples([15, 16, 17, 18, 400])
    expect(estimate).not.toBeNull()
    if (!estimate) return
    expect(estimate.high).toBeLessThan(60)
  })

  it('rounds the displayed range to five seconds', () => {
    const estimate = estimateFromSamples([14, 16, 18])
    expect(estimate).not.toBeNull()
    if (!estimate) return
    expect(estimate.low % 5).toBe(0)
    expect(estimate.high % 5).toBe(0)
  })
})

describe('recordSample', () => {
  const memory = new Map<string, string>()
  const storage = {
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => {
      memory.set(key, value)
    },
    removeItem: (key: string) => {
      memory.delete(key)
    },
    clear: () => memory.clear(),
    key: () => null,
    get length() {
      return memory.size
    },
  }

  afterEach(() => memory.clear())

  it('ignores non-positive and implausibly long samples', () => {
    Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true })
    recordSample('INVESTIGATION', 0)
    recordSample('INVESTIGATION', -4)
    recordSample('INVESTIGATION', 20 * 60 + 1)
    recordSample('INVESTIGATION', Number.NaN)
    expect(readSamples('INVESTIGATION')).toEqual([])
    recordSample('INVESTIGATION', 15)
    expect(readSamples('INVESTIGATION')).toEqual([15])
  })

  it('ignores a corrupt stored value', () => {
    Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true })
    storage.setItem('ma-eta-v1', '{')
    expect(readSamples('INVESTIGATION')).toEqual([])
  })
})

describe('quantile', () => {
  it('reads the ends and the middle', () => {
    expect(quantile([10, 20, 30], 0)).toBe(10)
    expect(quantile([10, 20, 30], 1)).toBe(30)
    expect(quantile([10, 20, 30], 0.5)).toBe(20)
  })
})
