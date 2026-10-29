import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MetricFamily, OverviewResponse } from '../../backend/contracts/types'
import { EvidenceTag, type Evidence } from '../../components/ui/ProvenanceChip'
import { formatDateShort } from '../../domain/format'

interface MovementItem {
  key: string
  date: string
  family: MetricFamily
  targetId: string
  label: string
  tag: Evidence
  inQueue: boolean
}

interface MovementPanelProps {
  overview: OverviewResponse
  family: MetricFamily | null
  queueIds: Set<string>
  highlighted: string | null
  onSelect: (id: string) => void
}

const INITIAL_COUNT = 6

/** Chronology only: dated scenario facts, first-red results and linked events. No charts here. */
export function MovementPanel({ overview, family, queueIds, highlighted, onSelect }: MovementPanelProps) {
  const dq = overview.dataQuality
  const [expanded, setExpanded] = useState(false)
  const items: MovementItem[] = [
    ...overview.deterioration.map((event) => ({
      key: `tr-${event.metricId}`,
      date: event.date,
      family: 'technology_risk' as const,
      targetId: event.metricId,
      label: `${event.metricId} · ${event.label}`,
      tag: 'fact' as const,
      inQueue: queueIds.has(event.metricId),
    })),
    ...dq.stories
      .filter((story) => story.firstRed)
      .map((story) => ({
        key: `fr-${story.id}`,
        date: story.firstRed as string,
        family: 'data_quality' as const,
        targetId: story.id,
        label: `${story.id} · first red result`,
        tag: 'workbook' as const,
        inQueue: queueIds.has(story.id),
      })),
    ...dq.events.map((event) => ({
      key: `ev-${event.id}`,
      date: event.date,
      family: 'data_quality' as const,
      targetId: event.controlId,
      label: `${event.id} ${event.type} · ${event.controlId}`,
      tag: 'linked' as const,
      inQueue: queueIds.has(event.controlId),
    })),
  ]
    .filter((item) => !family || item.family === family)
    .sort((a, b) => b.date.localeCompare(a.date) || a.key.localeCompare(b.key))

  const visible = expanded ? items : items.slice(0, INITIAL_COUNT)
  const hidden = items.length - visible.length

  return (
    <section className="card movement" aria-labelledby="movement-title">
      <div className="card-head">
        <h2 id="movement-title">Movement</h2>
        <span className="fine">Newest first · {items.length} dated item{items.length === 1 ? '' : 's'}</span>
      </div>
      <p className="fine">Chronology only. Events are linked to controls by control ID; a nearby date is not treated as a cause.</p>
      <ol className="movement-list" id="movement-list">
        {visible.map((item) => (
          <li key={item.key} className={`movement-item fam-${item.family}${highlighted === item.targetId ? ' is-active' : ''}`}>
            <time dateTime={item.date} className="num">
              {formatDateShort(item.date)}
            </time>
            <div>
              {item.inQueue ? (
                <button type="button" className="link-button" onClick={() => onSelect(item.targetId)}>
                  {item.label}
                </button>
              ) : (
                <Link to={`/metrics/${item.targetId}`}>{item.label}</Link>
              )}
              <EvidenceTag kind={item.tag} />
            </div>
          </li>
        ))}
      </ol>
      {items.length > INITIAL_COUNT && (
        <button type="button" className="btn btn-quiet btn-sm movement-toggle" aria-expanded={expanded} aria-controls="movement-list" onClick={() => setExpanded((value) => !value)}>
          {expanded ? 'Show recent only' : `View all movement (${hidden} more)`}
        </button>
      )}
    </section>
  )
}
