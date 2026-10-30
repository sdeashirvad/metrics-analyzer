import type { RagStatus } from '../../backend/contracts/types'

interface SparkPoint {
  value: number
  status: RagStatus
}

export function Sparkline({ points, label, width = 96, height = 28 }: { points: SparkPoint[]; label: string; width?: number; height?: number }) {
  if (points.length < 2) return <span className="spark spark-empty" aria-hidden="true" />
  const values = points.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const pad = 3
  const x = (index: number) => pad + (index / (points.length - 1)) * (width - pad * 2)
  const y = (value: number) => pad + ((max - value) / span) * (height - pad * 2)
  const d = points.map((point, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)} ${y(point.value).toFixed(1)}`).join(' ')
  const last = points[points.length - 1]
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <path d={d} className="spark-line" />
      <circle cx={x(points.length - 1)} cy={y(last.value)} r="2.6" className={`spark-dot dot-${last.status}`} />
    </svg>
  )
}
