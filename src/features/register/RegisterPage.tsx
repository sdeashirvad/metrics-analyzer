import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { DATA_NOTICE } from '../../backend/contracts/types'
import type { MetricFamily, MetricListItem, MetricListQuery } from '../../backend/contracts/types'
import { api } from '../../backend/services'
import { StatusBadge } from '../../components/StatusBadge'
import { DataTable } from '../../components/ui/DataTable'
import { Field, FilterToolbar } from '../../components/ui/FilterToolbar'
import { SelectField } from '../../components/ui/Select'
import { PageHeader } from '../../components/ui/PageHeader'
import { Pager, rangeText } from '../../components/ui/Pager'
import { PageError, PageLoading, SectionEmpty } from '../../components/ui/SectionState'
import { SegmentedControl } from '../../components/ui/SegmentedControl'
import { isRagStatus } from '../../domain/evaluateStatus'
import { directionLabel, formatDate, formatNumber, isFrequency, statusLabel } from '../../domain/format'
import { useLinkState } from '../../hooks/useOrigin'
import { useQuery } from '../../hooks/useQuery'
import { useUrlState } from '../../hooks/useUrlState'

const PAGE_SIZE = 25
const WORKBOOK_NOTICE = 'Workbook snapshot SMARTS_DQ_mock_data.xlsx — not connected to SMARTS'
const FAMILY_LABEL: Record<MetricFamily, string> = { technology_risk: 'Technology Risk', data_quality: 'Data Quality' }

type FamilyView = 'all' | MetricFamily

export function RegisterPage() {
  const [params, setParams] = useUrlState()
  const q = params.get('q') ?? ''
  const domain = params.get('domain') ?? ''
  const statusParam = params.get('status') ?? ''
  const frequencyParam = params.get('frequency') ?? ''
  const status = isRagStatus(statusParam) ? statusParam : undefined
  const frequency = isFrequency(frequencyParam) ? frequencyParam : undefined
  const familyParam = params.get('family') ?? ''
  const family: MetricFamily | undefined = familyParam === 'technology_risk' || familyParam === 'data_quality' ? familyParam : undefined
  const investigation = params.get('inv') === '1'
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const [search, setSearch] = useState(q)
  const [showThresholds, setShowThresholds] = useState(false)
  const [exporting, setExporting] = useState(false)
  const linkState = useLinkState('Metric register')

  const query: MetricListQuery = { q, domain, status, frequency, family, investigation: investigation || undefined, page, pageSize: PAGE_SIZE }
  const { data, error, retry, refreshing } = useQuery('register', JSON.stringify(query), () => api.listMetrics(query))
  const counts = useQuery('register-counts', '', async () => {
    const [tech, dq] = await Promise.all([
      api.listMetrics({ family: 'technology_risk', pageSize: 1 }),
      api.listMetrics({ family: 'data_quality', pageSize: 1 }),
    ])
    return { technology_risk: tech.total, data_quality: dq.total }
  })

  useEffect(() => {
    setSearch((current) => (current.trim() === q.trim() ? current : q))
  }, [q])

  useEffect(() => {
    if (search === q) return
    const timer = window.setTimeout(() => setParams({ q: search, page: null }), 250)
    return () => window.clearTimeout(timer)
  }, [search, q, setParams])

  function commit(next: Record<string, string | null>) {
    setParams({ ...next, page: null }, { commit: true })
  }

  function clear() {
    setSearch('')
    setParams({ q: null, domain: null, status: null, frequency: null, inv: null, page: null }, { commit: true })
  }

  async function exportAll() {
    if (!data) return
    setExporting(true)
    try {
      const all = await api.listMetrics({ ...query, page: 1, pageSize: Math.max(data.total, 1) })
      download(all.items, 'metrics-analyzer-register-all.csv')
    } finally {
      setExporting(false)
    }
  }

  if (error && !data) return <PageError message={error.message} onRetry={retry} />
  if (!data) return <PageLoading label="Loading the metric register" />

  const activeCount = [q, domain, status, frequency, investigation ? '1' : ''].filter(Boolean).length
  const pages = Math.max(1, Math.ceil(data.total / data.pageSize))
  const groups: Array<{ family: MetricFamily; items: MetricListItem[] }> = []
  for (const item of data.items) {
    const last = groups[groups.length - 1]
    if (last && last.family === item.family) last.items.push(item)
    else groups.push({ family: item.family, items: [item] })
  }
  const total = counts.data ? counts.data.technology_risk + counts.data.data_quality : undefined
  const columns = showThresholds ? 10 : 7

  return (
    <div className="page register">
      <PageHeader
        title="Metric register"
        subtitle="Find a metric or control. Technology Risk readings are synthetic; Data Quality readings are workbook pass rates."
      >
        <SegmentedControl<FamilyView>
          label="Family"
          value={family ?? 'all'}
          onChange={(next) => commit({ family: next === 'all' ? null : next, domain: null })}
          options={[
            { value: 'all', label: 'All', count: total },
            { value: 'technology_risk', label: 'Technology Risk', count: counts.data?.technology_risk },
            { value: 'data_quality', label: 'Data Quality', count: counts.data?.data_quality },
          ]}
        />
      </PageHeader>

      <FilterToolbar
        label="Register filters"
        activeCount={activeCount}
        onClear={clear}
        summary={
          <>
            <span className="num results-line" aria-live="polite">
              {data.total === 0 ? 'No matches' : `${rangeText(data.page, data.pageSize, data.total)} · Page ${data.page} of ${pages}`}
            </span>
            <label className="check">
              <input type="checkbox" checked={showThresholds} onChange={(event) => setShowThresholds(event.target.checked)} />
              Show thresholds
            </label>
            <span className="toolbar-spacer" />
            <button type="button" className="btn btn-sm" disabled={data.items.length === 0} onClick={() => download(data.items, 'metrics-analyzer-register-page.csv')}>
              Export this page
            </button>
            <button type="button" className="btn btn-sm" disabled={data.total === 0 || exporting} onClick={exportAll}>
              {exporting ? 'Exporting…' : `Export all matching (${data.total})`}
            </button>
          </>
        }
      >
        <Field label="Search" grow>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, ID, domain, or control" type="search" />
        </Field>
        <SelectField
          label={family === 'data_quality' ? 'Dimension' : family === 'technology_risk' ? 'Domain' : 'Domain or dimension'}
          value={domain}
          onChange={(next) => commit({ domain: next || null })}
          options={[
            { value: '', label: 'All' },
            ...(family
              ? data.facets.domains.map((item) => ({ value: item, label: item }))
              : (['technology_risk', 'data_quality'] as const).flatMap((group) =>
                  data.facets.domainsByFamily[group].map((item) => ({ value: item, label: item, group: FAMILY_LABEL[group] })),
                )),
          ]}
        />
        <SelectField
          label="Status"
          value={status ?? ''}
          onChange={(next) => commit({ status: next || null })}
          options={[{ value: '', label: 'All' }, ...data.facets.statuses.map((item) => ({ value: item, label: statusLabel(item) }))]}
        />
        <SelectField
          label="Frequency"
          value={frequency ?? ''}
          onChange={(next) => commit({ frequency: next || null })}
          options={[{ value: '', label: 'All' }, ...data.facets.frequencies.map((item) => ({ value: item, label: item }))]}
        />
        <label className="check">
          <input type="checkbox" checked={investigation} onChange={(event) => commit({ inv: event.target.checked ? '1' : null })} />
          Has investigation
        </label>
      </FilterToolbar>

      {data.items.length === 0 ? (
        <SectionEmpty
          title="No metrics match"
          body="Clear the search or choose a broader status, domain, or frequency."
          action={
            <button type="button" className="btn" onClick={clear}>
              Clear filters
            </button>
          }
        />
      ) : (
        <DataTable
          caption="Metric register"
          refreshing={refreshing}
          className="register-table"
          head={
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">Domain</th>
              <th scope="col">Status</th>
              <th scope="col">Reading</th>
              <th scope="col">First red or breach</th>
              <th scope="col">Frequency</th>
              {showThresholds && (
                <>
                  <th scope="col">Green</th>
                  <th scope="col">Amber</th>
                  <th scope="col">Direction</th>
                </>
              )}
              <th scope="col">
                <span className="sr-only">Action</span>
              </th>
            </tr>
          }
        >
          {groups.map((group) => (
            <GroupRows key={`${group.family}-${group.items[0].metric.id}`} showHeading={!family} family={group.family} columns={columns}>
              {group.items.map((item) => (
                <tr key={item.metric.id} className={`reg-row fam-${item.family}`}>
                  <td className="reg-metric">
                    <Link to={`/metrics/${item.metric.id}`} state={linkState}>
                      <span className="mono">{item.metric.id}</span>
                      <span className="reg-name">{item.metric.name}</span>
                    </Link>
                  </td>
                  <td className="reg-domain">{item.metric.domain}</td>
                  <td className="reg-status">
                    <StatusBadge status={item.reading.status} />
                  </td>
                  <td className="reg-reading num">{readingLabel(item)}</td>
                  <td className="reg-date">{item.reading.breachedOn ? formatDate(item.reading.breachedOn) : <span className="muted">—</span>}</td>
                  <td className="reg-freq">{item.metric.frequency}</td>
                  {showThresholds && (
                    <>
                      <td className="num">{formatNumber(item.metric.thresholds.green, item.metric.unit)}</td>
                      <td className="num">{formatNumber(item.metric.thresholds.amber, item.metric.unit)}</td>
                      <td>{directionLabel(item.metric.direction)}</td>
                    </>
                  )}
                  <td className="reg-action">
                    {item.investigationAvailable ? (
                      <Link className="btn btn-sm" to={`/investigations/${item.metric.id}`} state={linkState}>
                        Investigation
                      </Link>
                    ) : (
                      <Link className="btn btn-sm btn-quiet" to={`/metrics/${item.metric.id}`} state={linkState}>
                        Detail
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </GroupRows>
          ))}
        </DataTable>
      )}
      <Pager page={data.page} pageSize={data.pageSize} total={data.total} label="Register pages" onPage={(next) => setParams({ page: String(next) }, { commit: true })} />
    </div>
  )
}

function GroupRows({ family, showHeading, columns, children }: { family: MetricFamily; showHeading: boolean; columns: number; children: ReactNode }) {
  return (
    <>
      {showHeading && (
        <tr className={`group-row group-${family}`}>
          <th scope="colgroup" colSpan={columns}>
            {FAMILY_LABEL[family]}
          </th>
        </tr>
      )}
      {children}
    </>
  )
}

function readingLabel(item: MetricListItem): string {
  if (item.reading.value == null) return 'No reading'
  if (item.family === 'data_quality') return `${item.reading.value.toFixed(2)}% workbook`
  return `${formatNumber(item.reading.value, item.metric.unit)} synthetic`
}

function download(items: MetricListItem[], filename: string) {
  if (items.length === 0) return
  const blob = new Blob([buildRegisterCsv(items)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function csvCell(value: string | number | null): string {
  const text = value == null ? '' : String(value)
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`
  return text
}

function buildRegisterCsv(items: MetricListItem[]): string {
  const headers = [
    'family',
    'metric_id',
    'metric_name',
    'domain',
    'control_id',
    'control_statement',
    'owner_function',
    'frequency',
    'direction',
    'unit',
    'green_threshold',
    'amber_threshold',
    'provisional_definition',
    'reading',
    'reading_as_of',
    'reading_origin',
    'status',
    'status_basis',
    'breach_date',
    'investigation_available',
    'data_notice',
  ]
  const lines = items.map((item) =>
    [
      item.family,
      item.metric.id,
      item.metric.name,
      item.metric.domain,
      item.metric.controlId,
      item.metric.controlStatement,
      item.metric.ownerFunction,
      item.metric.frequency,
      item.metric.direction,
      item.metric.unit,
      item.metric.thresholds.green,
      item.metric.thresholds.amber,
      item.metric.provisionalDefinition,
      item.reading.value,
      item.reading.asOf,
      item.reading.origin,
      item.reading.status,
      item.reading.statusBasis,
      item.reading.breachedOn,
      item.investigationAvailable ? 'yes' : 'no',
      item.family === 'data_quality' ? WORKBOOK_NOTICE : DATA_NOTICE,
    ]
      .map(csvCell)
      .join(','),
  )
  return `\uFEFF${headers.join(',')}\n${lines.join('\n')}\n`
}
