import { useState } from 'react'
import type { TrendPoint } from '../../backend/contracts/types'
import { api } from '../../backend/services'
import { StatusBadge } from '../../components/StatusBadge'
import { DataTable } from '../../components/ui/DataTable'
import { Pager } from '../../components/ui/Pager'
import { SelectField } from '../../components/ui/Select'
import { EvidenceTag } from '../../components/ui/ProvenanceChip'
import { SectionEmpty, SectionError, SectionLoading, SectionUnavailable } from '../../components/ui/SectionState'
import { TabPanel, Tabs } from '../../components/ui/Tabs'
import { formatDate } from '../../domain/format'
import { useQuery } from '../../hooks/useQuery'
import { useUrlState } from '../../hooks/useUrlState'

export function useControlNotes(controlId: string) {
  return useQuery(`dq-notes:${controlId}`, '', () => api.getControlNotes(controlId))
}

export function DeskBreakdownCard({ controlId, trend, hasDeskSplit }: { controlId: string; trend: TrendPoint[]; hasDeskSplit: boolean }) {
  const dates = trend.map((point) => point.date).reverse()
  const [date, setDate] = useState<string>(dates[0] ?? '')
  const desks = useQuery(`dq-desks:${controlId}`, date, () => api.getDeskBreakdown(controlId, date || undefined))

  if (!hasDeskSplit) {
    return (
      <section className="card" aria-labelledby="breakdown-title">
        <h2 id="breakdown-title">Breakdown</h2>
        <SectionUnavailable title="Desk split not supplied for this control." body="dq_results_by_desk covers eight of the workbook's controls. This is not one of them." />
      </section>
    )
  }

  const data = desks.data
  const max = Math.max(...(data?.rows ?? []).map((row) => row.failed), 1)
  return (
    <section className="card" aria-labelledby="breakdown-title" aria-busy={desks.refreshing}>
      <div className="card-head">
        <h2 id="breakdown-title">Desk breakdown</h2>
        <SelectField label="Date" value={date} onChange={setDate} options={dates.map((item) => ({ value: item, label: formatDate(item) }))} />
      </div>
      <p className="fine">Bars show failed-record volume, not the lowest pass rate. Shares are of this control's failures on the chosen date.</p>
      {data ? (
        data.available ? (
          <DataTable
            caption={`Desk breakdown for ${controlId} on ${formatDate(data.date)}`}
            refreshing={desks.refreshing}
            head={
              <tr>
                <th scope="col">Desk</th>
                <th scope="col">Failed</th>
                <th scope="col">Share of failures</th>
                <th scope="col">Pass rate</th>
                <th scope="col">RAG</th>
              </tr>
            }
          >
            {data.rows.map((row) => (
              <tr key={row.deskId}>
                <td>{row.deskName}</td>
                <td className="num">
                  <span className="cell-bar">
                    <span style={{ width: `${(row.failed / max) * 100}%` }} />
                  </span>
                  {row.failed.toLocaleString()} <span className="muted">of {row.total.toLocaleString()}</span>
                </td>
                <td className="num">{row.shareOfFailures.toFixed(1)}%</td>
                <td className="num">{row.passRate.toFixed(2)}%</td>
                <td>
                  <StatusBadge status={row.status} />
                </td>
              </tr>
            ))}
          </DataTable>
        ) : (
          <SectionUnavailable title={data.reason} />
        )
      ) : desks.error ? (
        <SectionError message={desks.error.message} onRetry={desks.retry} />
      ) : (
        <SectionLoading label="Loading desk rows" />
      )}
    </section>
  )
}

type EvidenceTab = 'exceptions' | 'events' | 'commentary'

export function EvidenceTabs({ controlId }: { controlId: string }) {
  const [params, update] = useUrlState()
  const raw = params.get('tab')
  const tab: EvidenceTab = raw === 'events' || raw === 'commentary' ? raw : 'exceptions'
  const page = Math.max(1, Number(params.get('xpage') ?? '1') || 1)
  const status = params.get('xstatus') ?? ''
  const notes = useControlNotes(controlId)
  const exceptions = useQuery(`dq-exceptions:${controlId}`, `${status}|${page}`, () =>
    api.listExceptions({ controlId, status: status || undefined, page, pageSize: 25 }),
  )
  const counts = useQuery(`dq-exception-count:${controlId}`, '', () => api.listExceptions({ controlId, pageSize: 1 }))

  const label = (text: string, count: number | undefined) => (
    <>
      {text} {count != null && <span className="seg-count num">{count}</span>}
    </>
  )

  return (
    <section className="card evidence" aria-labelledby="evidence-title">
      <h2 id="evidence-title">Workbook evidence</h2>
      <Tabs<EvidenceTab>
        label="Evidence"
        idPrefix="evidence"
        value={tab}
        onChange={(next) => update({ tab: next === 'exceptions' ? null : next }, { commit: false })}
        tabs={[
          { id: 'exceptions', label: label('Exceptions', counts.data?.total) },
          { id: 'events', label: label('Events', notes.data?.events.length) },
          { id: 'commentary', label: label('Commentary', notes.data?.commentary.length) },
        ]}
      />
      {tab === 'exceptions' && (
        <TabPanel idPrefix="evidence" id="exceptions" className="tab-body">
          <div className="row tab-tools">
            <SelectField
              label="Status"
              value={status}
              onChange={(next) => update({ xstatus: next || null, xpage: null }, { commit: true })}
              options={[{ value: '', label: 'All' }, ...(counts.data?.statuses ?? exceptions.data?.statuses ?? []).map((item) => ({ value: item, label: item }))]}
            />
          </div>
          {exceptions.data ? (
            exceptions.data.total === 0 ? (
              <SectionEmpty title="No exception rows for this control and status." />
            ) : (
              <>
                <DataTable
                  caption={`Exceptions for ${controlId}`}
                  refreshing={exceptions.refreshing}
                  minWidth={760}
                  head={
                    <tr>
                      <th scope="col">Exception</th>
                      <th scope="col">Date</th>
                      <th scope="col">Desk</th>
                      <th scope="col">Field and value</th>
                      <th scope="col">Reason</th>
                      <th scope="col">Status</th>
                      <th scope="col">Age</th>
                    </tr>
                  }
                >
                  {exceptions.data.items.map((row) => (
                    <tr key={row.id}>
                      <td className="mono">{row.id}</td>
                      <td>{formatDate(row.date)}</td>
                      <td>{row.deskName}</td>
                      <td>
                        <span className="mono">{row.field}</span> {row.value ? <span className="muted">“{row.value}”</span> : <span className="muted">empty</span>}
                      </td>
                      <td>{row.reason}</td>
                      <td>{row.status}</td>
                      <td className="num">{row.ageingDays}d</td>
                    </tr>
                  ))}
                </DataTable>
                <Pager
                  page={exceptions.data.page}
                  pageSize={exceptions.data.pageSize}
                  total={exceptions.data.total}
                  label="Exception pages"
                  onPage={(next) => update({ xpage: next > 1 ? String(next) : null }, { commit: true })}
                />
              </>
            )
          ) : exceptions.error ? (
            <SectionError message={exceptions.error.message} onRetry={exceptions.retry} />
          ) : (
            <SectionLoading label="Loading exceptions" />
          )}
        </TabPanel>
      )}
      {tab === 'events' && (
        <TabPanel idPrefix="evidence" id="events" className="tab-body">
          {notes.data ? (
            notes.data.events.length === 0 ? (
              <SectionEmpty title="No change or incident rows list this control." />
            ) : (
              <ul className="evidence-list">
                {notes.data.events.map((event) => (
                  <li key={event.id}>
                    <div className="row">
                      <span className="mono">{event.id}</span>
                      <strong>{formatDate(event.date)}</strong>
                      <span className="muted">{event.type}</span>
                      <EvidenceTag kind="linked" />
                    </div>
                    <p>{event.description}</p>
                    <p className="fine">Desks: {event.deskIds}</p>
                  </li>
                ))}
              </ul>
            )
          ) : (
            <SectionLoading label="Loading events" />
          )}
        </TabPanel>
      )}
      {tab === 'commentary' && (
        <TabPanel idPrefix="evidence" id="commentary" className="tab-body">
          {notes.data ? (
            notes.data.commentary.length === 0 ? (
              <SectionEmpty title="No analyst commentary was supplied for this control." />
            ) : (
              <ul className="evidence-list">
                {notes.data.commentary.map((note) => (
                  <li key={`${note.date}-${note.cause}`}>
                    <div className="row">
                      <strong>{formatDate(note.date)}</strong>
                      <span className="muted">{note.author}</span>
                      <StatusBadge status={note.ragAtTime} label={`RAG at time: ${note.ragAtTime}`} />
                      <EvidenceTag kind="hypothesis" label="Supplied commentary" />
                    </div>
                    <p>{note.text}</p>
                    <p className="fine">
                      Stated cause: {note.cause} · Stated path: {note.path}
                    </p>
                  </li>
                ))}
              </ul>
            )
          ) : (
            <SectionLoading label="Loading commentary" />
          )}
        </TabPanel>
      )}
    </section>
  )
}
