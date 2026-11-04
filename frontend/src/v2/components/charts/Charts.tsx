import { useEffect, useRef, useState, type ReactNode } from 'react'
import { formatInt, formatMonth } from '../../format'
import { barLength, domain, lineSegments, yPosition } from './scale'

export function Sparkline({ values }: { values: Array<number | null> }) {
  const width = 96
  const height = 26
  const pad = 3
  const { min, max } = domain(values)
  const step = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0
  const segments = lineSegments(values.map((value, index) => ({ x: pad + index * step, y: yPosition(value, min, max, height, pad) })))
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      {segments.map((points) => (
        <polyline key={points} points={points} fill="none" stroke="#2357c5" strokeWidth="1.8" />
      ))}
    </svg>
  )
}

export function LineChart({
  points,
  onSelect,
}: {
  points: Array<{ label: string; value: number | null; unobserved?: boolean }>
  onSelect?: (index: number) => void
}) {
  // Draw at the real container width so a full-width card uses its full width.
  const holder = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)
  useEffect(() => {
    const node = holder.current
    if (!node) return undefined
    const measure = () => setWidth(Math.max(320, Math.round(node.getBoundingClientRect().width)))
    measure()
    if (typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  const height = 160
  const pad = 28
  const { min, max } = domain(points.map((point) => point.value))
  const step = points.length > 1 ? (width - pad * 2) / (points.length - 1) : 0
  const coords = points.map((point, index) => ({
    ...point,
    x: pad + index * step,
    y: point.unobserved ? null : yPosition(point.value, min, max, height - 18, pad),
  }))
  const segments = lineSegments(coords)
  const labelled = coords.filter((_, index) => index === 0 || index === coords.length - 1 || index === Math.floor(coords.length / 2))
  const axis = labelled.filter((point, index, list) => list.findIndex((item) => item.label === point.label) === index)
  return (
    <div className="line-chart" ref={holder}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <title>Trend. Missing points are not observed or not available.</title>
        {[0, 1, 2].map((row) => (
          <line key={row} x1={pad} x2={width - 8} y1={pad + row * 40} y2={pad + row * 40} stroke="#e8edf2" />
        ))}
        {segments.map((segment) => (
          <polyline key={segment} points={segment} fill="none" stroke="#2357c5" strokeWidth="2.4" />
        ))}
        {coords.map((point) =>
          point.y == null ? null : (
            <circle
              key={point.label}
              cx={point.x}
              cy={point.y}
              r="4.5"
              fill="#2357c5"
              className={onSelect ? 'chart-hit' : undefined}
              onClick={onSelect ? () => onSelect(coords.indexOf(point)) : undefined}
            >
              <title>{point.unobserved ? `${point.label}. Not observed` : point.label}</title>
            </circle>
          ),
        )}
      </svg>
      <div className="line-axis">
        {axis.map((point) => (
          <span key={point.label}>{point.unobserved ? 'Not observed' : point.label}</span>
        ))}
      </div>
    </div>
  )
}

const SEGMENT: Record<string, string> = {
  Compliant: 'sg',
  Non_Compliant: 'sr',
  Pending: 'sa',
  Not_Applicable: 'sn',
}

export function StackedBar({
  segments,
  onSelect,
}: {
  segments: Array<{ key: string; label: string; value: number }>
  onSelect?: (key: string) => void
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0)
  if (total <= 0) return <p className="fine">No rows in this scope.</p>
  return (
    <div className="stack-bar" role="img" aria-label="Distribution">
      {segments.map((segment) => (
        onSelect ? (
          <button
            key={segment.key}
            type="button"
            className={`${SEGMENT[segment.key] ?? 'sn'} chart-hit`}
            style={{ width: `${(segment.value / total) * 100}%` }}
            title={`${segment.label}: ${formatInt(segment.value)}`}
            onClick={() => onSelect(segment.key)}
          />
        ) : (
          <span key={segment.key} className={SEGMENT[segment.key] ?? 'sn'} style={{ width: `${(segment.value / total) * 100}%` }} title={`${segment.label}: ${formatInt(segment.value)}`} />
        )
      ))}
    </div>
  )
}

export function MonthMix({ columns }: { columns: Array<{ label: string; segments: Array<{ key: string; value: number }> }> }) {
  const max = Math.max(1, ...columns.map((column) => column.segments.reduce((sum, segment) => sum + segment.value, 0)))
  if (!columns.length) return <p className="fine">No observed months in this scope.</p>
  return (
    <div className="month-mix-scroll">
      <div className="month-mix" role="img" aria-label="Status mix by month, metric rows">
        {columns.map((column) => (
          <div className="month-mix-col" key={column.label}>
            <div className="month-mix-stack">
              {column.segments.map((segment) => (
                <span
                  key={segment.key}
                  className={SEGMENT[segment.key] ?? 'sn'}
                  style={{ height: `${(segment.value / max) * 100}%` }}
                  title={`${segment.key}: ${formatInt(segment.value)}`}
                />
              ))}
            </div>
            <span className="fine">{column.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function BarList({
  items,
  onSelect,
}: {
  items: Array<{ key: string; label: string; value: number | null; note: ReactNode }>
  onSelect?: (key: string) => void
}) {
  const max = Math.max(0, ...items.map((item) => item.value ?? 0))
  return (
    <div>
      {items.map((item) => {
        const length = barLength(item.value, max, 100)
        return (
          onSelect ? (
            <button type="button" className="hbar chart-hit" key={item.key} title={`${item.label}: ${item.value ?? 'not available'}`} onClick={() => onSelect(item.key)}>
              <span>{item.label}</span>
              <div className="bar-track">{length == null ? null : <div className="bar-fill" style={{ width: `${length}%` }} />}</div>
              <span className="num">{item.note}</span>
            </button>
          ) : (
            <div className="hbar" key={item.key} title={`${item.label}: ${item.value ?? 'not available'}`}>
              <span>{item.label}</span>
              <div className="bar-track">{length == null ? null : <div className="bar-fill" style={{ width: `${length}%` }} />}</div>
              <span className="num">{item.note}</span>
            </div>
          )
        )
      })}
    </div>
  )
}

export function StatusStrip({
  cells,
}: {
  cells: Array<{ month: string; observed: boolean; tone?: string; text?: string }>
}) {
  return (
    <div className="stack">
      <div className="tl" role="img" aria-label="Month history. Hatched months are not observed.">
        {cells.map((cell) => (
          <div
            key={cell.month}
            className={cell.observed ? undefined : 'is-unobserved'}
            title={cell.observed ? cell.text : 'Not observed'}
            style={cell.observed && cell.tone ? { background: cell.tone } : undefined}
          />
        ))}
      </div>
      <div className="tl-lab">
        {cells.map((cell) => (
          <span key={cell.month}>{formatMonth(cell.month).slice(0, 3)}</span>
        ))}
      </div>
      <ul className="list">
        {cells.filter((cell) => !cell.observed).map((cell) => (
          <li key={cell.month}>
            <span className="grow">{formatMonth(cell.month)}</span>
            <span>Not observed</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
