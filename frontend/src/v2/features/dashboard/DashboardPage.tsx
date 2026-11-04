import './DashboardPage.css'
import { Link, useNavigate } from 'react-router-dom'
import {
  getAttributeDistribution,
  getComplianceDistribution,
  getDataCoverage,
  getOrgContribution,
  getOverview,
  getTestingDistribution,
  getTrends,
  getApplications,
} from '../../api/portfolio'
import type { ScopeFilters } from '../../api/types'
import { BarList, LineChart, StackedBar } from '../../components/charts/Charts'
import { Card, Dash, QueryPanel, StatusChip } from '../../components/present'
import { ScopeBar } from '../../components/ScopeBar'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatInt, formatMonth, formatPercent, formatPp, formatSignedInt, labelOf } from '../../format'
import { useApiQuery } from '../../hooks/useApiQuery'
import { useLinkState } from '../../hooks/useOrigin'
import { useScopeFilters } from '../../hooks/useScopeFilters'
import { readPositiveInt } from '../../api/query'
import { AskAgentLink } from '../../components/ui/AskAgentLink'
import { scopeKey, scopedTo } from '../../scopePath'

const ATTENTION = ['nonCompliant', 'noCompletedTest', 'failedTest', 'newlyNonCompliant', 'resolved'] as const
type AttentionTab = (typeof ATTENTION)[number]

function isAttention(value: string | null): value is AttentionTab {
  return value === 'nonCompliant' || value === 'noCompletedTest' || value === 'failedTest' || value === 'newlyNonCompliant' || value === 'resolved'
}

const ATTENTION_LABEL: Record<AttentionTab, string> = {
  nonCompliant: 'Non-compliant',
  noCompletedTest: 'No completed test',
  failedTest: 'Failed test',
  newlyNonCompliant: 'Newly non-compliant',
  resolved: 'Resolved',
}

function AttentionList({ filters }: { filters: ScopeFilters }) {
  const { params, replace } = useScopeFilters()
  const linkState = useLinkState('Back')
  const attention = isAttention(params.get('attention')) ? params.get('attention')! : 'nonCompliant'
  const expanded = params.get('explore') === 'attention'
  const pageSize = expanded ? 25 : 5
  const page = expanded ? readPositiveInt(params, 'attentionPage', 1) : 1
  const query = useApiQuery(`attention-${attention}`, `${scopeKey(filters)}|${page}|${pageSize}`, () =>
    getApplications(filters, { attention, page, pageSize }),
  )
  return (
    <div className="stack">
      <div className="seg seg-wrap dashboard-attention-tabs" role="group" aria-label="Attention">
        {ATTENTION.map((item) => (
          <button key={item} type="button" className={item === attention ? 'on' : ''} onClick={() => replace({ attention: item, attentionPage: null })}>
            {ATTENTION_LABEL[item]}
          </button>
        ))}
      </div>
      <QueryPanel query={query}>
        {(data) => (
          <>
            <ul className="list dashboard-attention-list">
              {data.items.map((item) => (
                <li key={item.eonId} className="attention-row">
                  <Link className="attention-id" to={scopedTo(`/investigate/applications/${encodeURIComponent(item.eonId)}`, filters)} state={linkState}>
                    <span className="t-title">{item.applicationName}</span>
                    <span className="fine">{item.eonId}</span>
                  </Link>
                  <StatusChip value={item.movement} />
                  <span className="num">{formatInt(item.nonCompliantRows)}</span>
                </li>
              ))}
              {data.items.length === 0 && <li>No applications in this list.</li>}
            </ul>
            <div className="spread">
              {!expanded && data.page.totalItems > pageSize && (
                <button type="button" className="btn btn-sm" onClick={() => replace({ explore: 'attention', attentionPage: null })}>
                  View all {formatInt(data.page.totalItems)}
                </button>
              )}
              {expanded && (
                <button type="button" className="btn btn-quiet btn-sm" onClick={() => replace({ explore: null, attentionPage: null })}>
                  Back to summary
                </button>
              )}
            </div>
          </>
        )}
      </QueryPanel>
    </div>
  )
}

function OrgCard({ filters }: { filters: ScopeFilters }) {
  const { params, replace, replaceScope } = useScopeFilters()
  const level = params.get('orgLevel') === '2' ? 2 : 1
  const expanded = params.get('explore') === 'org'
  const page = expanded ? readPositiveInt(params, 'orgPage', 1) : 1
  const query = useApiQuery('org', `${scopeKey(filters)}|${level}|${page}|${expanded}`, () =>
    getOrgContribution(filters, { level, page, pageSize: expanded ? 40 : 8 }),
  )
  return (
    <section className="dashboard-panel dashboard-panel-org">
    <Card
      title="Where it concentrates"
      action={
        <div className="seg" role="group" aria-label="Organisation level">
          <button type="button" className={level === 1 ? 'on' : ''} onClick={() => replace({ orgLevel: null, orgPage: null })}>
            Level 1
          </button>
          <button type="button" className={level === 2 ? 'on' : ''} onClick={() => replace({ orgLevel: '2', orgPage: null })}>
            Level 2
          </button>
        </div>
      }
    >
      <p className="fine">Non-compliant applications. Bar length matches the count.</p>
      <QueryPanel query={query}>
        {(data) => (
          <>
            <BarList
              onSelect={(key) => {
                if (level === 1) replaceScope({ ...filters, l1: [key], l2: undefined })
                else replaceScope({ ...filters, l2: [key] })
              }}
              items={data.items.map((item) => ({
                key: item.key,
                label: item.label,
                value: item.nonCompliantApplications,
                note: (
                  <>
                    {formatInt(item.nonCompliantApplications)} · <Dash value={formatPercent(item.nonCompliantShare)} />
                  </>
                ),
              }))}
            />
            <div className="spread">
              {!expanded && (
                <button type="button" className="btn btn-sm" onClick={() => replace({ explore: 'org', orgPage: null })}>
                  View all {formatInt(data.page.totalItems)}
                </button>
              )}
              {expanded && (
                <button type="button" className="btn btn-quiet btn-sm" onClick={() => replace({ explore: null, orgPage: null })}>
                  Back to summary
                </button>
              )}
            </div>
          </>
        )}
      </QueryPanel>
    </Card>
    </section>
  )
}

function LegalEntityCard({ filters }: { filters: ScopeFilters }) {
  const { params, replace, replaceScope } = useScopeFilters()
  const expanded = params.get('explore') === 'legal'
  const query = useApiQuery('legal', scopeKey(filters), () => getAttributeDistribution('legalEntity', filters))
  return (
    <section className="dashboard-panel dashboard-panel-legal">
    <Card title="Legal entities">
      <p className="fine">Non-compliant applications. Bar length matches the count.</p>
      <QueryPanel query={query}>
        {(data) => {
          const shown = expanded ? data.items : data.items.slice(0, 8)
          return (
            <>
              <BarList
                onSelect={(key) => replaceScope({ ...filters, legalEntity: [key] })}
                items={shown.map((item) => ({
                  key: item.key,
                  label: item.label,
                  value: item.nonCompliantApplications,
                  note: (
                    <>
                      {formatInt(item.nonCompliantApplications)} · <Dash value={formatPercent(item.nonCompliantShare)} />
                    </>
                  ),
                }))}
              />
              <div className="spread">
                {!expanded && data.items.length > 0 && (
                  <button type="button" className="btn btn-sm" onClick={() => replace({ explore: 'legal' })}>
                    View all {formatInt(data.items.length)}
                  </button>
                )}
                {expanded && (
                  <button type="button" className="btn btn-quiet btn-sm" onClick={() => replace({ explore: null })}>
                    Back to summary
                  </button>
                )}
              </div>
            </>
          )
        }}
      </QueryPanel>
    </Card>
    </section>
  )
}

export function DashboardPage() {
  const { filters, params, replaceScope } = useScopeFilters()
  const navigate = useNavigate()
  const explore = params.get('explore')
  const key = scopeKey(filters)
  const overview = useApiQuery('overview', key, () => getOverview(filters))
  const compliance = useApiQuery('compliance', key, () => getComplianceDistribution(filters))
  const testing = useApiQuery('testing', key, () => getTestingDistribution(filters))
  const trends = useApiQuery('trends', key, () => getTrends(filters))
  const coverage = useApiQuery('coverage', filters.month ?? 'latest', () => getDataCoverage(filters.month))
  const showLegal = !filters.legalEntity?.length

  return (
    <div className="page compliance-dashboard">
      <div className="dashboard-page-header">
        <PageHeader
          eyebrow="Dashboard"
          title="Compliance health"
          subtitle="Portfolio health for the selected month. Open a card to see the underlying records."
          actions={<AskAgentLink />}
        />
      </div>
      <div className="dashboard-scope-bar">
        <ScopeBar />
      </div>
      {explore === 'org' && <OrgCard filters={filters} />}
      {explore === 'legal' && <LegalEntityCard filters={filters} />}
      {explore === 'attention' && (
        <section className="dashboard-panel dashboard-panel-expanded">
          <Card title="Applications needing attention">
            <AttentionList filters={filters} />
          </Card>
        </section>
      )}
      {!explore && (
      <QueryPanel query={overview}>
        {(data) => (
          <div className="grid g4 dashboard-kpis">
            <Link className="kpi" to={scopedTo('/register', filters)}>
              <div className="kpi-label">Applications reporting</div>
              <div className="kpi-value num">{formatInt(data.applicationsReporting.value)}</div>
              <p className="kpi-delta">{formatSignedInt(data.applicationsReporting.delta) ?? '—'}</p>
            </Link>
            <Link className="kpi" to={scopedTo('/register', filters, { hasNonCompliant: 'true' })}>
              <div className="kpi-label">Non-compliant</div>
              <div className="kpi-value num">{formatInt(data.nonCompliant.applications.value)}</div>
              <p className="kpi-delta">
                <Dash value={formatPercent(data.nonCompliant.share.value)} /> · <Dash value={formatPp(data.nonCompliant.share.deltaPp)} />
              </p>
            </Link>
            <Link className="kpi" to={scopedTo('/', filters, { explore: 'attention', attention: 'noCompletedTest' })}>
              <div className="kpi-label">No completed test</div>
              <div className="kpi-value num">{formatInt(data.testing.withoutCompletedTest.value)}</div>
              <p className="kpi-delta">{formatSignedInt(data.testing.withoutCompletedTest.delta) ?? '—'}</p>
            </Link>
            <article className="kpi">
              <div className="kpi-label">Open findings</div>
              <div className="kpi-value num">{formatInt(data.openFindings.value)}</div>
              <p className="kpi-delta">Counted once · {formatSignedInt(data.openFindings.delta) ?? '—'}</p>
            </article>
          </div>
        )}
      </QueryPanel>
      )}
      {!explore && <div className="grid g2 dash-columns dashboard-analytics-grid">
        <div className="stack dashboard-column dashboard-column-left">
        <section className="dashboard-panel dashboard-panel-compliance">
        <Card title="Compliance mix">
          <QueryPanel query={compliance}>
            {(data) => (
              <>
                <p className="fine">
                  Metric rows, not applications · {formatMonth(data.month)} · {formatInt(data.metricRows.total)} rows
                </p>
                <StackedBar
                  onSelect={(status) =>
                    navigate(scopedTo('/register', filters, status === 'Non_Compliant' ? { hasNonCompliant: 'true' } : undefined))
                  }
                  segments={data.metricRows.byStatus.map((item) => ({
                    key: item.status,
                    label: labelOf(item.status),
                    value: item.rows,
                  }))}
                />
                <ul className="list">
                  {data.metricRows.byStatus.map((item) => (
                    <li key={item.status}>
                      <span className="grow">{labelOf(item.status)}</span>
                      <span className="num">
                        {formatInt(item.rows)} · <Dash value={formatPercent(item.share)} />
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="fine">
                  Application count, separate from the rows above: {formatInt(data.applications.nonCompliant)} non-compliant · {formatInt(data.applications.notNonCompliant)} other ·{' '}
                  {formatInt(data.applications.total)} reporting
                </p>
              </>
            )}
          </QueryPanel>
        </Card>
        </section>
        <section className="dashboard-panel dashboard-panel-testing">
        <Card title="Testing distribution">
            <QueryPanel query={testing}>
              {(data) => (
                <div className="stack">
                  <p className="fine">Metric rows by test status. This is not an application count.</p>
                  <BarList
                    onSelect={(key) => {
                      if (key === 'No_Test') navigate(scopedTo('/', filters, { explore: 'attention', attention: 'noCompletedTest' }))
                    }}
                    items={(data.byTestStatus ?? []).map((item) => ({
                      key: item.testStatus,
                      label: labelOf(item.testStatus),
                      value: item.metricRows,
                      note: (
                        <>
                          {formatInt(item.metricRows)} · <Dash value={formatPercent(item.share)} />
                        </>
                      ),
                    }))}
                  />
                  <p className="fine">Applications, counted once</p>
                  <BarList
                    onSelect={(key) => {
                      if (key === 'noCompletedTest') navigate(scopedTo('/', filters, { explore: 'attention', attention: 'noCompletedTest' }))
                      if (key === 'failedTest') navigate(scopedTo('/', filters, { explore: 'attention', attention: 'failedTest' }))
                    }}
                    items={[
                      { key: 'noCompletedTest', label: 'No completed test', value: data.applications.withoutCompletedTest, note: formatInt(data.applications.withoutCompletedTest) },
                      { key: 'failedTest', label: 'Failed test', value: data.applications.withFailedTest, note: formatInt(data.applications.withFailedTest) },
                    ]}
                  />
                  <p className="fine">{formatInt(data.applications.reporting)} applications reporting</p>
                  <QueryPanel query={coverage}>
                    {(cover) => (
                      <p className="fine">
                        Coverage {formatInt(cover.applicationsReporting)} reporting · {formatInt(cover.applicationsNotReporting)} not reporting ·{' '}
                        {formatMonth(cover.months.first)} – {formatMonth(cover.months.last)}
                      </p>
                    )}
                  </QueryPanel>
                </div>
              )}
            </QueryPanel>
          </Card>
          </section>
        </div>
        <div className="stack dashboard-column dashboard-column-right">
        <section className="dashboard-panel dashboard-panel-movement">
        <Card title="Movement and attention">
          <QueryPanel query={overview}>
            {(data) =>
              data.movement ? (
                <div className="stack">
                  <div className="grid g2 dashboard-movement-stats">
                    <div className="move-bad">
                      <div className="fine">Newly non-compliant</div>
                      <div className="num">{formatInt(data.movement.newlyNonCompliant)}</div>
                    </div>
                    <div className="move-good">
                      <div className="fine">Resolved</div>
                      <div className="num">{formatInt(data.movement.resolved)}</div>
                    </div>
                  </div>
                  <p className="fine">
                    Persistent {formatInt(data.movement.persistentNonCompliant)} · No prior month {formatInt(data.movement.noPriorMonth)}
                  </p>
                </div>
              ) : (
                <p className="fine">No prior month, so movement is not available.</p>
              )
            }
          </QueryPanel>
          <AttentionList filters={filters} />
        </Card>
        </section>
        </div>
      </div>}
      {!explore && (
        <section className="dashboard-panel dashboard-panel-trend">
          <Card title="Non-compliant share">
            <p className="fine">Application share by month. Select a point to change the reporting month. Gaps are not plotted as zero.</p>
            <QueryPanel query={trends}>
              {(data) => (
                <LineChart
                  onSelect={(index) => {
                    const month = data.points[index]?.month
                    if (month) replaceScope({ ...filters, month })
                  }}
                  points={data.points.map((point) => ({ label: formatMonth(point.month), value: point.nonCompliantShare }))}
                />
              )}
            </QueryPanel>
          </Card>
        </section>
      )}
      {!explore && (
        <div className={`dashboard-pair${showLegal ? '' : ' dashboard-pair-single'}`}>
          <OrgCard filters={filters} />
          {showLegal && <LegalEntityCard filters={filters} />}
        </div>
      )}
    </div>
  )
}
