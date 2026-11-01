import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MetricFamily } from '../../backend/contracts/types'
import { StatusBadge } from '../../components/StatusBadge'
import { EvidenceTag, ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { SectionEmpty } from '../../components/ui/SectionState'
import { formatDate, formatDateShort, formatNumber, recoveredLine } from '../../domain/format'
import { useLinkState } from '../../hooks/useOrigin'
import { useAnalysisCache, type CacheEntry } from '../../state/analysisState'
import { estimateFor } from '../../state/etaStore'
import { InvestigationActions, InvestigationMark } from '../investigation/AccessControls'
import { investigationAccess } from '../investigation/access'
import { rowId, type DqQueueItem, type QueueItem, type TechQueueItem } from './triage'

interface GroupInfo {
  family: MetricFamily
  title: string
  atRisk: number
  total: number
  hiddenNote: string | null
}

interface TriageQueueProps {
  groups: Array<GroupInfo & { items: QueueItem[] }>
  highlighted: string | null
  casesLoading: boolean
  onClear: () => void
}

export function TriageQueue({ groups, highlighted, casesLoading, onClear }: TriageQueueProps) {
  const cache = useAnalysisCache(groups.flatMap((group) => group.items.filter((item) => item.family === 'data_quality').map((item) => item.id)))
  const eta = estimateFor('INVESTIGATION')
  const total = groups.reduce((sum, group) => sum + group.items.length, 0)
  if (total === 0) {
    return (
      <SectionEmpty
        title="Nothing matches these filters"
        body="Change a filter or clear them to see the full at-risk queue."
        action={
          <button type="button" className="btn" onClick={onClear}>
            Clear filters
          </button>
        }
      />
    )
  }
  return (
    <div className="triage">
      {groups.map((group) => (
        <section key={group.family} className={`triage-group group-${group.family}`} aria-labelledby={`group-${group.family}`}>
          <header className="triage-group-head">
            <h2 id={`group-${group.family}`}>
              {group.title} <span className="muted num">· {group.atRisk} at risk of {group.total}</span>
            </h2>
            <ProvenanceChip
              kind={group.family === 'data_quality' ? 'workbook' : 'synthetic'}
              label={group.family === 'data_quality' ? 'Live from Snowflake' : 'Illustrative'}
            />
          </header>
          {group.items.length === 0 ? (
            <p className="fine triage-none">No {group.title} rows match these filters.</p>
          ) : (
            <ul className="triage-list">
              {group.items.map((item) =>
                item.family === 'technology_risk' ? (
                  <TechRow key={item.id} item={item} highlighted={highlighted === item.id} casesLoading={casesLoading} />
                ) : (
                  <DqRow key={item.id} item={item} highlighted={highlighted === item.id} entry={cache(item.id)} etaLabel={eta?.label ?? null} />
                ),
              )}
            </ul>
          )}
          {group.hiddenNote && <p className="fine triage-hidden">{group.hiddenNote}</p>}
        </section>
      ))}
    </div>
  )
}

function useExpand() {
  const [open, setOpen] = useState(false)
  return { open, toggle: () => setOpen((value) => !value) }
}

function TechRow({ item, highlighted, casesLoading }: { item: TechQueueItem; highlighted: boolean; casesLoading: boolean }) {
  const { open, toggle } = useExpand()
  const linkState = useLinkState('Triage')
  const { metric, reading } = item.item
  const hotspot = item.summary?.hotspotLabel
  const unconfirmed = item.trend?.points.some((point) => point.unconfirmedAmber)
  const bodyId = `${rowId(item.id)}-body`
  return (
    <li id={rowId(item.id)} className={`triage-row tone-${item.status}${highlighted ? ' is-highlighted' : ''}${open ? ' is-open' : ''}`}>
      <div className="triage-summary">
        <StatusBadge status={item.status} />
        <div className="triage-main">
          <div className="triage-title">
            <span className="mono">{metric.id}</span> {metric.name}
          </div>
          <div className="triage-fact">
            {metric.domain} · <span className="num">{reading.value == null ? 'No reading' : formatNumber(reading.value, metric.unit)}</span> synthetic
            {reading.breachedOn && <> · red since {formatDateShort(reading.breachedOn)}</>}
          </div>
        </div>
        <div className="triage-actions">
          <InvestigationMark
            access={investigationAccess({ family: 'technology_risk', id: metric.id, investigationAvailable: item.investigationAvailable })}
            family="technology_risk"
            etaLabel={null}
          />
          <InvestigationActions
            id={metric.id}
            access={investigationAccess({ family: 'technology_risk', id: metric.id, investigationAvailable: item.investigationAvailable })}
            state={linkState}
            length="short"
          />
          <button type="button" className="btn btn-quiet btn-sm expand" aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
            <span className="chevron" aria-hidden="true" />
            <span className="sr-only">Details for {metric.id}</span>
          </button>
        </div>
      </div>
      <div id={bodyId} className="triage-body" hidden={!open}>
        {item.summary && <p>{item.summary.headline}</p>}
        <p className="fine">
          {hotspot ? `Organizational hotspot: ${hotspot} (illustrative).` : 'Organizational breakdown not supplied.'}
        </p>
        {unconfirmed && item.trend?.caption && <p className="note-amber">{item.trend.caption}</p>}
        {item.investigationAvailable &&
          (item.investigation ? (
            <>
              <h4>Checks to validate</h4>
              <ul className="tight-list">
                {item.investigation.pathToGreen.checks.map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            </>
          ) : (
            casesLoading && <p className="fine">Loading validation checks…</p>
          ))}
        <div className="row">
          <Link to={`/metrics/${metric.id}`} state={linkState}>
            Open detail
          </Link>
        </div>
      </div>
    </li>
  )
}

function DqRow({ item, highlighted, entry, etaLabel }: { item: DqQueueItem; highlighted: boolean; entry: CacheEntry | undefined; etaLabel: string | null }) {
  const { open, toggle } = useExpand()
  const linkState = useLinkState('Triage')
  const control = item.control
  const access = investigationAccess(
    { family: 'data_quality', id: control.id, investigationAvailable: item.investigationAvailable },
    entry,
  )
  const bodyId = `${rowId(item.id)}-body`
  return (
    <li id={rowId(item.id)} className={`triage-row tone-${item.recovered ? 'recovered' : item.status}${highlighted ? ' is-highlighted' : ''}${open ? ' is-open' : ''}`}>
      <div className="triage-summary">
        <StatusBadge status={control.status} label={item.recovered ? 'Recovered' : undefined} />
        <div className="triage-main">
          <div className="triage-title">
            <span className="mono">{control.id}</span> {control.name}
          </div>
          <div className="triage-fact">
            {item.recovered ? (
              recoveredLine(control)
            ) : (
              <>
                {control.dimension} · <span className="num">{control.passRate.toFixed(2)}%</span> ·{' '}
                <span className="num">{control.failed.toLocaleString()}</span> failed
                {control.firstRed && <> · first red {formatDateShort(control.firstRed)}</>}
              </>
            )}
          </div>
        </div>
        <div className="triage-actions">
          <InvestigationMark access={access} family="data_quality" etaLabel={etaLabel} />
          <InvestigationActions id={control.id} access={access} state={linkState} length="short" />
          <button type="button" className="btn btn-quiet btn-sm expand" aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
            <span className="chevron" aria-hidden="true" />
            <span className="sr-only">Details for {control.id}</span>
          </button>
        </div>
      </div>
      <div id={bodyId} className="triage-body" hidden={!open}>
        {control.readme ? (
          <p>
            <EvidenceTag kind="hypothesis" label="README story" /> {control.readme}
          </p>
        ) : (
          <p className="fine">No planted investigation. The workbook supplies results and exceptions only.</p>
        )}
        <dl className="facts-inline">
          <div>
            <dt>Latest</dt>
            <dd className="num">
              {control.passRate.toFixed(2)}% · {control.failed.toLocaleString()} of {control.total.toLocaleString()} failed · {formatDate(control.asOf)}
            </dd>
          </div>
          <div>
            <dt>First red</dt>
            <dd>{control.firstRed ? formatDate(control.firstRed) : 'No red result'}</dd>
          </div>
          <div>
            <dt>Desk split</dt>
            <dd>{control.hasDeskSplit ? 'Desk split supplied' : 'Desk split not supplied for this control'}</dd>
          </div>
          <div>
            <dt>Linked events</dt>
            <dd>{control.eventCount ? `${control.eventCount} linked by control ID` : 'None linked'}</dd>
          </div>
        </dl>
        <div className="row">
          <Link to={`/metrics/${control.id}`} state={linkState}>
            Open detail
          </Link>
        </div>
      </div>
    </li>
  )
}
