import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { DqInvestigation, Investigation, MetricFamily, RagStatus } from '../../backend/contracts/types'
import { api } from '../../backend/services'
import { FilterToolbar } from '../../components/ui/FilterToolbar'
import { SelectField } from '../../components/ui/Select'
import { PageHeader } from '../../components/ui/PageHeader'
import { EvidenceTag, ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { PageError, PageLoading, SectionLoading } from '../../components/ui/SectionState'
import { formatDate } from '../../domain/format'
import { useLinkState } from '../../hooks/useOrigin'
import { useQuery } from '../../hooks/useQuery'
import { useUrlState } from '../../hooks/useUrlState'
import { loadTechBook } from '../dashboard/DashboardPage'
import { MovementPanel } from './MovementRail'
import { TrendExplorer } from './TrendExplorer'
import { TriageQueue } from './TriageQueue'
import { matchesFilters, rowId, type DqQueueItem, type QueueItem, type StatusFilter, type TechQueueItem, type TriageFilters } from './triage'

const SEEDED = ['M001', 'M003', 'M007', 'M004']
const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'red', label: 'Red' },
  { value: 'amber', label: 'Amber' },
  { value: 'insufficient_data', label: 'Not evaluated' },
  { value: 'recovered', label: 'Recovered' },
]

function isTechCase(item: Investigation | DqInvestigation): item is Investigation {
  return !('kind' in item)
}

function parseStatus(value: string | null): StatusFilter | null {
  return STATUS_OPTIONS.some((option) => option.value === value) ? (value as StatusFilter) : null
}

function parseFamily(value: string | null): MetricFamily | null {
  return value === 'technology_risk' || value === 'data_quality' ? value : null
}

export function OverviewPage() {
  const [params, update] = useUrlState()
  const filters: TriageFilters = {
    family: parseFamily(params.get('family')),
    status: parseStatus(params.get('status')),
    domain: params.get('domain') || null,
    investigation: params.get('inv') === '1',
  }
  const overviewQuery = useQuery('overview', '', () => api.getOverview())
  const techQuery = useQuery('book:technology_risk', '', loadTechBook)
  const casesQuery = useQuery('overview-cases', '', () => Promise.all(SEEDED.map((id) => api.getInvestigation(id))))
  const trendsQuery = useQuery('overview-trends', '', () => Promise.all(SEEDED.map((id) => api.getTrend(id))))
  const [highlighted, setHighlighted] = useState<string | null>(null)
  const linkState = useLinkState('Triage')

  const failed = overviewQuery.error ?? techQuery.error
  if (failed && (!overviewQuery.data || !techQuery.data)) {
    return (
      <PageError
        message={failed.message}
        onRetry={() => {
          overviewQuery.retry()
          techQuery.retry()
        }}
      />
    )
  }
  if (!overviewQuery.data || !techQuery.data) return <PageLoading label="Loading the triage queue" />

  const overview = overviewQuery.data
  const dq = overview.dataQuality
  const techItems = techQuery.data.items
  const cases = (casesQuery.data ?? []).filter(isTechCase)
  const techQueue: TechQueueItem[] = techItems.map((item) => ({
    family: 'technology_risk',
    id: item.metric.id,
    name: item.metric.name,
    domain: item.metric.domain,
    status: item.reading.status,
    item,
    summary: overview.investigations.find((summary) => summary.metricId === item.metric.id),
    investigation: cases.find((record) => record.metricId === item.metric.id),
    trend: trendsQuery.data?.find((trend) => trend.metricId === item.metric.id),
    investigationAvailable: item.investigationAvailable,
    recovered: false,
  }))
  const rank: Record<RagStatus, number> = { red: 0, amber: 1, insufficient_data: 2, green: 3 }
  techQueue.sort(
    (a, b) =>
      rank[a.status] - rank[b.status] ||
      (a.item.reading.breachedOn ?? '9999').localeCompare(b.item.reading.breachedOn ?? '9999') ||
      a.id.localeCompare(b.id),
  )
  const dqQueue: DqQueueItem[] = dq.atRisk.map((control) => ({
    family: 'data_quality',
    id: control.id,
    name: control.name,
    domain: control.dimension,
    status: control.status,
    control,
    investigationAvailable: control.investigationAvailable,
    recovered: control.recovered,
  }))

  const techVisible = techQueue.filter((item) => matchesFilters(item, filters))
  const dqVisible = dqQueue.filter((item) => matchesFilters(item, filters))
  const techCounts = { red: 0, amber: 0, insufficient_data: 0, green: 0 }
  for (const item of techQueue) techCounts[item.status] += 1
  const hiddenHint = (items: QueueItem[]) => {
    if (filters.status) return null
    const notEvaluated = items.filter((item) => item.status === 'insufficient_data').length
    const recovered = items.filter((item) => item.recovered).length
    const parts = []
    if (notEvaluated) parts.push(`${notEvaluated} not evaluated`)
    if (recovered) parts.push(`${recovered} recovered`)
    return parts.length ? `${parts.join(' and ')} not shown. Use the Status filter to include them.` : null
  }

  const groups = [
    {
      family: 'technology_risk' as const,
      title: 'Technology Risk',
      atRisk: techCounts.red + techCounts.amber,
      total: techItems.length,
      hiddenNote: hiddenHint(techQueue),
      items: techVisible as QueueItem[],
    },
    {
      family: 'data_quality' as const,
      title: 'Data Quality',
      atRisk: dq.latest.red + dq.latest.amber,
      total: dq.controls,
      hiddenNote: hiddenHint(dqQueue),
      items: dqVisible as QueueItem[],
    },
  ].filter((group) => !filters.family || group.family === filters.family)

  const techDomains = [...new Set(techItems.map((item) => item.metric.domain))]
  const dqDimensions = dq.byDimension.map((item) => item.name)
  const activeCount = [filters.family, filters.status, filters.domain, filters.investigation || null].filter(Boolean).length
  const queueIds = new Set([...techVisible, ...dqVisible].map((item) => item.id))
  const shown = techVisible.length + dqVisible.length

  function select(id: string) {
    setHighlighted(id)
    const node = document.getElementById(rowId(id))
    if (!node) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    node.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
  }

  function clear() {
    update({ family: null, status: null, domain: null, inv: null }, { commit: true })
  }

  return (
    <div className="page overview">
      <PageHeader title="Triage" subtitle="Portfolio triage" />
      <FilterToolbar
        label="Triage filters"
        activeCount={activeCount}
        onClear={clear}
        summary={
          <span className="fine num" aria-live="polite">
            {shown} row{shown === 1 ? '' : 's'} in the queue
          </span>
        }
      >
        <SelectField
          label="Family"
          value={filters.family ?? ''}
          onChange={(next) => update({ family: next || null, domain: null }, { commit: true })}
          options={[
            { value: '', label: 'Both books' },
            { value: 'technology_risk', label: 'Technology Risk' },
            { value: 'data_quality', label: 'Data Quality' },
          ]}
        />
        <SelectField
          label="Status"
          value={filters.status ?? ''}
          onChange={(next) => update({ status: next || null }, { commit: true })}
          options={[{ value: '', label: 'Red and amber' }, ...STATUS_OPTIONS]}
        />
        <SelectField
          label={filters.family === 'data_quality' ? 'Dimension' : filters.family === 'technology_risk' ? 'Domain' : 'Domain or dimension'}
          value={filters.domain ?? ''}
          onChange={(next) => update({ domain: next || null }, { commit: true })}
          options={[
            { value: '', label: 'All' },
            ...(filters.family !== 'data_quality' ? techDomains.map((item) => ({ value: item, label: item, group: 'Technology Risk domains' })) : []),
            ...(filters.family !== 'technology_risk' ? dqDimensions.map((item) => ({ value: item, label: item, group: 'Data Quality dimensions' })) : []),
          ]}
        />
        <label className="check">
          <input
            type="checkbox"
            checked={filters.investigation}
            onChange={(event) => update({ inv: event.target.checked ? '1' : null }, { commit: true })}
          />
          Has investigation
        </label>
      </FilterToolbar>

      <div className="triage-layout">
        <div className="triage-col">
          <TriageQueue groups={groups} highlighted={highlighted} casesLoading={!casesQuery.data} onClear={clear} />
        </div>
        <aside className="triage-rail" aria-label="Trend explorer and movement">
          <TrendExplorer overview={overview} family={filters.family} />
          <MovementPanel overview={overview} family={filters.family} queueIds={queueIds} highlighted={highlighted} onSelect={select} />
        </aside>
      </div>

      <section className="overview-section" aria-labelledby="hotspots-title">
        <h2 id="hotspots-title">Hotspots</h2>
        <div className="two-up">
          {filters.family !== 'data_quality' && (
            <article className="card">
              <div className="card-head">
                <h3>Technology Risk organizational hotspots</h3>
                <ProvenanceChip kind="synthetic" />
              </div>
              <p className="fine">Supplied only for M001 and M003. Figures are illustrative.</p>
              <ul className="callout-list">
                {overview.hotspotCallouts.map((item) => (
                  <li key={item.metricId}>
                    <Link className="callout" to={`/investigations/${item.metricId}`} state={linkState}>
                      <span className="mono">{item.metricId}</span>
                      <strong>{item.group}</strong>
                      <span className="muted">{item.statement}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </article>
          )}
          {filters.family !== 'technology_risk' && (
            <article className="card">
              <div className="card-head">
                <h3>Data Quality desk failure volume · {formatDate(dq.asOf)}</h3>
                <ProvenanceChip kind="workbook" />
              </div>
              <p className="fine">
                Failure volume, not lowest pass rate; {dq.coverage.deskControls} of {dq.controls} controls have a desk split.
              </p>
              <VolumeBars rows={dq.hotspots.map((row) => ({ label: row.deskName, value: row.failed }))} />
            </article>
          )}
        </div>
      </section>

      <section className="overview-section" aria-labelledby="coverage-title">
        <h2 id="coverage-title">Coverage and validation</h2>
        <div className="two-up">
          {filters.family !== 'data_quality' && (
            <article className="card">
              <div className="card-head">
                <h3>Technology Risk checks still open</h3>
                <EvidenceTag kind="not_supplied" label="Pending validation" />
              </div>
              <p className="fine">Checks required before the seeded stories can be treated as evidenced. No owner or deadline was supplied.</p>
              {casesQuery.data ? (
                <div className="validate-cases">
                  {cases.map((item) => (
                    <div key={item.metricId} className="validate-case">
                      <Link to={`/investigations/${item.metricId}`} state={linkState} className="mono">
                        {item.metricId}
                      </Link>
                      <ul className="tight-list">
                        {item.pathToGreen.checks.map((check) => (
                          <li key={check}>{check}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <SectionLoading label="Loading validation checks" />
              )}
              <h4>Data discovery</h4>
              <ul className="tight-list">
                <li>Confirm whether SMARTS holds metric-by-organization breakdowns.</li>
                <li>Confirm whether change and incident records can be joined to metrics.</li>
              </ul>
            </article>
          )}
          {filters.family !== 'technology_risk' && (
            <article className="card">
              <div className="card-head">
                <h3>Data Quality coverage</h3>
                <ProvenanceChip kind="workbook" />
              </div>
              <ul className="tight-list">
                <li>
                  <span className="num">{dq.coverage.deskControls}</span> of <span className="num">{dq.controls}</span> controls have a desk split.
                </li>
                <li>
                  <span className="num">{dq.coverage.controlDatesWithoutDesk.toLocaleString()}</span> control-dates have no desk split.
                </li>
                <li>
                  <span className="num">{dq.coverage.controlsWithoutNarrative}</span> controls have no planted narrative.
                </li>
              </ul>
              <p className="callout-warn">{dq.coverage.discrepancy}</p>
            </article>
          )}
        </div>
      </section>
    </div>
  )
}

function VolumeBars({ rows }: { rows: Array<{ label: string; value: number }> }) {
  const max = Math.max(...rows.map((row) => row.value), 1)
  return (
    <ul className="volume-bars">
      {rows.map((row) => (
        <li key={row.label}>
          <span className="vb-label">{row.label}</span>
          <span className="vb-track" aria-hidden="true">
            <span style={{ width: `${(row.value / max) * 100}%` }} />
          </span>
          <span className="vb-value num">{row.value.toLocaleString()}</span>
        </li>
      ))}
    </ul>
  )
}
