import { Link } from 'react-router-dom'
import type { DataQualityOverview, MetricListItem, RagStatus, TrendResponse } from '../../backend/contracts/types'
import { api } from '../../backend/services'
import { StatusStrip, type StripSegment } from '../../components/ui/StatusStrip'
import { AttentionRow } from '../../components/ui/AttentionRow'
import { BookTile } from '../../components/ui/BookTile'
import { PageHeader } from '../../components/ui/PageHeader'
import { ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { SectionError, SectionLoading } from '../../components/ui/SectionState'
import { SegmentedControl } from '../../components/ui/SegmentedControl'
import { Sparkline } from '../../components/ui/Sparkline'
import { formatDate, formatDateShort, formatNumber } from '../../domain/format'
import { useLinkState } from '../../hooks/useOrigin'
import { useQuery } from '../../hooks/useQuery'
import { useUrlState } from '../../hooks/useUrlState'

type View = 'all' | 'technology_risk' | 'data_quality'

const STATUS_ORDER: RagStatus[] = ['red', 'amber', 'green', 'insufficient_data']

export function loadTechBook() {
  return api.listMetrics({ family: 'technology_risk', pageSize: 100 })
}

export function loadDqBook() {
  return api.getOverview().then((overview) => overview.dataQuality)
}

function countBy<T>(items: T[], statusOf: (item: T) => RagStatus): Record<RagStatus, number> {
  const counts: Record<RagStatus, number> = { red: 0, amber: 0, green: 0, insufficient_data: 0 }
  for (const item of items) counts[statusOf(item)] += 1
  return counts
}

function registerLink(family: string, domain: string | null, status: RagStatus) {
  const params = new URLSearchParams({ family })
  if (domain) params.set('domain', domain)
  params.set('status', status)
  return `/metrics?${params.toString()}`
}

function segments(counts: Record<RagStatus, number>, link: (status: RagStatus) => string): StripSegment[] {
  return STATUS_ORDER.map((status) => ({ status, count: counts[status], to: link(status) }))
}

export function DashboardPage() {
  const [params, update] = useUrlState()
  const raw = params.get('view')
  const view: View = raw === 'technology_risk' || raw === 'data_quality' ? raw : 'all'
  const tech = useQuery('book:technology_risk', '', loadTechBook)
  const dq = useQuery('book:data_quality', '', loadDqBook)

  return (
    <div className={`page dashboard view-${view}`}>
      <PageHeader title="Metric health" subtitle="Two books, kept separate. Each tile names its own source.">
        <SegmentedControl<View>
          label="Book"
          value={view}
          onChange={(next) => update({ view: next === 'all' ? null : next }, { commit: true })}
          options={[
            { value: 'all', label: 'All' },
            { value: 'technology_risk', label: 'Technology Risk' },
            { value: 'data_quality', label: 'Data Quality' },
          ]}
        />
      </PageHeader>

      <div className="book-grid">
        {view !== 'data_quality' && (
          <TechBook
            items={tech.data?.items}
            error={tech.error}
            retry={tech.retry}
            single={view === 'technology_risk'}
          />
        )}
        {view !== 'technology_risk' && (
          <DqBook data={dq.data} error={dq.error} retry={dq.retry} single={view === 'data_quality'} />
        )}
      </div>
    </div>
  )
}

interface BookProps {
  error: Error | null
  retry: () => void
  single: boolean
}

function TechBook({ items, error, retry, single }: BookProps & { items: MetricListItem[] | undefined }) {
  const linkState = useLinkState('Dashboard')
  const seeded = (items ?? [])
    .filter((item) => item.investigationAvailable && (item.reading.status === 'red' || item.reading.status === 'amber'))
    .sort((a, b) => (a.reading.breachedOn ?? '9999').localeCompare(b.reading.breachedOn ?? '9999'))
  const limit = single ? 6 : 3
  const shown = seeded.slice(0, limit)
  const trends = useQuery('dashboard-trends', shown.map((item) => item.metric.id).join(','), () =>
    Promise.all(shown.map((item) => api.getTrend(item.metric.id))),
  )

  if (!items) {
    return (
      <>
        <BookTile family="technology_risk" title="Technology Risk" chip={<ProvenanceChip kind="synthetic" />} wide={single}>
          {error ? <SectionError message={error.message} onRetry={retry} /> : <SectionLoading label="Loading Technology Risk" />}
        </BookTile>
        <div className="book-card" />
        <div className="book-card" />
      </>
    )
  }

  const counts = countBy(items, (item) => item.reading.status)
  const atRisk = counts.red + counts.amber
  const domains = [...new Set(items.map((item) => item.metric.domain))]
  const hidden = seeded.length - shown.length
  const trendById = new Map<string, TrendResponse>((trends.data ?? []).map((trend) => [trend.metricId, trend]))

  return (
    <>
      <BookTile
        family="technology_risk"
        title="Technology Risk"
        chip={<ProvenanceChip kind="synthetic" />}
        figure={atRisk}
        figureLabel={
          <>
            at risk of {items.length}
            <span className="muted"> · {counts.red} red, {counts.amber} amber</span>
          </>
        }
        footnote={
          counts.insufficient_data > 0
            ? `${counts.insufficient_data} metrics have no reading. Not counted as green.`
            : undefined
        }
        wide={single}
      >
        <StatusStrip
          label="Technology Risk status"
          segments={segments(counts, (status) => registerLink('technology_risk', null, status))}
        />
      </BookTile>

      <section className="book-card" aria-labelledby="tech-next">
        <div className="card-head">
          <h2 id="tech-next">Open next</h2>
          <span className="fine">Seeded investigations, earliest breach first</span>
        </div>
        <ul className="attention-list">
          {shown.map((item) => {
            const trend = trendById.get(item.metric.id)
            return (
              <AttentionRow
                key={item.metric.id}
                id={item.metric.id}
                name={item.metric.name}
                status={item.reading.status}
                to={`/investigations/${item.metric.id}`}
                state={linkState}
                action="Investigate"
                fact={
                  <>
                    <span className="num">{item.reading.value == null ? 'No reading' : formatNumber(item.reading.value, item.metric.unit)}</span> synthetic
                    {item.reading.breachedOn && <> · red since {formatDateShort(item.reading.breachedOn)}</>}
                  </>
                }
                spark={
                  trend ? (
                    <Sparkline label={`${item.metric.id} recent synthetic trend`} points={trend.points.map((point) => ({ value: point.value, status: point.status }))} />
                  ) : (
                    <span className="spark spark-empty" aria-hidden="true" />
                  )
                }
              />
            )
          })}
        </ul>
        {hidden > 0 && (
          <Link className="more-link" to="/overview?family=technology_risk">
            +{hidden} more in Triage ({seeded.slice(limit).map((item) => item.metric.id).join(', ')})
          </Link>
        )}
      </section>

      <section className="book-card" aria-labelledby="tech-where">
        <div className="card-head">
          <h2 id="tech-where">Where it concentrates</h2>
          <span className="fine">Status by domain · segments open the register</span>
        </div>
        <ul className="concentration">
          {domains.map((domain) => {
            const inDomain = items.filter((item) => item.metric.domain === domain)
            const domainCounts = countBy(inDomain, (item) => item.reading.status)
            return (
              <li key={domain}>
                <span className="conc-label">{domain}</span>
                <StatusStrip
                  size="sm"
                  label={domain}
                  segments={segments(domainCounts, (status) => registerLink('technology_risk', domain, status))}
                />
                <span className="conc-count num">{inDomain.length}</span>
              </li>
            )
          })}
        </ul>
      </section>
    </>
  )
}

function DqBook({ data, error, retry, single }: BookProps & { data: DataQualityOverview | undefined }) {
  const linkState = useLinkState('Dashboard')
  if (!data) {
    return (
      <>
        <BookTile family="data_quality" title="Data Quality" chip={<ProvenanceChip kind="workbook" />} wide={single}>
          {error ? <SectionError message={error.message} onRetry={retry} /> : <SectionLoading label="Loading Data Quality" />}
        </BookTile>
        <div className="book-card" />
        <div className="book-card" />
      </>
    )
  }

  const counts: Record<RagStatus, number> = { ...data.latest, insufficient_data: 0 }
  const atRisk = data.latest.red + data.latest.amber
  const recentById = new Map(data.stories.map((story) => [story.id, story.recent]))
  const reds = data.atRisk.filter((item) => item.status === 'red' && !item.recovered)
  const ordered = [
    ...reds.filter((item) => item.investigationAvailable).sort((a, b) => (a.firstRed ?? '').localeCompare(b.firstRed ?? '')),
    ...reds.filter((item) => !item.investigationAvailable),
  ]
  const limit = single ? 6 : 3
  const shown = ordered.slice(0, limit)
  const hiddenReds = ordered.slice(limit)
  const ambers = data.atRisk.filter((item) => item.status === 'amber')

  let moreText = ''
  if (hiddenReds.length > 0) {
    const [first, ...rest] = hiddenReds
    moreText = rest.length ? `${first.id} and ${rest.length} more red control${rest.length > 1 ? 's' : ''} in Triage` : `${first.id} in Triage`
  } else if (ambers.length > 0) {
    moreText = `${ambers.length} amber control${ambers.length > 1 ? 's' : ''} in Triage`
  }

  return (
    <>
      <BookTile
        family="data_quality"
        title="Data Quality"
        chip={<ProvenanceChip kind="workbook" />}
        figure={atRisk}
        figureLabel={
          <>
            at risk of {data.controls}
            <span className="muted"> · {data.latest.red} red, {data.latest.amber} amber</span>
          </>
        }
        aside={
          <>
            <span className="aside-num num">{data.openExceptions.toLocaleString()}</span>
            <span className="fine">open exceptions</span>
          </>
        }
        footnote={`Latest supplied RAG per control on ${formatDate(data.asOf)}. Not added to Technology Risk.`}
        wide={single}
      >
        <StatusStrip label="Data Quality status" segments={segments(counts, (status) => registerLink('data_quality', null, status))} />
      </BookTile>

      <section className="book-card" aria-labelledby="dq-next">
        <div className="card-head">
          <h2 id="dq-next">Open next</h2>
          <span className="fine">Red controls, earliest first red first</span>
        </div>
        <ul className="attention-list">
          {shown.map((item) => {
            const recent = recentById.get(item.id)
            return (
              <AttentionRow
                key={item.id}
                id={item.id}
                name={item.name}
                status={item.status}
                to={item.investigationAvailable ? `/investigations/${item.id}` : `/metrics/${item.id}`}
                state={linkState}
                action={item.investigationAvailable ? 'Investigate' : 'Detail only'}
                fact={
                  <>
                    <span className="num">{item.passRate.toFixed(2)}%</span> · <span className="num">{item.failed.toLocaleString()}</span> failed
                    {item.firstRed && <> · first red {formatDateShort(item.firstRed)}</>}
                  </>
                }
                spark={
                  recent ? (
                    <Sparkline label={`${item.id} last ${recent.length} workbook results`} points={recent.map((point) => ({ value: point.passRate, status: point.status }))} />
                  ) : (
                    <span className="spark spark-empty" aria-hidden="true" />
                  )
                }
              />
            )
          })}
        </ul>
        {moreText && (
          <Link className="more-link" to="/overview?family=data_quality">
            {moreText}
          </Link>
        )}
      </section>

      <section className="book-card" aria-labelledby="dq-where">
        <div className="card-head">
          <h2 id="dq-where">Where it concentrates</h2>
          <span className="fine">Latest status by dimension · segments open the register</span>
        </div>
        <ul className="concentration">
          {data.byDimension.map((dimension) => (
            <li key={dimension.name}>
              <span className="conc-label">{dimension.name}</span>
              <StatusStrip
                size="sm"
                label={dimension.name}
                segments={segments(
                  { red: dimension.red, amber: dimension.amber, green: dimension.green, insufficient_data: 0 },
                  (status) => registerLink('data_quality', dimension.name, status),
                )}
              />
              <span className="conc-count num">{dimension.red + dimension.amber + dimension.green}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
