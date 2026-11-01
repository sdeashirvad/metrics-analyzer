import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { DqSummary, MetricDetailResponse } from '../../backend/contracts/types'
import { api, generateDqSummary, getDqSummary } from '../../backend/services'
import { pollDqInvestigation } from '../../backend/services/httpApi'
import { useAnalysisCache } from '../../state/analysisState'
import { estimateFor, recordSample } from '../../state/etaStore'
import { InvestigationActions, InvestigationMark } from '../investigation/AccessControls'
import { investigationAccess } from '../investigation/access'
import { summaryRetry, type SummaryErrorKind } from './summaryFlow'
import { StatusBadge } from '../../components/StatusBadge'
import { ThresholdScale } from '../../components/ThresholdScale'
import { TrendChart } from '../../components/TrendChart'
import { Breadcrumbs } from '../../components/ui/Breadcrumbs'
import { PageHeader } from '../../components/ui/PageHeader'
import { FamilyChip, ProvenanceChip, provenanceOf } from '../../components/ui/ProvenanceChip'
import { ApiError } from '../../backend/services/errors'
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
          <InvestigationLink
            metricId={metric.id}
            family={data.family}
            investigationAvailable={data.investigationAvailable}
            snapshotUnavailable={data.snapshotUnavailable}
            state={linkState}
          />
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
          {workbook ? <DqSummaryCard controlId={metric.id} snapshotUnavailable={data.snapshotUnavailable} /> : null}
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

function InvestigationLink({
  metricId,
  family,
  investigationAvailable,
  snapshotUnavailable,
  state,
}: {
  metricId: string
  family: MetricDetailResponse['family']
  investigationAvailable: boolean
  snapshotUnavailable?: boolean
  state: unknown
}) {
  const dataQuality = family === 'data_quality'
  const cache = useAnalysisCache(dataQuality ? [metricId] : [])
  const eta = estimateFor('INVESTIGATION')
  const access = investigationAccess(
    { family, id: metricId, investigationAvailable, snapshotUnavailable },
    dataQuality ? cache(metricId) : undefined,
  )
  if (access === 'unavailable') return <p className="fine no-inv">No investigation available</p>
  return (
    <div className="row detail-inv">
      <InvestigationMark access={access} family={family} etaLabel={eta?.label ?? null} />
      <InvestigationActions id={metricId} access={access} state={state} length="long" detail={false} />
    </div>
  )
}

async function waitForSummary(controlId: string, runId: string, startedAt: number): Promise<DqSummary> {
  let failures = 0
  const started = Date.now()
  while (Date.now() - started < 20 * 60 * 1000) {
    try {
      const status = await pollDqInvestigation(controlId, runId)
      failures = 0
      if (status.status === 'COMPLETED' && status.result) {
        recordSample('SUMMARY', (Date.now() - startedAt) / 1000)
        return status.result as unknown as DqSummary
      }
      if (status.status === 'FAILED') throw new Error(status.message || 'The summary did not finish. The previous summary is unchanged.')
    } catch (error) {
      if (error instanceof Error && /did not finish|unchanged/.test(error.message)) throw error
      failures += 1
      if (failures >= 3) throw new Error('The status check failed. The previous summary is unchanged.')
    }
    await new Promise((resolve) => setTimeout(resolve, 2500))
  }
  throw new Error('The summary is still running. Reload this page to check it.')
}

function DqSummaryCard({ controlId, snapshotUnavailable }: { controlId: string; snapshotUnavailable?: boolean }) {
  const [summary, setSummary] = useState<DqSummary | null>(null)
  const [missing, setMissing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorKind, setErrorKind] = useState<SummaryErrorKind>(null)
  const [pending, setPending] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [reload, setReload] = useState(0)
  const summaryBusy = useRef(false)
  const summaryEta = estimateFor('SUMMARY')

  useEffect(() => {
    let cancelled = false
    setSummary(null)
    setMissing(false)
    setError(null)
    setErrorKind(null)
    if (snapshotUnavailable) return
    getDqSummary(controlId)
      .then((found) => {
        if (!cancelled) setSummary(found)
      })
      .catch((reason: unknown) => {
        if (cancelled) return
        if (reason instanceof ApiError && reason.status === 404) setMissing(true)
        else {
          setErrorKind('load')
          setError(reason instanceof Error ? reason.message : 'Summary could not be loaded.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [controlId, snapshotUnavailable, reload])

  async function generate(forceRefresh: boolean) {
    if (summaryBusy.current) return
    summaryBusy.current = true
    setPending(true)
    setError(null)
    setErrorKind(null)
    try {
      const startedAt = Date.now()
      const started = await generateDqSummary(controlId, forceRefresh)
      if ('status' in started && started.status === 'RUNNING' && started.runId) {
        const finished = await waitForSummary(controlId, started.runId, startedAt)
        setSummary(finished)
      } else if ('text' in started) {
        setSummary(started)
      }
      setMissing(false)
    } catch (reason) {
      setErrorKind('generate')
      setError(reason instanceof Error ? reason.message : 'Summary could not be generated.')
    } finally {
      summaryBusy.current = false
      setPending(false)
    }
  }

  return (
    <section className="card" aria-labelledby="summary-title">
      <div className="card-head">
        <h2 id="summary-title">Summary</h2>
        <ProvenanceChip kind="workbook" />
      </div>
      {snapshotUnavailable ? (
        <p>No snapshot is stored for this control, so a summary is not generated.</p>
      ) : summary ? (
        <>
          <p>{summary.text}</p>
          <dl className="kv">
            <dt>Movement</dt>
            <dd>{summary.movement}</dd>
            <dt>Threshold position</dt>
            <dd>{summary.thresholdPosition}</dd>
            <dt>Implications</dt>
            <dd>{summary.implications}</dd>
          </dl>
          <p className="fine">{summary.disclaimer}</p>
          {summary.source === 'deterministic' && (
            <p className="fine">Deterministic reading of stored facts. Not a Cortex analysis.</p>
          )}
          {error && <p>{error}</p>}
          {confirming && (
            <div className="callout confirm-run">
              <p>
                Refresh this summary? {summaryEta ? `${summaryEta.label}. ` : ''}The summary on screen stays until the new one finishes.
              </p>
              <div className="actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setConfirming(false)
                    void generate(true)
                  }}
                >
                  Refresh summary
                </button>
                <button type="button" className="btn" onClick={() => setConfirming(false)}>
                  Keep this one
                </button>
              </div>
            </div>
          )}
          <div className="actions">
            <button type="button" className="btn" disabled={pending || confirming} onClick={() => setConfirming(true)}>
              {pending ? 'Refreshing…' : 'Force refresh'}
            </button>
          </div>
        </>
      ) : error ? (
        <div>
          <p>{error}</p>
          {summaryRetry(errorKind) === 'reload' && (
            <div className="actions">
              <button type="button" className="btn" disabled={pending} onClick={() => setReload((value) => value + 1)}>
                Try again
              </button>
            </div>
          )}
          {summaryRetry(errorKind) === 'generate' && (
            <div className="actions">
              <button type="button" className="btn btn-primary" disabled={pending} onClick={() => void generate(false)}>
                {pending ? 'Generating…' : 'Try again'}
              </button>
            </div>
          )}
        </div>
      ) : missing ? (
        <div className="actions">
          {confirming && (
            <p className="fine">Generate a summary? {summaryEta ? `${summaryEta.label}. ` : ''}This asks the analysis service to write one.</p>
          )}
          <button type="button" className="btn btn-primary" disabled={pending} onClick={() => (confirming ? void generate(false) : setConfirming(true))}>
            {pending ? 'Generating…' : confirming ? 'Confirm and generate' : 'Generate summary'}
          </button>
        </div>
      ) : (
        <p className="fine">Checking for a stored summary…</p>
      )}
    </section>
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
            An illustrative organizational contribution is supplied for this metric.
            {data.investigationAvailable && (
              <>
                {' '}
                <Link to={`/investigations/${data.metric.id}`} state={linkState}>
                  See investigation
                </Link>
                .
              </>
            )}
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
