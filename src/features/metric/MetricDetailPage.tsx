import { Link, useParams } from 'react-router-dom'
import type { MetricDetailResponse } from '../../backend/contracts/types'
import { api } from '../../backend/services'
import { StatusBadge } from '../../components/StatusBadge'
import { ThresholdScale } from '../../components/ThresholdScale'
import { TrendChart } from '../../components/TrendChart'
import { Breadcrumbs } from '../../components/ui/Breadcrumbs'
import { PageHeader } from '../../components/ui/PageHeader'
import { FamilyChip, ProvenanceChip, provenanceOf } from '../../components/ui/ProvenanceChip'
import { PageError, PageLoading, SectionUnavailable } from '../../components/ui/SectionState'
import { directionLabel, displayOrMissing, formatDate, formatNumber } from '../../domain/format'
import { useBackTarget, useLinkState } from '../../hooks/useOrigin'
import { useQuery } from '../../hooks/useQuery'
import { DeskBreakdownCard, EvidenceTabs, useControlNotes } from './DqEvidence'

export function MetricDetailPage() {
  const { metricId = '' } = useParams()
  const { data, error, retry } = useQuery(`metric:${metricId}`, '', () => api.getMetric(metricId))
  const back = useBackTarget({ to: '/metrics', label: 'Metric register' })

  if (error && !data) return <PageError message={error.message} onRetry={retry} />
  if (!data) return <PageLoading label="Loading metric detail" />
  return <DetailView key={data.metric.id} data={data} back={back} />
}

function DetailView({ data, back }: { data: MetricDetailResponse; back: ReturnType<typeof useBackTarget> }) {
  const { metric, reading } = data
  const workbook = data.family === 'data_quality'
  const linkState = useLinkState(metric.id)
  const valueText =
    reading.value == null ? 'No reading' : workbook ? `${reading.value.toFixed(2)}%` : formatNumber(reading.value, metric.unit)

  return (
    <div className="page detail">
      <PageHeader
        crumbs={
          <Breadcrumbs
            items={[
              { label: back.label, to: back.to, state: back.state, onClick: back.go },
              { label: metric.id },
            ]}
          />
        }
        title={
          <>
            <span className="mono title-id">{metric.id}</span> {metric.name}
          </>
        }
        chips={
          <>
            <StatusBadge status={reading.status} />
            <FamilyChip family={data.family} />
            <ProvenanceChip kind={provenanceOf(data.family)} />
            <span className="fine">
              {metric.domain} · {metric.frequency} · {directionLabel(metric.direction)}
            </span>
          </>
        }
        actions={
          data.investigationAvailable ? (
            <Link className="btn btn-primary" to={`/investigations/${metric.id}`} state={linkState}>
              Open investigation
            </Link>
          ) : (
            <p className="fine no-inv">No planted investigation for this control. Detail only.</p>
          )
        }
      />

      <dl className="key-facts">
        <div>
          <dt>{workbook ? 'Workbook pass rate' : 'Synthetic reading'}</dt>
          <dd className="kf-value num">{valueText}</dd>
        </div>
        <div>
          <dt>As of</dt>
          <dd>{reading.asOf ? formatDate(reading.asOf) : 'Not supplied'}</dd>
        </div>
        <div>
          <dt>{workbook ? 'First red result' : 'Breach date'}</dt>
          <dd>{reading.breachedOn ? formatDate(reading.breachedOn) : workbook ? 'No red result' : 'Not supplied'}</dd>
        </div>
        {data.workbook && (
          <div>
            <dt>Failed / total</dt>
            <dd className="num">
              {data.workbook.failed.toLocaleString()} / {data.workbook.total.toLocaleString()}
            </dd>
          </div>
        )}
        <div className="kf-scale">
          <dt>Threshold position</dt>
          <dd>
            <ThresholdScale direction={metric.direction} unit={metric.unit} thresholds={metric.thresholds} value={reading.value} family={data.family} compact />
          </dd>
        </div>
      </dl>

      <div className="detail-layout">
        <div className="detail-main">
          {workbook ? <DqTrendCard data={data} /> : <TrendCard data={data} />}
          {workbook ? (
            <>
              <DeskBreakdownCard controlId={metric.id} trend={data.trend} hasDeskSplit={data.workbook?.hasDeskSplit ?? false} />
              <EvidenceTabs controlId={metric.id} />
            </>
          ) : (
            <TechBreakdown data={data} linkState={linkState} />
          )}
        </div>
        <aside className="detail-rail" aria-label="Definition">
          {workbook && data.workbook ? (
            <section className="card">
              <h2>Check logic (workbook)</h2>
              <p>{data.workbook.checkLogic}</p>
              <dl className="kv rail-kv">
                <dt>Regulation</dt>
                <dd>{data.workbook.regulation}</dd>
                <dt>Report</dt>
                <dd>{data.workbook.report}</dd>
                <dt>Critical data element</dt>
                <dd>{data.workbook.cde}</dd>
                <dt>Source system</dt>
                <dd>{data.workbook.sourceSystem}</dd>
                <dt>Owner</dt>
                <dd>{displayOrMissing(metric.ownerFunction)}</dd>
                <dt>Severity</dt>
                <dd>{data.workbook.severity}</dd>
                <dt>BCBS 239</dt>
                <dd>{data.workbook.principle}</dd>
                <dt>Thresholds</dt>
                <dd className="num">
                  Green {metric.thresholds.green}% · Amber {metric.thresholds.amber}%
                </dd>
              </dl>
              <p className="provenance">{data.coverageNote}</p>
            </section>
          ) : (
            <section className="card">
              <h2>Provisional definition — pending client validation</h2>
              <p>{metric.provisionalDefinition}</p>
              <dl className="kv rail-kv">
                <dt>Control</dt>
                <dd className="mono">{metric.controlId}</dd>
                <dt>Control statement</dt>
                <dd>{displayOrMissing(metric.controlStatement)}</dd>
                <dt>Owner function</dt>
                <dd>{displayOrMissing(metric.ownerFunction)}</dd>
                <dt>Thresholds</dt>
                <dd className="num">
                  Green {formatNumber(metric.thresholds.green, metric.unit)} · Amber {formatNumber(metric.thresholds.amber, metric.unit)}
                </dd>
              </dl>
              <ThresholdScale direction={metric.direction} unit={metric.unit} thresholds={metric.thresholds} value={reading.value} family={data.family} />
              <p className="provenance">{data.coverageNote}</p>
            </section>
          )}
        </aside>
      </div>
    </div>
  )
}

function TrendCard({ data }: { data: MetricDetailResponse }) {
  const { metric, reading } = data
  return (
    <section className="card" aria-labelledby="trend-title">
      <div className="card-head">
        <h2 id="trend-title">Trend</h2>
        <ProvenanceChip kind={provenanceOf(data.family)} />
      </div>
      {data.trend.length > 0 ? (
        <TrendChart
          points={data.trend}
          unit={metric.unit}
          thresholds={metric.thresholds}
          breachDate={reading.breachedOn}
          caption={data.trendCaption}
          family={data.family}
          frequency={metric.frequency}
        />
      ) : (
        <SectionUnavailable title="No trend was supplied for this metric." body="Status is not evaluated. It is not a green assessment." />
      )}
    </section>
  )
}

function DqTrendCard({ data }: { data: MetricDetailResponse }) {
  const { metric, reading } = data
  const notes = useControlNotes(metric.id)
  const events = (notes.data?.events ?? []).map((event) => ({ id: event.id, date: event.date, label: `${event.type}: ${event.description}` }))
  return (
    <section className="card" aria-labelledby="trend-title">
      <div className="card-head">
        <h2 id="trend-title">Pass rate trend</h2>
        <ProvenanceChip kind="workbook" />
      </div>
      <TrendChart
        points={data.trend}
        unit={metric.unit}
        thresholds={metric.thresholds}
        breachDate={reading.breachedOn}
        caption={data.trendCaption}
        family={data.family}
        frequency={metric.frequency}
        events={events}
      />
    </section>
  )
}

function TechBreakdown({ data, linkState }: { data: MetricDetailResponse; linkState: unknown }) {
  const org = useQuery(`org:${data.metric.id}`, '', () => api.getOrgContribution(data.metric.id))
  return (
    <section className="card" aria-labelledby="breakdown-title">
      <h2 id="breakdown-title">Breakdown</h2>
      {org.data ? (
        org.data.availability === 'available' ? (
          <p>
            An illustrative organizational contribution is supplied for this metric.{' '}
            <Link to={`/investigations/${data.metric.id}`} state={linkState}>
              See investigation
            </Link>
            .
          </p>
        ) : (
          <SectionUnavailable title="Not supplied." body={org.data.reason} />
        )
      ) : (
        <p className="fine">Checking for an organizational breakdown…</p>
      )}
    </section>
  )
}
