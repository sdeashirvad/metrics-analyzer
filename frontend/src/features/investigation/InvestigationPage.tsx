import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { Investigation, MetricDetailResponse } from '../../backend/contracts/types'
import { api } from '../../backend/services'
import { ApiError } from '../../backend/services/errors'
import { HotspotChart } from '../../components/HotspotChart'
import { StatusBadge } from '../../components/StatusBadge'
import { ThresholdScale } from '../../components/ThresholdScale'
import { TrendChart } from '../../components/TrendChart'
import { Disclosure } from '../../components/ui/Disclosure'
import { PageHeader } from '../../components/ui/PageHeader'
import { EvidenceTag, FamilyChip, ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { PageError, PageLoading } from '../../components/ui/SectionState'
import { displayOrMissing, formatDate, formatNumber } from '../../domain/format'
import { useBackTarget, useLinkState, type BackTarget } from '../../hooks/useOrigin'
import { useQuery } from '../../hooks/useQuery'
import { DQ_STAGES, DqInvestigationView } from './DqInvestigationView'
import { AnalysisSimulation } from './AnalysisSimulation'
import { BackButton, InvestigationCrumbs } from './InvestigationChrome'

const ANALYSIS_STAGES = [
  'Retrieving the control definition, direction, and thresholds',
  'Placing the illustrative reading against the green and amber lines',
  'Separating what the scenario states from what is still a hypothesis',
  'Checking for an organizational contribution, and stopping where none was supplied',
]

function isNotFound(error: Error): boolean {
  return error instanceof ApiError && error.code === 'NOT_FOUND'
}

export function InvestigationPage() {
  const { metricId = '' } = useParams()
  const back = useBackTarget({ to: '/overview', label: 'Triage' })
  const detailQuery = useQuery(`metric:${metricId}`, '', () => api.getMetric(metricId))
  const investigationQuery = useQuery(`investigation:${metricId}`, '', () => api.getInvestigation(metricId))

  if (detailQuery.data && investigationQuery.error && isNotFound(investigationQuery.error)) {
    return <NoInvestigation detail={detailQuery.data} back={back} />
  }
  const failed = detailQuery.error ?? investigationQuery.error
  if (failed && (!detailQuery.data || !investigationQuery.data)) {
    return (
      <PageError
        message={failed.message}
        onRetry={() => {
          detailQuery.retry()
          investigationQuery.retry()
        }}
      />
    )
  }
  if (metricId.startsWith('DQ-') && !investigationQuery.data && !investigationQuery.error) {
    return (
      <div className="page investigation">
        <AnalysisSimulation
          stages={DQ_STAGES}
          hold
          onDone={() => undefined}
          note="The published Cortex Agent is writing the narrative. These stages stay on screen until that response is ready. Pass rate, RAG, and counts still come from Snowflake."
        />
      </div>
    )
  }
  if (!detailQuery.data || !investigationQuery.data) return <PageLoading label="Loading investigation" />

  const investigation = investigationQuery.data
  const detail = detailQuery.data
  if ('kind' in investigation) return <DqInvestigationView key={metricId} pack={investigation} detail={detail} back={back} revealImmediately />
  return <TechInvestigationView key={metricId} investigation={investigation} detail={detail} back={back} />
}

function NoInvestigation({ detail, back }: { detail: MetricDetailResponse; back: BackTarget }) {
  const { metric } = detail
  const linkState = useLinkState(`${metric.id} investigation`)
  return (
    <div className="page page-narrow">
      <InvestigationCrumbs back={back} metricId={metric.id} />
      <section className="state-card">
        <p className="eyebrow">Investigation</p>
        <h1>
          <span className="mono">{metric.id}</span> {metric.name}
        </h1>
        <div className="row">
          <StatusBadge status={detail.reading.status} />
          <FamilyChip family={detail.family} />
        </div>
        <p className="lede">
          No planted investigation exists for this control. Its results and exceptions are on the detail page. No root-cause narrative is generated for it.
        </p>
        <div className="actions">
          <Link className="btn btn-primary" to={`/metrics/${metric.id}`} state={linkState}>
            Open {metric.id} detail
          </Link>
          <BackButton back={back} />
        </div>
      </section>
    </div>
  )
}

function TechInvestigationView({ investigation, detail, back }: { investigation: Investigation; detail: MetricDetailResponse; back: BackTarget }) {
  const { metric, reading } = detail
  const org = investigation.orgContribution
  const [revealed, setRevealed] = useState(false)

  function printReport() {
    window.print()
  }

  return (
    <div className="page investigation">
      <PageHeader
        crumbs={<InvestigationCrumbs back={back} metricId={metric.id} />}
        eyebrow={`Investigation · ${metric.domain}`}
        title={
          <>
            <span className="mono title-id">{metric.id}</span> {metric.name}
          </>
        }
        chips={
          <>
            <StatusBadge status={reading.status} />
            <FamilyChip family="technology_risk" />
            <ProvenanceChip kind="synthetic" />
            <ProvenanceChip kind="simulated" />
            <span className="fine">As of {reading.asOf ? formatDate(reading.asOf) : 'not supplied'}</span>
          </>
        }
        actions={
          <div className="row no-print">
            <BackButton back={back} />
            <button type="button" className="btn" onClick={printReport} disabled={!revealed}>
              Print / Save PDF
            </button>
          </div>
        }
      />

      {!revealed ? (
        <AnalysisSimulation stages={ANALYSIS_STAGES} onDone={() => setRevealed(true)} note="Working through a fixed sequence in the browser. This does not call Snowflake Cortex, a model, or SMARTS." />
      ) : (
        <div className="ledger-layout">
          <div className="ledger">
            <section className="ledger-item" aria-labelledby="summary-title">
              <div className="card-head">
                <h2 id="summary-title">Summary</h2>
                <ProvenanceChip kind="simulated" />
              </div>
              <p className="definition-label">Provisional definition — pending client validation</p>
              <p>{metric.provisionalDefinition}</p>
              <p>{investigation.summary.text}</p>
              <p className="fine">{investigation.summary.disclaimer}</p>
              <p className="fine">Simulated analysis finished in the browser. This report was not produced by Snowflake Cortex.</p>
            </section>

            <div className="two-up">
              <section className="ledger-item">
                <h3>What changed</h3>
                <p>{investigation.whatChanged}</p>
              </section>
              <section className="ledger-item">
                <h3>Why it matters</h3>
                <p>{investigation.whyItMatters}</p>
              </section>
            </div>

            <section className="ledger-item" aria-labelledby="causal-title">
              <h2 id="causal-title">Causal assessment</h2>
              <ul className="ledger-list">
                {investigation.signals.map((signal) => (
                  <li key={signal.id} className={`ledger-entry entry-${signal.classification}`}>
                    <div className="row">
                      <EvidenceTag kind={signal.classification === 'hypothesis' ? 'hypothesis' : 'fact'} />
                      <h3>{signal.title}</h3>
                    </div>
                    <p>{signal.statement}</p>
                    <Disclosure summary="Evidence and gaps">
                      <p>
                        <strong>Evidence on hand. </strong>
                        {signal.evidenceNote}
                      </p>
                      <h4>Still to validate</h4>
                      <ul className="tight-list">
                        {signal.gaps.map((gap) => (
                          <li key={gap}>{gap}</li>
                        ))}
                      </ul>
                    </Disclosure>
                  </li>
                ))}
              </ul>
            </section>

            <section className="ledger-item" aria-labelledby="path-title">
              <h2 id="path-title">Path to validate</h2>
              <p className="provenance">{investigation.pathToGreen.disclaimer}</p>
              <div className="two-up">
                <div>
                  <h3>Checks</h3>
                  <ol className="tight-list">
                    {investigation.pathToGreen.checks.map((check) => (
                      <li key={check}>{check}</li>
                    ))}
                  </ol>
                </div>
                <div>
                  <div className="row">
                    <h3>Possible actions</h3>
                    <EvidenceTag kind="recommendation" />
                  </div>
                  <ul className="tight-list">
                    {investigation.pathToGreen.possibleActions.map((action) => (
                      <li key={action}>{action}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>

            <section className="ledger-item" aria-labelledby="timeline-title">
              <h2 id="timeline-title">Breach timeline and trend</h2>
              <p className="provenance">{investigation.timelineNote}</p>
              <ol className="timeline">
                {investigation.timeline.map((event) => (
                  <li key={`${event.date ?? 'undated'}-${event.label}`}>
                    <div className="row">
                      <time className="num">{event.date ? formatDate(event.date) : 'Date not supplied'}</time>
                      <EvidenceTag kind={event.kind === 'scenario_fact' ? 'fact' : 'recommendation'} label={event.provenanceLabel} />
                    </div>
                    <p>{event.label}</p>
                  </li>
                ))}
              </ol>
              {detail.trend.length > 0 && (
                <TrendChart
                  points={detail.trend}
                  unit={metric.unit}
                  thresholds={metric.thresholds}
                  breachDate={reading.breachedOn}
                  caption={detail.trendCaption}
                  family="technology_risk"
                  frequency={metric.frequency}
                />
              )}
            </section>
          </div>

          <aside className="sticky-rail" aria-label="Context">
            <section className="rail-card">
              <h2>Threshold position</h2>
              <p className="fine num">
                {reading.value == null ? 'No reading' : `${formatNumber(reading.value, metric.unit)} synthetic`} · control{' '}
                <span className="mono">{metric.controlId}</span>
              </p>
              <ThresholdScale direction={metric.direction} unit={metric.unit} thresholds={metric.thresholds} value={reading.value} />
            </section>
            <section className="rail-card">
              <div className="card-head">
                <h2>Organizational contribution</h2>
                {org.availability === 'available' ? <ProvenanceChip kind="synthetic" label="Illustrative" /> : <EvidenceTag kind="not_supplied" />}
              </div>
              {org.availability === 'available' ? (
                <>
                  <HotspotChart groups={org.groups} unit={metric.unit} shareLabel={org.shareLabel} />
                  <Disclosure summary="Method">
                    <p className="fine">{org.methodNote}</p>
                  </Disclosure>
                </>
              ) : (
                <p className="provenance">{org.reason}</p>
              )}
            </section>
            <section className="rail-card">
              <Disclosure summary="Data lineage and provenance">
                <dl className="lineage">
                  {investigation.lineage.map((item) => (
                    <div key={item.label}>
                      <dt>{item.label}</dt>
                      <dd>{item.detail}</dd>
                    </div>
                  ))}
                </dl>
              </Disclosure>
            </section>
            <section className="rail-card rail-note">
              <h2>Data still to verify</h2>
              <p>{investigation.validationNote}</p>
              <p className="fine">Owner function: {displayOrMissing(metric.ownerFunction)} · Control statement: {displayOrMissing(metric.controlStatement)}</p>
            </section>
          </aside>
        </div>
      )}
    </div>
  )
}
