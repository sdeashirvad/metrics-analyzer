import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../backend/services'
import { EvidenceTag, ProvenanceChip, type Evidence, type Provenance } from '../../components/ui/ProvenanceChip'
import { PageHeader } from '../../components/ui/PageHeader'
import { PageError, PageLoading } from '../../components/ui/SectionState'
import { StatusBadge } from '../../components/StatusBadge'
import { formatDate } from '../../domain/format'
import { useQuery } from '../../hooks/useQuery'
import { ENVIRONMENT_NOTICE } from '../../components/EnvironmentBar'

const EVIDENCE: Array<{ kind: Evidence; meaning: string }> = [
  { kind: 'fact', meaning: 'A fact written into the synthetic Technology Risk scenario, such as a breach date. It is part of the story, not a live observation.' },
  { kind: 'workbook', meaning: 'A Data Quality result stored in Snowflake from the supplied workbook. It is not a live SMARTS feed.' },
  { kind: 'established', meaning: 'Follows directly from supplied results or definitions, for example a threshold comparison.' },
  { kind: 'hypothesis', meaning: 'A possible explanation supplied with the scenario or workbook. It has not been validated.' },
  { kind: 'linked', meaning: 'An event tied to a control by control ID. A nearby date is not treated as a cause.' },
  { kind: 'recommendation', meaning: 'An illustrative next step written for the demonstration. It is not an instruction.' },
  { kind: 'not_supplied', meaning: 'The source does not provide this. The app shows it as unavailable rather than inferring a value.' },
]

const SOURCES: Array<{ kind: Provenance; meaning: string }> = [
  { kind: 'simulated', meaning: 'The Technology Risk investigation is an illustrative scenario served by the API. It is not a Snowflake or Cortex result.' },
  { kind: 'proposed', meaning: 'Architecture elements that are drawn but not built.' },
]

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="gloss-term">
      <dt>{term}</dt>
      <dd>{children}</dd>
    </div>
  )
}

export function GlossaryPage() {
  const data = useQuery('glossary', '', async () => {
    const [tech, dq, techList, dqList, overview] = await Promise.all([
      api.getMetric('M001'),
      api.getMetric('DQ-025'),
      api.listMetrics({ family: 'technology_risk', pageSize: 1 }),
      api.listMetrics({ family: 'data_quality', pageSize: 1 }),
      api.getOverview(),
    ])
    return { tech, dq, techList, dqList, overview }
  })

  if (data.error && !data.data) return <PageError message={data.error.message} onRetry={data.retry} />
  if (!data.data) return <PageLoading label="Loading the glossary" />
  const { tech, dq, techList, dqList, overview } = data.data
  const dqOverview = overview.dataQuality
  const techDomains = techList.facets.domains
  const dqDimensions = dqList.facets.domains

  return (
    <div className="page glossary page-narrow">
      <PageHeader title="Glossary & conventions" subtitle="How to read identifiers, statuses and source labels. Technology Risk and Data Quality use different sources." />

      <nav className="gloss-toc" aria-label="On this page">
        <a href="#gloss-ids">Identifiers</a>
        <a href="#gloss-terms">Terms</a>
        <a href="#gloss-evidence">Evidence tags</a>
        <a href="#gloss-sources">Data sources</a>
        <a href="#gloss-missing">Missing readings</a>
        <a href="#gloss-demo">Demo environment</a>
      </nav>

      <section className="card" id="gloss-ids" aria-labelledby="gloss-ids-title">
        <h2 id="gloss-ids-title">Identifiers</h2>
        <dl className="gloss-list">
          <Term term="M-numbers · Technology Risk metrics">
            Identifiers such as <Link to={`/metrics/${tech.metric.id}`}>{tech.metric.id}</Link> ({tech.metric.name}, {tech.metric.domain}). The register holds {techList.total} Technology
            Risk metrics across {techDomains.length} domains: {techDomains.join(', ')}. Readings are illustrative scenario data.
          </Term>
          <Term term="DQ-numbers · Data Quality controls">
            Identifiers such as <Link to={`/metrics/${dq.metric.id}`}>{dq.metric.id}</Link> ({dq.metric.name}, {dq.metric.domain}). The workbook defines {dqList.total} controls across{' '}
            {dqDimensions.length} dimensions: {dqDimensions.join(', ')}. Results are read from Snowflake.
          </Term>
          <Term term="Why two series">
            The two books are measured differently and come from different sources, so their counts and pass rates are never added together or averaged.
          </Term>
          <Term term="Full records">
            This page is a reading guide. Every metric and control, with its thresholds, owner and frequency, is listed in the <Link to="/metrics">Metric register</Link>.
          </Term>
        </dl>
      </section>

      <section className="card" id="gloss-terms" aria-labelledby="gloss-terms-title">
        <h2 id="gloss-terms-title">Terms</h2>
        <dl className="gloss-list">
          <Term term="Metric and control">
            A metric is a measured quantity with thresholds. In Data Quality each metric is a control: a named check on a data field. Both appear in the register.
          </Term>
          <Term term="RAG status">
            <span className="gloss-badges">
              <StatusBadge status="red" /> <StatusBadge status="amber" /> <StatusBadge status="green" /> <StatusBadge status="insufficient_data" />
            </span>{' '}
            Each metric has a green and an amber threshold and a direction (higher or lower is better). Green meets the green threshold, amber falls between the two, and red is
            beyond the amber threshold. Data Quality uses the RAG supplied in the workbook; Technology Risk status is derived from its synthetic reading.
          </Term>
          <Term term="Pass rate">
            For Data Quality, the percentage of records that passed a control on a date. For example, {dq.metric.id} reads {dq.reading.value?.toFixed(2)}% on {formatDate(dq.reading.asOf ?? '')} against a green
            threshold of {dq.metric.thresholds.green}%.
          </Term>
          <Term term="First red and breach date">
            First red is the earliest date a Data Quality control shows red in the supplied results. Breach date is the date a Technology Risk reading first crossed its threshold in the scenario.
            Recovered controls show both the red dates and the date they returned to green.
          </Term>
          <Term term="Exception">
            A record-level failure listed in the workbook. The snapshot has {dqOverview.openExceptions.toLocaleString()} open exceptions. Technology Risk has no exception records.
          </Term>
          <Term term="Desk breakdown">
            Failed-record volume by trading desk for a control on a chosen date. The workbook supplies it for {dqOverview.coverage.deskControls} of {dqOverview.controls} controls. The bars show volume, not
            the lowest pass rate.
          </Term>
          <Term term="Hotspot">
            Where a problem concentrates. For Data Quality it is desk failure volume. For Technology Risk it is an illustrative organizational concentration supplied only for M001 and M003.
          </Term>
          <Term term="Triage and investigation">
            <Link to="/overview">Triage</Link> lists the at-risk metrics and controls. A Technology Risk investigation is an illustrative scenario. A Data Quality investigation is drafted from Snowflake facts, checked, and cached. Controls without that investigation show their detail page only.
          </Term>
        </dl>
      </section>

      <section className="card" id="gloss-evidence" aria-labelledby="gloss-evidence-title">
        <h2 id="gloss-evidence-title">Evidence tags</h2>
        <p className="fine">Investigation lines carry a tag so scenario facts, workbook results, hypotheses and recommendations stay distinct.</p>
        <dl className="gloss-list gloss-tags">
          {EVIDENCE.map((item) => (
            <div key={item.kind} className="gloss-term">
              <dt>
                <EvidenceTag kind={item.kind} />
              </dt>
              <dd>{item.meaning}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card" id="gloss-sources" aria-labelledby="gloss-sources-title">
        <h2 id="gloss-sources-title">Data sources</h2>
        <p>
          Technology Risk readings, trends and hotspots are illustrative values written for the scenario. They are served by the application API and are not Snowflake or Cortex results. Data Quality results, exceptions, events and commentary are stored in Snowflake from the
          supplied workbook, not from a live SMARTS feed. Narrative text on a completed Data Quality investigation is written by the published Cortex agent from those stored facts, then checked against the retrieved figures. A facts-only view is not a Cortex analysis. The two books are never mixed or added together.
        </p>
        <dl className="gloss-list gloss-tags">
          {SOURCES.map((item) => (
            <div key={item.kind} className="gloss-term">
              <dt>
                <ProvenanceChip kind={item.kind} />
              </dt>
              <dd>{item.meaning}</dd>
            </div>
          ))}
        </dl>
        <p className="fine">Where a result is shown, its own date is given next to it.</p>
      </section>

      <section className="card" id="gloss-missing" aria-labelledby="gloss-missing-title">
        <h2 id="gloss-missing-title">A missing reading is not green</h2>
        <p>
          A metric with no reading is shown as <StatusBadge status="insufficient_data" /> and is not counted as green. Absence of a value means the metric could not be evaluated, not that
          it passed. Dashboard counts therefore show not evaluated as its own segment.
        </p>
      </section>

      <section className="card" id="gloss-demo" aria-labelledby="gloss-demo-title">
        <h2 id="gloss-demo-title">Demo environment</h2>
        <p className="env-quote">{ENVIRONMENT_NOTICE}</p>
        <p>
          Technology Risk is illustrative scenario data served by the API. It does not call SMARTS or Snowflake Cortex. Data Quality calls the same API, which reads Snowflake and, for a new
          investigation, the published Cortex agent. The Architecture page shows what is running and what is only planned.
        </p>
      </section>
    </div>
  )
}
