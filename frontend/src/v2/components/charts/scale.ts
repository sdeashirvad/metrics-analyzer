export interface ChartPoint {
  x: number
  y: number | null
}

export function domain(values: Array<number | null>): { min: number; max: number } {
  const present = values.filter((value): value is number => value != null)
  if (!present.length) return { min: 0, max: 1 }
  return { min: Math.min(...present), max: Math.max(...present) }
}

export function yPosition(value: number | null, min: number, max: number, height: number, pad: number): number | null {
  if (value == null) return null
  const span = max - min || 1
  return pad + (1 - (value - min) / span) * (height - pad * 2)
}

export function lineSegments(points: ChartPoint[]): string[] {
  const segments: string[] = []
  let current: string[] = []
  for (const point of points) {
    if (point.y == null) {
      if (current.length) segments.push(current.join(' '))
      current = []
      continue
    }
    current.push(`${round(point.x)},${round(point.y)}`)
  }
  if (current.length) segments.push(current.join(' '))
  return segments
}

/** Null is not drawn. A counted zero is a zero-length bar. */
export function barLength(value: number | null, max: number, width: number): number | null {
  if (value == null) return null
  if (max <= 0) return 0
  return (value / max) * width
}

function round(value: number): number {
  return Math.round(value * 100) / 100
}
