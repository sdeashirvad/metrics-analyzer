import { useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { getMetricPreview } from '../../api/portfolio'
import type { ScopeFilters } from '../../api/types'
import { LineChart } from '../../components/charts/Charts'
import { Dash, Provisional, QueryPanel, RagPill, useFocusContain } from '../../components/present'
import { describeFilters, useLegalEntityNames } from '../../components/scopeLabels'
import { Skeleton } from '../../components/Skeleton'
import { AskAgentLink } from '../../components/ui/AskAgentLink'
import { formatInt, formatMonth, formatPercent, formatPp, labelOf } from '../../format'
import { useApiQuery } from '../../hooks/useApiQuery'
import { useLinkState } from '../../hooks/useOrigin'
import { scopeKey, scopedTo } from '../../scopePath'

/**
 * Centred modal preview of one register metric. It overlays the page, so the table never changes width.
 * Escape and the backdrop close it, focus enters it and returns to the row control that opened it.
 */
export function PreviewModal({
  metricId,
  filters,
  sparkline,
  onClose,
}: {
  metricId: string
  filters: ScopeFilters
  sparkline: Array<{ label: string; value: number | null }>
  onClose: () => void
}) {
  const linkState = useLinkState('Back')
  const agentState = useLinkState(`Back to ${metricId}`)
  const ref = useRef<HTMLDivElement>(null)
  const titleId = useId()
  useFocusContain(ref, onClose)
  const names = useLegalEntityNames()
  const query = useApiQuery('metric-preview', `${metricId}|${scopeKey(filters)}`, () => getMetricPreview(metricId, filters))
  const summary = scopedTo(`/register/${encodeURIComponent(metricId)}`, filters)
  const investigation = scopedTo(`/investigate/metrics/${encodeURIComponent(metricId)}`, filters)
  const scope = describeFilters(filters, names)

  return createPortal(
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        ref={ref}
        className="modal preview-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-head">
          <div className="modal-title">
            <p className="eyebrow">Metric preview</p>
            <h2 id={titleId} tabIndex={-1} data-initial-focus>
              {metricId}
            </h2>
          </div>
          <div className="modal-head-end">
            {query.data && <RagPill rag={query.data.rag} />}
            <button type="button" className="btn btn-quiet btn-sm" onClick={onClose}>
              Close
            </button>
          </div>
        </header>
        <div className="modal-body">
          <QueryPanel query={query} skeleton={<Skeleton shape="preview" label="Loading the preview" />}>
            {(data) => (
              <>
                <dl className="preview-meta">
                  <div>
                    <dt>Period</dt>
                    <dd>
                      {formatMonth(data.month)}
                      {data.previousMonth && <span className="fine"> vs {formatMonth(data.previousMonth)}</span>}
                    </dd>
                  </div>
                  <div>
                    <dt>Scope</dt>
                    <dd>{scope.length ? scope.join(' · ') : 'Default scope'}</dd>
                  </div>
                </dl>
                <div className="preview-kpis">
                  <div className="stat preview-result">
                    <div className="fine">
                      Rate <Provisional id="PD-01" of="preview rate" />
                    </div>
                    <div className="kpi-value num">
                      <Dash value={formatPercent(data.rate.rate)} />
                    </div>
                    <p className="fine">
                      {formatInt(data.rate.numerator)} / {formatInt(data.rate.denominator)} · <Dash value={formatPp(data.rate.deltaPp)} />
                    </p>
                  </div>
                  <div className="stat">
                    <div className="fine">Applications</div>
                    <div className="num preview-stat">{formatInt(data.coverage.applications)}</div>
                  </div>
                  <div className="stat">
                    <div className="fine">Non-compliant rows</div>
                    <div className="num preview-stat">{formatInt(data.compliance.nonCompliant)}</div>
                  </div>
                </div>
                <section aria-label="Definition">
                  <h3 className="sec-label">Definition</h3>
                  <p className="preview-def">{data.definition.summary}</p>
                  <p className="fine">
                    Denominator: {labelOf(data.definition.denominatorScope)} <Provisional of="denominator scope" />
                  </p>
                </section>
                <section aria-label="Supporting values">
                  <h3 className="sec-label">Supporting values</h3>
                  <ul className="list preview-list">
                    <li>
                      <span className="grow">Compliant rows</span>
                      <span className="num">{formatInt(data.compliance.compliant)}</span>
                    </li>
                    <li>
                      <span className="grow">Pending rows</span>
                      <span className="num">{formatInt(data.compliance.pending)}</span>
                    </li>
                    <li>
                      <span className="grow">Not applicable rows</span>
                      <span className="num">{formatInt(data.compliance.notApplicable)}</span>
                    </li>
                    <li>
                      <span className="grow">Tests passed / failed</span>
                      <span className="num">
                        {formatInt(data.testing.pass)} / {formatInt(data.testing.fail)}
                      </span>
                    </li>
                  </ul>
                </section>
                {sparkline.length > 0 && (
                  <section aria-label="Trend">
                    <h3 className="sec-label">Trend</h3>
                    <LineChart points={sparkline} />
                  </section>
                )}
              </>
            )}
          </QueryPanel>
        </div>
        <footer className="modal-foot">
          <Link className="btn btn-primary" to={summary} state={linkState}>
            Open Summary / Details
          </Link>
          <Link className="btn" to={investigation} state={linkState}>
            Open Investigation
          </Link>
          <AskAgentLink
            to={scopedTo('/agent', filters, { focusMetric: metricId, ctx: 'preview' })}
            label="Chat with Agent"
            variant="button"
            state={agentState}
          />
        </footer>
      </div>
    </div>,
    document.body,
  )
}
