import { describe, expect, it } from 'vitest'
import { barLength, lineSegments, yPosition } from './scale'

describe('chart scale', () => {
  it('breaks a line on a missing value instead of treating it as zero', () => {
    const y = yPosition(null, 0, 1, 100, 8)
    expect(y).toBeNull()
    const segments = lineSegments([
      { x: 0, y: 10 },
      { x: 20, y: null },
      { x: 40, y: 30 },
    ])
    expect(segments).toEqual(['0,10', '40,30'])
    expect(segments.join(' ')).not.toContain(',0')
  })

  it('gives a counted zero no length and leaves a missing value undrawn', () => {
    expect(barLength(0, 10, 100)).toBe(0)
    expect(barLength(null, 10, 100)).toBeNull()
    expect(barLength(5, 10, 100)).toBe(50)
  })
})
