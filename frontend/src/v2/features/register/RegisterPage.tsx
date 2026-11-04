import { readPositiveInt } from '../../api/query'
import { getMetrics } from '../../api/portfolio'
import type { DenominatorScope, RagStatus } from '../../api/types'
import { Sparkline } from '../../components/charts/Charts'
import { MenuSelect } from '../../components/MenuSelect'
import { Dash, Pager, Provisional, QueryPanel, RagPill } from '../../components/present'
import { ScopeBar } from '../../components/ScopeBar'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatInt, formatMonth, formatPercent, labelOf } from '../../format'
import { useApiQuery } from '../../hooks/useApiQuery'
import { useScopeFilters } from '../../hooks/useScopeFilters'
import { scopeKey } from '../../scopePath'
import { PreviewModal } from './PreviewModal'
import { Skeleton } from '../../components/Skeleton'

const SORTS = ['applications:desc', 'nonCompliant:desc', 'rate:desc', 'rateDelta:desc', 'rag:desc', 'metricId:asc'] as const
const RAGS: RagStatus[] = ['red', 'amber', 'green', 'unclassified']
const RAG_NAME: Record<RagStatus, string> = { red: 'Needs attention', amber: 'Watch', green: 'Healthy', unclassified: 'Unclassified' }
const DENOMINATORS: DenominatorScope[] = ['INCLUDES_PENDING', 'EXCLUDES_PENDING', 'MIXED', 'UNDETERMINED']

function isSort(value: string | null): value is (typeof SORTS)[number] {
  return SORTS.includes(value as (typeof SORTS)[number])
}

function pageSizeOf(value: string | null): number {
  const size = Number(value)
  return size === 10 || size === 25 || size === 50 || size === 100 ? size : 25
}

export function RegisterPage() {
  const { filters, params, replace } = useScopeFilters()
  const q = params.get('q') ?? ''
  const sort = isSort(params.get('sort')) ? params.get('sort')! : 'applications:desc'
  const page = readPositiveInt(params, 'page', 1)
  const pageSize = pageSizeOf(params.get('pageSize'))
  const hasNonCompliant = params.get('hasNonCompliant') === 'true'
  const denominatorScope = params.getAll('denominatorScope').filter((item): item is DenominatorScope => DENOMINATORS.includes(item as DenominatorScope))
  const rag = params.getAll('rag').filter((item): item is RagStatus => RAGS.includes(item as RagStatus))
  const preview = params.get('preview')
  const registerFilterCount = (q ? 1 : 0) + rag.length + denominatorScope.length + (hasNonCompliant ? 1 : 0)
  const query = useApiQuery('register', `${scopeKey(filters)}|${q}|${sort}|${page}|${pageSize}|${hasNonCompliant}|${denominatorScope.join(',')}|${rag.join(',')}`, () =>
    getMetrics(filters, {
      q: q || undefined,
      rag: rag.length ? rag : undefined,
      sort,
      page,
      pageSize,
      hasNonCompliant: hasNonCompliant || undefined,
      denominatorScope: denominatorScope.length ? denominatorScope : undefined,
    }),
    { keep: 'register' },
  )

  // One filter surface: search, scope, register filters and ordering live together; paging sits with the table.
  const search = (
    <label className="field field-search">
      <span className="field-label">Search</span>
      <input type="search" value={q} placeholder="Metric id" onChange={(event) => replace({ q: event.target.value || null, page: null })} />
    </label>
  )
  const registerFilters = (
    <>
      <div className="field">
        <span className="field-label">RAG</span>
        <MenuSelect
          label="RAG"
          multiple
          options={RAGS.map((item) => ({ value: item, label: RAG_NAME[item] }))}
          selected={rag}
          onChange={(next) => replace({ rag: next, page: null })}
        />
      </div>
      <div className="field">
        <span className="field-label">Denominator</span>
        <MenuSelect
          label="Denominator"
          multiple
          options={DENOMINATORS.map((item) => ({ value: item, label: labelOf(item) }))}
          selected={denominatorScope}
          onChange={(next) => replace({ denominatorScope: next, page: null })}
        />
      </div>
      <div className="field">
        <span className="field-label">Sort</span>
        <MenuSelect
          label="Sort"
          allowEmpty={false}
          emptyLabel="Applications"
          options={[
            { value: 'applications:desc', label: 'Applications' },
            { value: 'nonCompliant:desc', label: 'Non-compliant' },
            { value: 'rate:desc', label: 'Rate' },
            { value: 'rag:desc', label: 'RAG' },
            { value: 'rateDelta:desc', label: 'Rate change' },
            { value: 'metricId:asc', label: 'Metric id' },
          ]}
          selected={[sort]}
          onChange={(next) => {
            const value = next[0]
            if (!value) return
            replace({ sort: value === 'applications:desc' ? null : value, page: null })
          }}
        />
      </div>
      <label className="check">
        <input type="checkbox" checked={hasNonCompliant} onChange={(event) => replace({ hasNonCompliant: event.target.checked ? 'true' : null, page: null })} />
        Has non-compliant rows
      </label>
      {registerFilterCount > 0 && (
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => replace({ q: null, rag: [], denominatorScope: [], hasNonCompliant: null, page: null })}>
          Reset register filters
        </button>
      )}
    </>
  )

  return (
    <div className="page">
      <PageHeader eyebrow="Metric register" title="Metric register" subtitle="Search and filter the register. Preview opens over the table." />
      <ScopeBar search={search} extra={registerFilters} />
      <p className="fine">Provisional bands on the fractional rate: Healthy below 45%, Watch below 60%, Needs attention at 60% and above. A missing rate stays unclassified.</p>
      <QueryPanel query={query} skeleton={<Skeleton shape="table" rows={Math.min(pageSize, 12)} label="Loading the register" />}>
        {(data) => (
          <>
            <div className="table-wrap metric-register-wrap">
              <table className="metric-register">
                <caption className="sr-only">Metric register for the selected scope</caption>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Applications</th>
                    <th>
                      Rate <Provisional id="PD-01" of="register rate" />
                    </th>
                    <th>Non-compliant</th>
                    <th>Denominator</th>
                    <th>Trend</th>
                    <th>Preview</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => {
                    const open = preview === item.metricId
                    return (
                      <tr key={item.metricId} className={open ? 'sel' : undefined}>
                        <td className="num" data-label="Metric">
                          {item.metricId}
                        </td>
                        <td className="num" data-label="Applications">
                          {formatInt(item.applications)}
                        </td>
                        <td data-label="Rate">
                          <Dash value={formatPercent(item.rate.rate)} /> <RagPill rag={item.rag} />
                        </td>
                        <td className="num" data-label="Non-compliant">
                          {formatInt(item.nonCompliantApplications)}
                        </td>
                        <td data-label="Denominator">{labelOf(item.denominatorScope)}</td>
                        <td data-label="Trend">
                          <Sparkline values={item.sparkline.map((point) => point.rate)} />
                        </td>
                        <td data-label="Preview">
                          <button
                            type="button"
                            className="btn btn-sm"
                            aria-haspopup="dialog"
                            aria-label={`Preview ${item.metricId}`}
                            onClick={() => replace({ preview: item.metricId })}
                          >
                            Preview
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {data.items.length === 0 && <p className="fine">No metrics in this scope.</p>}
              <div className="table-foot">
                <Pager page={data.page} onPage={(next) => replace({ page: next <= 1 ? null : String(next) })} noun="metrics" />
                <div className="field field-inline">
                  <span className="field-label">Rows per page</span>
                  <MenuSelect
                    label="Rows per page"
                    allowEmpty={false}
                    options={[10, 25, 50, 100].map((size) => ({ value: String(size), label: String(size) }))}
                    selected={[String(pageSize)]}
                    onChange={(next) => {
                      const value = next[0]
                      if (!value) return
                      replace({ pageSize: value === '25' ? null : value, page: null })
                    }}
                  />
                </div>
              </div>
            </div>
            {preview && (
              <PreviewModal
                key={preview}
                metricId={preview}
                filters={filters}
                sparkline={
                  data.items
                    .find((item) => item.metricId === preview)
                    ?.sparkline.map((point) => ({ label: formatMonth(point.month), value: point.rate })) ?? []
                }
                onClose={() => replace({ preview: null })}
              />
            )}
          </>
        )}
      </QueryPanel>
    </div>
  )
}
