import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import type { Frequency, MetricFamily, TrendPoint, Unit } from '../backend/contracts/types'
import { formatDate, formatDateShort, formatNumber, statusLabel } from '../domain/format'
import { Disclosure } from './ui/Disclosure'

export interface ChartEvent {
  id: string
  date: string
  label: string
}

interface TrendChartProps {
  points: TrendPoint[]
  unit: Unit
  thresholds: { green: number; amber: number }
  breachDate: string | null
  caption: string | null
  family?: MetricFamily
  frequency?: Frequency
  events?: ChartEvent[]
  height?: number
  compact?: boolean
}

const DAY = 86_400_000
const GAP_DAYS: Record<Frequency, number> = { Daily: 4, Weekly: 10, Monthly: 40 }

function dayOf(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d) / DAY
}

function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const node = ref.current
    if (!node) return
    const measure = () => setWidth(Math.max(240, Math.round(node.getBoundingClientRect().width)))
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

export function TrendChart({
  points,
  unit,
  thresholds,
  breachDate,
  caption,
  family = 'technology_risk',
  frequency = 'Daily',
  events = [],
  height: heightProp,
  compact = false,
}: TrendChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>(640)
  const [active, setActive] = useState<number | null>(null)
  if (points.length === 0) return null

  const height = heightProp ?? (compact ? 180 : 240)
  const workbook = family === 'data_quality'
  const pad = { left: 52, right: 16, top: 14, bottom: events.length ? 40 : 28 }
  const days = points.map((point) => dayOf(point.date))
  const first = days[0]
  const last = days[days.length - 1]
  const spanDays = Math.max(last - first, 1)
  const values = points.map((point) => point.value)
  const guides = [thresholds.green, thresholds.amber]
  const rawMin = Math.min(...values, ...guides)
  const rawMax = Math.max(...values, ...guides)
  const margin = (rawMax - rawMin || 1) * 0.08
  const min = rawMin - margin
  const max = rawMax + margin
  const plotW = width - pad.left - pad.right
  const plotH = height - pad.top - pad.bottom
  const xOf = (day: number) => pad.left + ((day - first) / spanDays) * plotW
  const yOf = (value: number) => pad.top + ((max - value) / (max - min)) * plotH
  const gapLimit = GAP_DAYS[frequency]

  let path = ''
  points.forEach((point, index) => {
    const broken = index > 0 && days[index] - days[index - 1] > gapLimit
    path += `${index === 0 || broken ? 'M' : 'L'}${xOf(days[index]).toFixed(1)} ${yOf(point.value).toFixed(1)} `
  })
  const gaps = points.filter((_, index) => index > 0 && days[index] - days[index - 1] > gapLimit).length

  const breachLabel = workbook ? 'First red' : 'Breach'
  const breachDay = breachDate ? dayOf(breachDate) : null
  const showBreach = breachDay != null && breachDay >= first && breachDay <= last
  const labelDays: number[] = [first, last]
  if (showBreach && breachDay != null) labelDays.push(breachDay)
  const ticks = labelDays
    .sort((a, b) => a - b)
    .filter((day, index, list) => index === 0 || xOf(day) - xOf(list[index - 1]) > 56 || day === last)
  const tickDates = ticks.map((day) => new Date(day * DAY).toISOString().slice(0, 10))
  const yTicks = [rawMin, (rawMin + rawMax) / 2, rawMax]
  const hasUnconfirmed = points.some((point) => point.unconfirmedAmber)
  const visibleEvents = events.filter((event) => {
    const day = dayOf(event.date)
    return day >= first && day <= last
  })
  const readingLabel = workbook ? 'Workbook pass rate' : 'Synthetic reading'
  const current = active != null ? points[active] : null
  const precise = (value: number) => (workbook && unit === '%' ? `${value.toFixed(2)}%` : formatNumber(value, unit))

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    const lastIndex = points.length - 1
    let next: number | null = null
    if (event.key === 'ArrowRight') next = active == null ? 0 : Math.min(lastIndex, active + 1)
    if (event.key === 'ArrowLeft') next = active == null ? lastIndex : Math.max(0, active - 1)
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = lastIndex
    if (event.key === 'Escape') {
      setActive(null)
      return
    }
    if (next == null) return
    event.preventDefault()
    setActive(next)
  }

  function onPointer(clientX: number, svg: SVGSVGElement) {
    const box = svg.getBoundingClientRect()
    const x = clientX - box.left
    let best = 0
    let bestDist = Infinity
    days.forEach((day, index) => {
      const dist = Math.abs(xOf(day) - x)
      if (dist < bestDist) {
        bestDist = dist
        best = index
      }
    })
    setActive(best)
  }

  const tipLeft = current ? Math.min(Math.max(xOf(dayOf(current.date)), 90), width - 90) : 0

  return (
    <figure className={`chart${compact ? ' is-compact' : ''}`}>
      <div className="chart-frame" ref={ref}>
        <svg
          width={width}
          height={height}
          role="img"
          tabIndex={0}
          aria-label={`${readingLabel}, ${points.length} points from ${formatDate(points[0].date)} to ${formatDate(points[points.length - 1].date)}. Use arrow keys to step through points.`}
          onKeyDown={onKeyDown}
          onBlur={() => setActive(null)}
          onPointerMove={(event) => onPointer(event.clientX, event.currentTarget)}
          onPointerLeave={() => setActive(null)}
        >
          {yTicks.map((tick) => (
            <text key={tick} x={pad.left - 8} y={yOf(tick) + 4} textAnchor="end" className="chart-label">
              {formatNumber(tick, unit)}
            </text>
          ))}
          <line x1={pad.left} x2={width - pad.right} y1={pad.top + plotH} y2={pad.top + plotH} className="chart-axis" />
          <line x1={pad.left} x2={width - pad.right} y1={yOf(thresholds.green)} y2={yOf(thresholds.green)} className="chart-guide guide-green" />
          <line x1={pad.left} x2={width - pad.right} y1={yOf(thresholds.amber)} y2={yOf(thresholds.amber)} className="chart-guide guide-amber" />
          {showBreach && breachDay != null && (
            <g className="chart-breach">
              <line x1={xOf(breachDay)} x2={xOf(breachDay)} y1={pad.top} y2={pad.top + plotH} />
              <text x={xOf(breachDay) + 4} y={pad.top + 10} className="chart-label chart-label-strong">
                {breachLabel}
              </text>
            </g>
          )}
          {visibleEvents.map((event) => {
            const x = xOf(dayOf(event.date))
            const y = pad.top + plotH + 14
            return (
              <g key={event.id} className="chart-event">
                <line x1={x} x2={x} y1={pad.top} y2={pad.top + plotH} />
                <path d={`M${x} ${y - 5} L${x + 5} ${y} L${x} ${y + 5} L${x - 5} ${y} Z`}>
                  <title>
                    {event.id} · {formatDate(event.date)} · {event.label}. Linked by control ID, not causal.
                  </title>
                </path>
              </g>
            )
          })}
          <path d={path} className={`chart-line line-${family}`} />
          {points.map((point, index) => (
            <circle
              key={point.date}
              cx={xOf(days[index])}
              cy={yOf(point.value)}
              r={active === index ? 5 : point.unconfirmedAmber ? 4.5 : points.length > 40 ? 2.4 : 3.4}
              className={`chart-point point-${point.status}${point.unconfirmedAmber ? ' is-open' : ''}${active === index ? ' is-active' : ''}`}
            />
          ))}
          {current && (
            <line
              x1={xOf(dayOf(current.date))}
              x2={xOf(dayOf(current.date))}
              y1={pad.top}
              y2={pad.top + plotH}
              className="chart-cursor"
            />
          )}
          {ticks.map((day, index) => (
            <text
              key={day}
              x={xOf(day)}
              y={height - 8}
              textAnchor={index === 0 ? 'start' : index === ticks.length - 1 ? 'end' : 'middle'}
              className="chart-label"
            >
              {formatDateShort(tickDates[index])}
            </text>
          ))}
        </svg>
        {current && (
          <div className="chart-tip" style={{ left: tipLeft }} role="status">
            <strong className="num">{precise(current.value)}</strong> · {formatDate(current.date)} · {statusLabel(current.status)}
            {current.unconfirmedAmber && <span className="fine"> · Unconfirmed amber</span>}
          </div>
        )}
      </div>
      <figcaption>
        <ul className="legend">
          <li>
            <i className="swatch swatch-line" /> {readingLabel}
          </li>
          <li>
            <i className="swatch swatch-guide-green" /> Green {formatNumber(thresholds.green, unit)}
          </li>
          <li>
            <i className="swatch swatch-guide-amber" /> Amber {formatNumber(thresholds.amber, unit)}
          </li>
          {showBreach && (
            <li>
              <i className="swatch swatch-breach" /> {breachLabel} {breachDate ? formatDateShort(breachDate) : ''}
            </li>
          )}
          {visibleEvents.length > 0 && (
            <li>
              <i className="swatch swatch-event" /> Event linked by control ID, not causal
            </li>
          )}
          {hasUnconfirmed && (
            <li>
              <i className="swatch swatch-open" /> Illustrative amber before 22 October — not a confirmed event
            </li>
          )}
          {gaps > 0 && <li>Line breaks where no result was supplied</li>}
        </ul>
        {caption && !compact && <p className="provenance">{caption}</p>}
      </figcaption>
      <Disclosure summary={`View ${points.length} data points`} className="point-table">
        <div className="table-wrap">
          <table className="data-table">
            <caption className="sr-only">{readingLabel} points</caption>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Value</th>
                <th scope="col">Status</th>
                <th scope="col">Provenance</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.date}>
                  <td>{formatDate(point.date)}</td>
                  <td className="num">{precise(point.value)}</td>
                  <td>{statusLabel(point.status)}</td>
                  <td>{point.pointNote}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Disclosure>
    </figure>
  )
}
