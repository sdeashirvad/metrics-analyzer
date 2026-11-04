import { describe, expect, it } from 'vitest'
import { nextBackoffMs } from './usePolling'

describe('nextBackoffMs', () => {
  it('backs off and then holds the last delay', () => {
    expect(nextBackoffMs(0)).toBe(2000)
    expect(nextBackoffMs(1)).toBe(4000)
    expect(nextBackoffMs(2)).toBe(8000)
    expect(nextBackoffMs(3)).toBe(15000)
    expect(nextBackoffMs(8)).toBe(15000)
  })
})
