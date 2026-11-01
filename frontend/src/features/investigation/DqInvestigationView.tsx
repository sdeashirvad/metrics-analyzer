import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { DqInvestigation, MetricDetailResponse } from '../../backend/contracts/types'
import { StatusBadge } from '../../components/StatusBadge'
import { ThresholdScale } from '../../components/ThresholdScale'
import { TrendChart } from '../../components/TrendChart'
import { Disclosure } from '../../components/ui/Disclosure'
import { PageHeader } from '../../components/ui/PageHeader'
import { EvidenceTag, FamilyChip, ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { formatDate, recoveredLine } from '../../domain/format'
import { useLinkState, type BackTarget } from '../../hooks/useOrigin'
import { CacheChip } from '../../components/ui/CacheChip'
import { estimateFor } from '../../state/etaStore'
import { AnalysisSimulation } from './AnalysisSimulation'
import { investigationAction } from './openFlow'
import { BackButton, InvestigationCrumbs } from './InvestigationChrome'

export const DQ_STAGES = [
  'Reading the control definition, check logic and thresholds from the workbook',
  'Loading the supplied pass-rate results and locating the first red date',
  'Checking whether a desk split and exception rows were supplied',
  'Linking change and incident events by control ID, without treating them as causes',
  'Tagging each line as established, hypothesis or not supplied',
]

function withoutPrefix(lines: string[], prefix: string): string | undefined {
  const found = lines.find((line) => line.startsWith(prefix))
  return found ? found.slice(prefix.length).trim() : undefined
}

function presentation(pack: DqInvestigation) {
  const folded = pack.hypothesis
  return {
    summary: pack.summary || pack.established[0] || pack.name,
    whatChanged: pack.whatChanged || pack.established[1] || pack.established[0] || 'No separate movement line was stored.',
    whyItMatters: pack.whyItMatters || withoutPrefix(folded, 'Implications:') || 'No separate implication was stored for this investigation.',
    hypotheses: pack.hypotheses || folded.filter((line) => !line.startsWith('Implications:') && !line.startsWith('Validation step:')),
    steps: pack.validationSteps || folded.filter((line) => line.startsWith('Validation step:')).map((line) => line.slice('Validation step:'.length).trim()),
  }
}

export function DqInvestigationView({
  pack,
  detail,
  back,
  revealImmediately = false,
  cached = false,
  notice,
  onRunAgain,
  onResume,
  executing = false,
  resumable = false,
  etaLabel = null,
}: {
  pack: DqInvestigation
  detail: MetricDetailResponse
  back: BackTarget
  revealImmediately?: boolean
  cached?: boolean
  notice?: string
  onRunAgain?: () => void
  onResume?: () => void
  executing?: boolean
  resumable?: boolean
  etaLabel?: string | null
}) {
  const [revealed, setRevealed] = useState(revealImmediately)
  const [confirming, setConfirming] = useState(false)
  const [refreshSent, setRefreshSent] = useState(false)
  const action = investigationAction({ executing, resumable })
  useEffect(() => {
    if (!executing) setRefreshSent(false)
  }, [executing])
  const timing = estimateFor('INVESTIGATION')?.label ?? etaLabel
  const { metric, reading } = detail
  const workbook = detail.workbook
  const linkState = useLinkState(`${metric.id} investigation`)
  const recovered = reading.status === 'green' && Boolean(workbook?.firstRed)
  const statusLine =
    recovered && workbook && reading.asOf
      ? recoveredLine({ firstRed: workbook.firstRed, lastRed: workbook.lastRed, asOf: reading.asOf })
      : `${reading.value == null ? '' : `${reading.value.toFixed(2)}%`} on ${formatDate(reading.asOf)}${reading.breachedOn ? ` · first red ${formatDate(reading.breachedOn)}` : ''}`
  const story = presentation(pack)
  const events = pack.notes.events.map((event) => ({ id: event.id, date: event.date, label: `${event.type}: ${event.description}` }))
  const maxFailed = Math.max(...pack.desks.rows.map((row) => row.failed), 1)
  const paths = [...new Set(pack.notes.commentary.map((note) => note.path))]

  return (
    <div className="page investigation">
      <PageHeader
        crumbs={<InvestigationCrumbs back={back} metricId={metric.id} />}
        eyebrow={`Investigation · ${pack.dimension}`}
        title={
          <>
            <span className="mono title-id">{metric.id}</span> {pack.name}
          </>
        }
        chips={
          <>
            <StatusBadge status={reading.status} />
            <span className="status-line num">{statusLine}</span>
            <FamilyChip family="data_quality" />
            <ProvenanceChip kind="workbook" label={`Snowflake snapshot · ${formatDate(reading.asOf)}`} />
            {cached && <CacheChip />}
          </>
        }
        actions={
          <div className="row no-print">
            <BackButton back={back} />
            {onRunAgain && (
              <button
                type="button"
                className="btn"
                disabled={action.kind === 'disabled' || refreshSent || confirming}
                onClick={() => {
                  if (action.kind === 'resume') {
                    setRefreshSent(true)
                    onResume?.()
                    return
                  }
                  setConfirming(true)
                }}
              >
                {action.label}
              </button>
            )}
          </div>
        }
      />

      {confirming && onRunAgain && action.kind === 'confirm-new' && (
        <div className="callout confirm-run" role="region" aria-label="Confirm a new investigation">
          <p>
            Run a new investigation? {timing ? `${timing}. ` : ''}The investigation on screen stays available until the new one finishes.
          </p>
          <div className="actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setConfirming(false)
                setRefreshSent(true)
                onRunAgain()
              }}
            >
              Run new investigation
            </button>
            <button type="button" className="btn" onClick={() => setConfirming(false)}>
              Keep this one
            </button>
          </div>
        </div>
      )}

      {notice && <p className="fine">{notice}</p>}

      {!revealed ? (
        <AnalysisSimulation stages={DQ_STAGES} onDone={() => setRevealed(true)} note="The published Cortex Agent is writing the narrative. Pass rate, RAG, counts, and dates stay on the Snowflake rows." />
      ) : (
        <>
      {pack.discrepancy && (
        <div className="callout-warn discrepancy" role="note">
          <strong>Sources disagree. </strong>
          {pack.discrepancy}
        </div>
      )}

      <div className="ledger-layout">
        <div className="ledger">
          <section className="ledger-item" aria-labelledby="summary-title">
            <div className="card-head">
              <h2 id="summary-title">Summary</h2>
              <EvidenceTag kind="established" />
            </div>
            <p>{story.summary}</p>
            <p className="fine">{pack.disclaimer}</p>
          </section>

          <div className="two-up">
            <section className="ledger-item">
              <h3>What changed</h3>
              <p>{story.whatChanged}</p>
            </section>
            <section className="ledger-item">
              <h3>Why it matters</h3>
              <p>{story.whyItMatters}</p>
            </section>
          </div>

          <section className="ledger-item" aria-labelledby="facts-title">
            <div className="card-head">
              <h2 id="facts-title">Established facts</h2>
              <EvidenceTag kind="established" />
            </div>
            <ul className="ledger-list">
              {pack.established.map((text) => (
                <li key={text} className="ledger-entry entry-established">
                  <EvidenceTag kind="established" />
                  <p>{text}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="ledger-item" aria-labelledby="hypothesis-title">
            <div className="card-head">
              <h2 id="hypothesis-title">Hypotheses</h2>
              <EvidenceTag kind="hypothesis" label="Not established" />
            </div>
            {story.hypotheses.length === 0 ? (
              <p className="fine">The agent did not return a hypothesis.</p>
            ) : (
              <ul className="ledger-list">
                {story.hypotheses.map((text) => (
                  <li key={text} className="ledger-entry entry-hypothesis">
                    <EvidenceTag kind="hypothesis" />
                    <p>{text}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {pack.readme && (
            <section className="ledger-item" aria-labelledby="story-title">
              <div className="card-head">
                <h2 id="story-title">Planted-story context</h2>
                <EvidenceTag kind="hypothesis" label="Supplied context" />
              </div>
              <p>{pack.readme}</p>
              <p className="fine">This is the stored story text. It is not an additional measurement.</p>
            </section>
          )}

          <section className="ledger-item" aria-labelledby="dq-trend-title">
            <div className="card-head">
              <h2 id="dq-trend-title">Supplied results</h2>
              <ProvenanceChip kind="workbook" />
            </div>
            <TrendChart
              points={detail.trend}
              unit={metric.unit}
              thresholds={metric.thresholds}
              breachDate={reading.breachedOn}
              caption={detail.trendCaption}
              family="data_quality"
              frequency={metric.frequency}
              events={events}
            />
          </section>

          <section className="ledger-item" aria-labelledby="desk-title">
            <div className="card-head">
              <h2 id="desk-title">Desk contribution · {pack.desks.date ? formatDate(pack.desks.date) : 'latest date'}</h2>
            </div>
            <p className="fine">Failure volume, not lowest pass rate.</p>
            {pack.desks.available ? (
              <ul className="volume-bars">
                {pack.desks.rows.map((row) => (
                  <li key={row.deskId}>
                    <span className="vb-label">{row.deskName}</span>
                    <span className="vb-track" aria-hidden="true">
                      <span style={{ width: `${(row.failed / maxFailed) * 100}%` }} />
                    </span>
                    <span className="vb-value num">{row.failed.toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="provenance">{pack.desks.reason}</p>
            )}
          </section>

          <section className="ledger-item" aria-labelledby="commentary-title">
            <h2 id="commentary-title">Commentary</h2>
            {pack.notes.commentary.length === 0 ? (
              <p className="fine">No analyst commentary was supplied for this control.</p>
            ) : (
              <ul className="evidence-list">
                {pack.notes.commentary.map((note) => (
                  <li key={`${note.date}-${note.cause}`}>
                    <div className="row">
                      <strong>{formatDate(note.date)}</strong>
                      <span className="muted">{note.author}</span>
                      <EvidenceTag kind="hypothesis" label="Supplied commentary" />
                    </div>
                    <p>{note.text}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="ledger-item" aria-labelledby="gaps-title">
            <h2 id="gaps-title">Evidence and gaps</h2>
            <Disclosure summary="Show evidence limits">
              <ul className="ledger-list">
                {pack.notSupplied.map((text) => (
                  <li key={text} className="ledger-entry entry-not_supplied">
                    <EvidenceTag kind="not_supplied" />
                    <p>{text}</p>
                  </li>
                ))}
                {!pack.desks.available && (
                  <li className="ledger-entry entry-not_supplied">
                    <EvidenceTag kind="not_supplied" />
                    <p>{pack.desks.reason}</p>
                  </li>
                )}
                {paths.length === 0 && <li className="fine">No commentary path was supplied.</li>}
              </ul>
            </Disclosure>
          </section>

          <section className="ledger-item" aria-labelledby="validate-title">
            <h2 id="validate-title">Path to validate</h2>
            <p className="fine">Steps returned by the agent, plus any commentary path stored with this control.</p>
            <ul className="tight-list">
              {story.steps.map((step) => (
                <li key={step}>
                  <EvidenceTag kind="hypothesis" label="Validation step" /> {step}
                </li>
              ))}
              {story.steps.length === 0 && <li className="fine">No validation step was returned.</li>}
              {paths.map((path) => (
                <li key={path}>
                  <EvidenceTag kind="hypothesis" label="Commentary path" /> {path}
                </li>
              ))}
            </ul>
          </section>

          <p className="provenance">{pack.disclaimer}</p>
        </div>

        <aside className="sticky-rail" aria-label="Context">
          <section className="rail-card">
            <h2>Threshold position</h2>
            <ThresholdScale direction={metric.direction} unit={metric.unit} thresholds={metric.thresholds} value={reading.value} family="data_quality" />
          </section>
          <section className="rail-card">
            <h2>Exceptions</h2>
            <dl className="kv">
              <dt>Linked rows</dt>
              <dd className="num">{pack.exceptions.total.toLocaleString()}</dd>
              <dt>Open</dt>
              <dd className="num">{pack.exceptions.open.toLocaleString()}</dd>
              <dt>Oldest open</dt>
              <dd className="num">{pack.exceptions.oldestAge == null ? 'None open' : `${pack.exceptions.oldestAge} days`}</dd>
            </dl>
            <Link className="more-link" to={`/metrics/${metric.id}?tab=exceptions`} state={linkState}>
              Open the exceptions tab
            </Link>
          </section>
          {workbook && (
            <section className="rail-card">
              <h2>Check logic (workbook)</h2>
              <p className="fine">{workbook.checkLogic}</p>
              <dl className="kv">
                <dt>Source system</dt>
                <dd>{workbook.sourceSystem}</dd>
                <dt>Report</dt>
                <dd>{workbook.report}</dd>
                <dt>Failed / total</dt>
                <dd className="num">
                  {workbook.failed.toLocaleString()} / {workbook.total.toLocaleString()}
                </dd>
              </dl>
            </section>
          )}
          <section className="rail-card">
            <Disclosure summary="Data lineage and provenance">
              <dl className="lineage">
                <div>
                  <dt>Measurements</dt>
                  <dd>Pass rate, RAG, counts, and dates are the Snowflake snapshot loaded from the workbook. They are not a live SMARTS feed.</dd>
                </div>
                <div>
                  <dt>Narrative</dt>
                  <dd>Summary implications, hypotheses, and validation steps come from the published Data Quality agent. Facts and hypotheses are labeled separately.</dd>
                </div>
                <div>
                  <dt>Generated</dt>
                  <dd>{cached ? 'Cached result' : 'New result'}{pack.generatedAt ? ` · ${formatDate(pack.generatedAt)}` : ''}</dd>
                </div>
              </dl>
            </Disclosure>
          </section>
          <section className="rail-card rail-note">
            <h2>Linked events</h2>
            {pack.notes.events.length ? (
              <ul className="tight-list">
                {pack.notes.events.map((event) => (
                  <li key={event.id}>
                    <span className="mono">{event.id}</span> {formatDate(event.date)} · {event.type}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="fine">No change or incident rows list this control.</p>
            )}
            <p className="fine">Linked by control ID, not causal.</p>
          </section>
        </aside>
      </div>
        </>
      )}
    </div>
  )
}
