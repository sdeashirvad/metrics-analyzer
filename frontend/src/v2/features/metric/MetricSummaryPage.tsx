import { Link, useParams } from 'react-router-dom'
import { getMetric, getMetricBreakdowns } from '../../api/portfolio'
import type { MetricBreakdownDimension } from '../../api/types'
import { BarList } from '../../components/charts/Charts'
import { Card, Dash, Provisional, QueryPanel, RagPill } from '../../components/present'
import { ScopeBar } from '../../components/ScopeBar'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatInt, formatMonth, formatPercent, formatPp, labelOf } from '../../format'
import { useApiQuery } from '../../hooks/useApiQuery'
import { useBackTarget, useLinkState } from '../../hooks/useOrigin'
import { useScopeFilters } from '../../hooks/useScopeFilters'
import { scopeKey, scopedTo } from '../../scopePath'
import { AskAgentLink } from '../../components/ui/AskAgentLink'
import { MetricFunnel } from './MetricFunnel'
import { MetricTrendCard } from './MetricTrendCard'
import { Skeleton } from '../../components/Skeleton'

const DIMENSIONS: MetricBreakdownDimension[] = ['org', 'legalEntity', 'tier', 'risk', 'lifecycle', 'complianceReason', 'testStatus']

function isDimension(value: string | null): value is MetricBreakdownDimension {
  return DIMENSIONS.includes(value as MetricBreakdownDimension)
}

export function MetricSummaryPage() {
  const { metricId = '' } = useParams()
  const { filters, params, replace } = useScopeFilters()
  const back = useBackTarget({ to: scopedTo('/register', filters), label: 'Back' })
  const linkState = useLinkState('Back')
  const breakdownParam = params.get('breakdown')
  const dimension: MetricBreakdownDimension = isDimension(breakdownParam) ? breakdownParam : 'org'
  const level = params.get('breakdownLevel') === '2' ? 2 : 1
  const key = `${metricId}|${scopeKey(filters)}`
  const summary = useApiQuery('metric', key, () => getMetric(metricId, filters), { keep: metricId })
  const breakdown = useApiQuery(
    'metric-breakdown',
    `${key}|${dimension}|${level}`,
    () => getMetricBreakdowns(metricId, filters, { dimension, level: dimension === 'org' ? level : undefined }),
    { keep: `${metricId}|${dimension}|${level}` },
  )
  const investigation = scopedTo(`/investigate/metrics/${encodeURIComponent(metricId)}`, filters)

  return (
    <div className="page">
      <PageHeader
        crumbs={
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link to={back.to} state={back.state} onClick={back.go}>
              Back
            </Link>
            {' · '}
            <Link to={scopedTo('/register', filters)}>Register</Link>
            {' / '}
            <span aria-current="page">{metricId}</span>
          </nav>
        }
        eyebrow="Metric summary"
        title={metricId}
        subtitle="Current result, how it is calculated, and where it concentrates."
        chips={
          summary.data && (
            <>
              <RagPill rag={summary.data.preview.rag} />
              <span className="chip">{formatMonth(summary.data.preview.month)}</span>
              <Provisional id="PD-01" of="metric rate band" />
            </>
          )
        }
        actions={
          <>
            <Link className="btn btn-primary" to={investigation} state={linkState}>
              Open Investigation
            </Link>
            <AskAgentLink />
          </>
        }
      >
        <ScopeBar mode="compact" />
      </PageHeader>
      <QueryPanel
        query={summary}
        skeleton={
          <div className="sk-stack">
            <Skeleton shape="kpis" label={`Loading the ${metricId} summary`} />
            <Skeleton shape="investigation" label="Loading the calculation" />
          </div>
        }
      >
        {(data) => (
          <div className="stack">
            {data.provisional.length > 0 && (
              <details className="context-fold">
                <summary>How this rate is calculated</summary>
                <ul className="list">
                  {data.provisional.map((item) => (
                    <li key={item.definitionId}>
                      <Link to={`/definitions#${item.definitionId}`}>{item.definitionId}</Link>
                      <span className="grow">{item.statement}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <div className="grid g4">
              <article className="kpi">
                <div className="kpi-label">
                  Rate <Provisional id="PD-01" of="rate card" />
                </div>
                <div className="kpi-value">
                  <Dash value={formatPercent(data.preview.rate.rate)} /> <RagPill rag={data.preview.rag} />
                </div>
                <p className="fine">
                  {formatInt(data.preview.rate.numerator)} / {formatInt(data.preview.rate.denominator)}
                </p>
                <p className="kpi-delta">
                  <Dash value={formatPp(data.preview.rate.deltaPp)} />
                </p>
              </article>
              <article className="kpi">
                <div className="kpi-label">Applications</div>
                <div className="kpi-value num">{formatInt(data.preview.coverage.applications)}</div>
              </article>
              <article className="kpi">
                <div className="kpi-label">Non-compliant rows</div>
                <div className="kpi-value num">{formatInt(data.preview.compliance.nonCompliant)}</div>
              </article>
              <article className="kpi">
                <div className="kpi-label">
                  Denominator <Provisional of="denominator scope" />
                </div>
                <div className="kpi-value" style={{ fontSize: 18 }}>
                  {labelOf(data.preview.definition.denominatorScope)}
                </div>
              </article>
            </div>
            <Card title="Calculation">
              <p>{data.calculation.formula}</p>
              <ul className="list">
                {data.calculation.steps.map((step) => (
                  <li key={step.label}>
                    <span className="grow">
                      {step.label}
                      {step.note && <span className="fine"> {step.note}</span>}
                    </span>
                    <span className="num">{step.value == null ? '—' : formatInt(step.value)}</span>
                  </li>
                ))}
              </ul>
              <p className="fine">
                Not applicable {formatInt(data.calculation.excludedRows.notApplicable)} · Pending excluded {formatInt(data.calculation.excludedRows.pendingExcluded)} · Pending
                included {formatInt(data.calculation.excludedRows.pendingIncluded)}
              </p>
            </Card>
            <MetricFunnel compliance={data.preview.compliance} testing={data.preview.testing} />
          </div>
        )}
      </QueryPanel>
      <MetricTrendCard metricId={metricId} filters={filters} />
      <Card
        title="Breakdown"
        action={
          <label className="field">
            <span className="sr-only">Breakdown</span>
            <select
              value={dimension}
              onChange={(event) => replace({ breakdown: event.target.value === 'org' ? null : event.target.value, appsPage: null })}
            >
              {DIMENSIONS.map((item) => (
                <option key={item} value={item}>
                  {labelOf(item)}
                </option>
              ))}
            </select>
          </label>
        }
      >
        {dimension === 'org' && (
          <div className="seg" role="group" aria-label="Organisation level">
            <button type="button" className={level === 1 ? 'on' : ''} onClick={() => replace({ breakdownLevel: null })}>
              Level 1
            </button>
            <button type="button" className={level === 2 ? 'on' : ''} onClick={() => replace({ breakdownLevel: '2' })}>
              Level 2
            </button>
          </div>
        )}
        <p className="fine">Bar length is non-compliant applications, scaled to the largest group. The percent is the provisional rate.</p>
        <QueryPanel query={breakdown} skeleton={<Skeleton shape="bars" rows={6} label="Loading the breakdown" />}>
          {(data) => (
            <BarList
              items={data.items.map((item) => ({
                key: item.key,
                label: item.label,
                value: item.nonCompliantApplications,
                note: (
                  <>
                    {formatInt(item.nonCompliantApplications)} · <Dash value={formatPercent(item.rate.rate)} />
                  </>
                ),
              }))}
            />
          )}
        </QueryPanel>
      </Card>
      <p className="fine">
        Affected applications, movement, and the path toward green are on the <Link to={investigation}>investigation</Link>.
      </p>
    </div>
  )
}
