import { Link, useParams } from 'react-router-dom'
import { getApplicationInvestigation } from '../../api/portfolio'
import { StatusStrip } from '../../components/charts/Charts'
import { Card, Dash, Provisional, QueryPanel, StatusChip } from '../../components/present'
import { ScopeBar } from '../../components/ScopeBar'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatInt, formatMonth, formatPercent, labelOf } from '../../format'
import { useApiQuery } from '../../hooks/useApiQuery'
import { useBackTarget, useLinkState } from '../../hooks/useOrigin'
import { useScopeFilters } from '../../hooks/useScopeFilters'
import { scopeKey, scopedTo } from '../../scopePath'
import { AskAgentLink } from '../../components/ui/AskAgentLink'
import { ApplicationPath } from './PathToGreen'
import { PreparedAnalysis } from './PreparedAnalysis'
import { Skeleton } from '../../components/Skeleton'


export function ApplicationInvestigationPage() {
  const { eonId = '' } = useParams()
  const { filters, params, replace } = useScopeFilters()
  const metricId = params.get('metric') || undefined
  const includeOwners = params.get('owners') === '1'
  const back = useBackTarget({ to: metricId ? scopedTo(`/investigate/metrics/${encodeURIComponent(metricId)}`, filters) : '/', label: 'Back' })
  const linkState = useLinkState('Back')
  const query = useApiQuery('application-investigation', `${eonId}|${scopeKey(filters)}|${metricId ?? ''}|${includeOwners}`, () =>
    getApplicationInvestigation(eonId, filters, { metricId, includeOwners }),
    { keep: `${eonId}|${metricId ?? ''}` },
  )

  return (
    <div className="page">
      <p className="crumbs">
        <Link to={back.to} state={back.state} onClick={back.go}>
          Back
        </Link>
        {metricId && (
          <>
            {' · '}
            <Link to={scopedTo(`/investigate/metrics/${encodeURIComponent(metricId)}`, filters)} state={linkState}>
              {metricId}
            </Link>
          </>
        )}
      </p>
      <QueryPanel query={query} skeleton={<Skeleton shape="investigation" label={`Loading application ${eonId}`} />}>
        {(data) => {
          const application = data.application
          return (
            <div className="stack">
              <PageHeader
                actions={<AskAgentLink />}
                eyebrow="Investigation"
                title={application.applicationName}
                subtitle={application.eonId}
                chips={
                  application.observed ? (
                    <>
                      {application.status.isNonCompliant && <span className="chip red">Non-compliant</span>}
                      {application.status.hasNoCompletedTest && <span className="chip amber">No completed test</span>}
                      {application.status.hasFailedTest && <span className="chip red">Failed test</span>}
                      <span className="chip">{labelOf(application.status.movement)}</span>
                    </>
                  ) : (
                    <span className="chip na">Not observed</span>
                  )
                }
              />
              <ScopeBar mode="compact" />
              {!application.observed && (
                <p className="callout warn">
                  Not observed{application.lastObservedMonth ? ` · last observed ${formatMonth(application.lastObservedMonth)}` : ''}.
                </p>
              )}
              {application.observed && (
                <div className="grid g3">
                  <article className="stat">
                    <div className="fine">Metrics reported</div>
                    <div className="num">{formatInt(application.status.metricsReported)}</div>
                  </article>
                  <article className="stat">
                    <div className="fine">Non-compliant rows</div>
                    <div className="num">{formatInt(application.status.nonCompliantRows)}</div>
                  </article>
                  <article className="stat">
                    <div className="fine">Open findings · counted once</div>
                    <div className="num">{application.status.openFindings == null ? '—' : formatInt(application.status.openFindings)}</div>
                  </article>
                </div>
              )}
              <div className="grid g-main">
                <Card title="History">
                  <StatusStrip
                    cells={data.history.months.map((month) =>
                      month.observed
                        ? {
                            month: month.month,
                            observed: true,
                            tone: month.isNonCompliant ? '#c0454c' : '#aab4bf',
                            text: month.isNonCompliant ? 'Non-compliant' : 'Observed',
                          }
                        : { month: month.month, observed: false },
                    )}
                  />
                  {data.history.note && <p className="fine">{data.history.note}</p>}
                  {data.derived.nonCompliantRun && (
                    <p className="fine">
                      Non-compliant for {formatInt(data.derived.nonCompliantRun.months)} months
                      {data.derived.nonCompliantRun.since ? ` since ${formatMonth(data.derived.nonCompliantRun.since)}` : ''}.
                    </p>
                  )}
                </Card>
                <div className="rail">
                  <Card title="Attributes">
                    <dl className="kv">
                      <dt>Tier</dt>
                      <dd>{application.attributes.tier}</dd>
                      <dt>Risk</dt>
                      <dd>{application.attributes.risk}</dd>
                      <dt>Lifecycle</dt>
                      <dd>{application.attributes.lifecycle}</dd>
                      <dt>Legal entity</dt>
                      <dd>
                        {application.attributes.legalEntityName}
                        {application.attributes.legalEntityCode !== application.attributes.legalEntityName && (
                          <span className="fine num"> · {application.attributes.legalEntityCode}</span>
                        )}
                      </dd>
                      <dt>Organisation</dt>
                      <dd>{application.attributes.org.businessOrg.level1}</dd>
                      <dt>M&A</dt>
                      <dd>{application.attributes.isMergersAcquisitionsAsset ? 'Yes' : 'No'}</dd>
                    </dl>
                    {application.changedAttributes.length > 0 && (
                      <ul className="list">
                        {application.changedAttributes.map((change) => (
                          <li key={`${change.field}:${change.month}`}>
                            <span className="grow">
                              {change.field}: {change.from} → {change.to}
                            </span>
                            <span className="fine">{formatMonth(change.month)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Card>
                  <Card title="Owners">
                    {includeOwners ? (
                      <dl className="kv">
                        <dt>Business</dt>
                        <dd>{application.attributes.owners?.business || '—'}</dd>
                        <dt>IT</dt>
                        <dd>{application.attributes.owners?.it || '—'}</dd>
                      </dl>
                    ) : (
                      <button type="button" className="btn btn-sm" onClick={() => replace({ owners: '1' })}>
                        Show owner names
                      </button>
                    )}
                  </Card>
                  <Card title="Peers">
                    <p className="fine">
                      <Provisional id="PD-17" of="peer basis" /> {data.derived.peers.basis.l1} · {data.derived.peers.basis.lifecycle}
                    </p>
                    <p>
                      {formatInt(data.derived.peers.nonCompliantApplications)} of {formatInt(data.derived.peers.applications)} ·{' '}
                      <Dash value={formatPercent(data.derived.peers.nonCompliantShare)} />
                    </p>
                  </Card>
                </div>
              </div>
              <Card title="Metrics this month">
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Status</th>
                        <th>Test</th>
                        <th>Movement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {application.metrics.map((row) => (
                        <tr key={row.metricId} className={row.metricId === metricId ? 'sel' : undefined}>
                          <td>
                            <Link to={scopedTo(`/investigate/metrics/${encodeURIComponent(row.metricId)}`, filters)} state={linkState}>
                              {row.metricId}
                            </Link>
                          </td>
                          <td><StatusChip value={row.complianceStatus} /></td>
                          <td><StatusChip value={row.testStatus} /></td>
                          <td><StatusChip value={row.metricMovement} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
              {data.history.metricTimeline.length > 0 && (
                <Card title="Metric months">
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Metric</th>
                          {data.history.months.map((month) => (
                            <th key={month.month}>{formatMonth(month.month)}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.history.metricTimeline.map((row) => (
                          <tr key={row.metricId} className={row.metricId === metricId ? 'sel' : undefined}>
                            <td>{row.metricId}</td>
                            {row.months.map((cell) => (
                              <td key={cell.month}>{cell.observed ? (cell.complianceStatus ? labelOf(cell.complianceStatus) : '—') : 'Not observed'}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
              {application.observed && <ApplicationPath rows={application.metrics} />}
              <PreparedAnalysis analysis={data.agentAnalysis} />
            </div>
          )
        }}
      </QueryPanel>
    </div>
  )
}
