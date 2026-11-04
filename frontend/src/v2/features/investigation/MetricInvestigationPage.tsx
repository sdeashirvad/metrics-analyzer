import { Link, useParams } from 'react-router-dom'
import { readPositiveInt } from '../../api/query'
import { getMetricApplications, getMetricInvestigation } from '../../api/portfolio'
import { Card, Dash, Pager, QueryPanel, RagPill, StatusChip } from '../../components/present'
import { ScopeBar } from '../../components/ScopeBar'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatInt, formatPercent } from '../../format'
import { useApiQuery } from '../../hooks/useApiQuery'
import { useBackTarget, useLinkState } from '../../hooks/useOrigin'
import { useScopeFilters } from '../../hooks/useScopeFilters'
import { scopeKey, scopedTo } from '../../scopePath'
import { AskAgentLink } from '../../components/ui/AskAgentLink'
import { MetricPath } from './PathToGreen'
import { PreparedAnalysis } from './PreparedAnalysis'

export function MetricInvestigationPage() {
  const { metricId = '' } = useParams()
  const { filters, params, replace } = useScopeFilters()
  const back = useBackTarget({ to: scopedTo(`/register/${encodeURIComponent(metricId)}`, filters), label: 'Back' })
  const linkState = useLinkState('Back')
  const appsPage = readPositiveInt(params, 'appsPage', 1)
  const key = `${metricId}|${scopeKey(filters)}`
  const query = useApiQuery('metric-investigation', key, () => getMetricInvestigation(metricId, filters))
  const applications = useApiQuery('metric-investigation-apps', `${key}|${appsPage}`, () =>
    getMetricApplications(metricId, filters, { page: appsPage, pageSize: 15 }),
  )

  return (
    <div className="page">
      <p className="crumbs">
        <Link to={back.to} state={back.state} onClick={back.go}>
          Back
        </Link>
        {' · '}
        <Link to={scopedTo('/register', filters)}>Register</Link>
        {' / '}
        {metricId}
      </p>
      <ScopeBar mode="compact" />
      <QueryPanel query={query}>
        {(data) => (
          <div className="stack">
            <PageHeader eyebrow="Investigation" title={metricId} subtitle="What is affected, what changed, and what would move this toward green." actions={<AskAgentLink />} />
            <PreparedAnalysis
              analysis={data.agentAnalysis}
              emptyText="No prepared investigation covers this scope. Prepared investigations cover the default scope for the latest reporting month. Use Ask Agent to explore this scope."
            />
            <div className="grid g4">
              <article className="kpi">
                <div className="kpi-label">Rate</div>
                <div className="kpi-value">
                  <Dash value={formatPercent(data.observations.rate.rate)} /> <RagPill rag={data.observations.rag} />
                </div>
                <p className="fine">
                  {formatInt(data.observations.rate.numerator)} / {formatInt(data.observations.rate.denominator)} ·{' '}
                  <Link to={scopedTo(`/register/${encodeURIComponent(metricId)}`, filters)}>How this is calculated</Link>
                </p>
              </article>
              <article className="kpi">
                <div className="kpi-label">Applications affected</div>
                <div className="kpi-value num">{formatInt(data.observations.applications)}</div>
              </article>
              <article className="kpi">
                <div className="kpi-label">Movement</div>
                <div className="kpi-value" style={{ fontSize: 18 }}>
                  {data.derived.movement
                    ? `${formatInt(data.derived.movement.newlyNonCompliant)} new · ${formatInt(data.derived.movement.persistentNonCompliant)} persistent`
                    : 'No prior month'}
                </div>
              </article>
              <article className="kpi">
                <div className="kpi-label">Tests</div>
                <div className="kpi-value" style={{ fontSize: 18 }}>
                  {formatInt(data.observations.testing.fail)} failed
                </div>
                <p className="fine">
                  {formatInt(data.observations.testing.none)} no test · {formatInt(data.observations.testing.pass)} pass
                </p>
              </article>
            </div>
            <Card title="Largest contributors">
              <ul className="list">
                {data.derived.largestContributors.map((item) => (
                  <li key={`${item.dimension}:${item.key}`}>
                    <span className="grow">
                      <span className="t-title">{item.key}</span>
                      <span className="fine"> {item.dimension === 'org' ? 'Organisation' : 'Legal entity'}</span>
                    </span>
                    <span className="num">
                      {formatInt(item.nonCompliantApplications)} / {formatInt(item.applications)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
            <MetricPath data={data} />
            <Card title="Affected applications">
              <p className="fine">Choose an application to open its investigation. This page does not pick one for you.</p>
              <QueryPanel query={applications}>
                {(rows) => (
                  <>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Application</th>
                            <th>Status</th>
                            <th>Test</th>
                            <th>Movement</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.items.map((row) => (
                            <tr key={row.eonId}>
                              <td>
                                <Link to={scopedTo(`/investigate/applications/${encodeURIComponent(row.eonId)}`, filters, { metric: metricId })} state={linkState}>
                                  {row.applicationName}
                                </Link>
                                <div className="fine num">{row.eonId}</div>
                              </td>
                              <td><StatusChip value={row.complianceStatus} /></td>
                              <td><StatusChip value={row.testStatus} /></td>
                              <td><StatusChip value={row.metricMovement} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <Pager page={rows.page} onPage={(next) => replace({ appsPage: next <= 1 ? null : String(next) })} />
                  </>
                )}
              </QueryPanel>
            </Card>
          </div>
        )}
      </QueryPanel>
    </div>
  )
}
