import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { DqInvestigation, MetricDetailResponse } from '../../backend/contracts/types'
import { StatusBadge } from '../../components/StatusBadge'
import { ThresholdScale } from '../../components/ThresholdScale'
import { TrendChart } from '../../components/TrendChart'
import { PageHeader } from '../../components/ui/PageHeader'
import { EvidenceTag, FamilyChip, ProvenanceChip, type Evidence } from '../../components/ui/ProvenanceChip'
import { formatDate, recoveredLine } from '../../domain/format'
import { useLinkState, type BackTarget } from '../../hooks/useOrigin'
import { AnalysisSimulation } from './AnalysisSimulation'
import { BackButton, InvestigationCrumbs } from './InvestigationChrome'

export const DQ_STAGES = [
  'Reading the control definition, check logic and thresholds from the workbook',
  'Loading the supplied pass-rate results and locating the first red date',
  'Checking whether a desk split and exception rows were supplied',
  'Linking change and incident events by control ID, without treating them as causes',
  'Tagging each line as established, hypothesis or not supplied',
]

export function DqInvestigationView({
  pack,
  detail,
  back,
  revealImmediately = false,
}: {
  pack: DqInvestigation
  detail: MetricDetailResponse
  back: BackTarget
  revealImmediately?: boolean
}) {
  const [revealed, setRevealed] = useState(revealImmediately)
  const { metric, reading } = detail
  const workbook = detail.workbook
  const linkState = useLinkState(`${metric.id} investigation`)
  const recovered = reading.status === 'green' && Boolean(workbook?.firstRed)
  const statusLine =
    recovered && workbook && reading.asOf
      ? recoveredLine({ firstRed: workbook.firstRed, lastRed: workbook.lastRed, asOf: reading.asOf })
      : `${reading.value == null ? '' : `${reading.value.toFixed(2)}%`} on ${formatDate(reading.asOf)}${reading.breachedOn ? ` · first red ${formatDate(reading.breachedOn)}` : ''}`
  const ledger: Array<{ kind: Evidence; label?: string; text: string }> = [
    ...pack.established.map((text) => ({ kind: 'established' as const, text })),
    ...pack.hypothesis.map((text) => ({ kind: 'hypothesis' as const, label: 'Supplied hypothesis', text })),
    ...pack.notSupplied.map((text) => ({ kind: 'not_supplied' as const, text })),
  ]
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
            <ProvenanceChip kind="workbook" label={`Workbook snapshot · ${formatDate(reading.asOf)}`} />
          </>
        }
        actions={<BackButton back={back} />}
      />

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
          <section className="ledger-item" aria-labelledby="ledger-title">
            <div className="card-head">
              <h2 id="ledger-title">Evidence ledger</h2>
              <span className="fine">Each line is tagged by what supports it</span>
            </div>
            <ul className="ledger-list">
              {ledger.map((line) => (
                <li key={line.text} className={`ledger-entry entry-${line.kind}`}>
                  <EvidenceTag kind={line.kind} label={line.label} />
                  <p>{line.text}</p>
                </li>
              ))}
            </ul>
          </section>

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

          <section className="ledger-item" aria-labelledby="validate-title">
            <h2 id="validate-title">Path to validation</h2>
            <p className="fine">Built only from the supplied commentary path and the gaps listed above.</p>
            <ul className="tight-list">
              {paths.map((path) => (
                <li key={path}>
                  <EvidenceTag kind="hypothesis" label="Commentary path" /> {path}
                </li>
              ))}
              {pack.notSupplied.map((line) => (
                <li key={line}>
                  <EvidenceTag kind="not_supplied" /> {line}
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
