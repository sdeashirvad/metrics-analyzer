import { useState } from 'react'
import { exportQueryUrl } from '../../api/agents'
import type { AnalysisContent, DataExplorerContent, Message, QueryResult } from '../../api/types'
import { Markdown } from '../../components/markdown'
import { formatInt } from '../../format'
import { remainingProse } from './datasetText'

const NUMERIC_TYPE = /^(fixed|real|number|numeric|decimal|float|double|int|integer|bigint|smallint)$/i

function isNumeric(type: string): boolean {
  return NUMERIC_TYPE.test(type.trim())
}

/** Display label for a column. The raw name stays available as the header's title. */
export function columnLabel(name: string): string {
  if (!/[_]/.test(name) && name !== name.toUpperCase()) return name
  if (name.length <= 3 && !name.includes('_')) return name
  const words = name.toLowerCase().replace(/_+/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function cellText(value: string | null): string {
  if (value == null || value === '') return ''
  return value
}

function toolLabel(name: string | null): string | null {
  if (!name) return null
  if (name === 'system_execute_sql') return 'Query'
  if (name === 'ApplicationComplianceAnalyst') return 'Analysis'
  return null
}

function rowsText(count: number | null): string | null {
  return count == null ? null : `${formatInt(count)} ${count === 1 ? 'row' : 'rows'}`
}

function plural(count: number, noun: string): string {
  return `${formatInt(count)} ${noun}${count === 1 ? '' : 's'}`
}

/** The rows a query returned, with its row count, truncation note and export link. */
function ResultTable({ query, conversationId, messageId }: { query: QueryResult; conversationId?: string; messageId?: string }) {
  if (query.error) return <p className="callout warn">{query.error.message}</p>
  if (query.columns.length === 0) {
    return query.status === 'empty' ? <p className="fine">The query returned no rows.</p> : null
  }
  const numeric = query.columns.map((column) => isNumeric(column.type))
  const rows = rowsText(query.rowCount)
  return (
    <div className="result">
      <div className="table-wrap">
        <table className="mini-table result-table">
          <thead>
            <tr>
              {query.columns.map((column, index) => (
                <th key={column.name} scope="col" className={numeric[index] ? 'num' : undefined} title={column.name}>
                  {columnLabel(column.name)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {query.rows.map((row, index) => (
              <tr key={index}>
                {row.map((value, cell) => (
                  <td key={query.columns[cell]?.name ?? cell} className={numeric[cell] ? 'num' : undefined}>
                    {cellText(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="fine result-foot">
        {rows && <span>{rows}</span>}
        {query.truncation.note && <span>{query.truncation.note}</span>}
        {query.exportable && conversationId && messageId && <a href={exportQueryUrl(conversationId, messageId, query.index)}>Export</a>}
      </p>
    </div>
  )
}

/** How a query was run: status, query id and the generated SQL with a copy action. */
function QueryDetails({ query }: { query: QueryResult }) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  async function copySql() {
    if (!query.sql) return
    try {
      await navigator.clipboard.writeText(query.sql)
      setCopyState('copied')
      window.setTimeout(() => setCopyState('idle'), 2000)
    } catch {
      setCopyState('failed')
    }
  }
  const rows = rowsText(query.rowCount)
  return (
    <div className="query-details">
      <p className="fine">
        Query {query.index + 1}
        {toolLabel(query.toolName) ? ` · ${toolLabel(query.toolName)}` : ''} · {query.status}
        {rows ? ` · ${rows}` : ''}
      </p>
      {query.queryId && (
        <p className="fine">
          Query ID <code>{query.queryId}</code>
        </p>
      )}
      {query.sql && (
        <>
          <pre className="code" aria-label={`SQL for query ${query.index + 1}`}>
            {query.sql}
          </pre>
          <div className="row">
            <button type="button" className="btn btn-sm" onClick={() => void copySql()}>
              {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy SQL'}
            </button>
            <span className="sr-only" role="status">
              {copyState === 'copied' ? 'SQL copied' : ''}
            </span>
          </div>
        </>
      )}
    </div>
  )
}

function Warnings({ warnings }: { warnings: AnalysisContent['warnings'] }) {
  return (
    <>
      {warnings
        .filter((warning) => warning.code !== 'UNKNOWN_BLOCK_TYPE' && warning.code !== 'CHART_NOT_RENDERED')
        .map((warning) => (
          <p key={warning.code} className="callout warn">
            {warning.message}
          </p>
        ))}
    </>
  )
}

function FollowUps({ items, onSuggest }: { items: string[]; onSuggest?: (text: string) => void }) {
  if (items.length === 0) return null
  return (
    <section className="followups" aria-label="Suggested follow-ups">
      <p className="sec-label">Suggested follow-ups</p>
      {onSuggest ? (
        <div className="sugg">
          {items.map((text) => (
            <button key={text} type="button" onClick={() => onSuggest(text)}>
              {text}
            </button>
          ))}
        </div>
      ) : (
        <ul className="md-list">
          {items.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function AnalysisView({
  content,
  onSuggest,
  showFollowUps = true,
  conversationId,
  messageId,
}: {
  content: AnalysisContent
  onSuggest?: (text: string) => void
  showFollowUps?: boolean
  conversationId?: string
  messageId?: string
}) {
  const failedSteps = content.toolActivity.filter((tool) => tool.status === 'ERROR').length
  const rowTotal = content.evidence.reduce((sum, query) => sum + (query.rowCount ?? 0), 0)
  const hasEvidence = content.evidence.length > 0 || failedSteps > 0
  return (
    <div className="reply">
      {content.notices.map((notice) => (
        <p key={notice.code} className="reply-notice">
          {notice.text}
        </p>
      ))}
      <Markdown text={content.text} />
      <Warnings warnings={content.warnings} />
      {hasEvidence && (
        <details className="evidence">
          <summary>
            <span>Evidence</span>
            <span className="fine">
              {plural(content.evidence.length, 'query')}
              {rowTotal > 0 ? ` · ${plural(rowTotal, 'row')}` : ''} · SQL and query IDs
            </span>
          </summary>
          <div className="evidence-body">
            {failedSteps > 0 && <p className="callout warn">{plural(failedSteps, 'step')} returned an error.</p>}
            {content.evidence.map((query) => (
              <div key={query.toolUseId} className="evidence-item">
                <QueryDetails query={query} />
                <ResultTable query={query} conversationId={conversationId} messageId={messageId} />
              </div>
            ))}
          </div>
        </details>
      )}
      {showFollowUps && <FollowUps items={content.suggestedFollowUps} onSuggest={onSuggest} />}
    </div>
  )
}

export function DatasetView({ content, conversationId, messageId }: { content: DataExplorerContent; conversationId?: string; messageId?: string }) {
  const prose = remainingProse(content.agentText)
  const primary = content.noQueryExecuted
    ? undefined
    : (content.queries.find((query) => query.index === content.primaryQueryIndex) ?? content.queries[0])
  const others = content.queries.filter((query) => query !== primary)
  const hasDetails = content.assumptions.length > 0 || content.queries.length > 0
  return (
    <div className="reply">
      {prose && <Markdown text={prose} />}
      {content.interpretedIntent && (
        <p className="reply-intent">
          <span className="sec-label">Interpreted intent</span>
          <span>{content.interpretedIntent}</span>
        </p>
      )}
      <Warnings warnings={content.warnings} />
      {content.noQueryExecuted ? (
        <p>No query was run.</p>
      ) : (
        primary && <ResultTable query={primary} conversationId={conversationId} messageId={messageId} />
      )}
      {hasDetails && (
        <details className="evidence">
          <summary>
            <span>How this was computed</span>
            <span className="fine">
              {[content.assumptions.length > 0 ? plural(content.assumptions.length, 'assumption') : null, content.queries.length > 0 ? 'SQL and query ID' : null]
                .filter(Boolean)
                .join(' · ')}
            </span>
          </summary>
          <div className="evidence-body">
            {content.assumptions.length > 0 && (
              <section className="stack">
                <h3 className="sec-label">Assumptions</h3>
                <ul className="md-list">
                  {content.assumptions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            )}
            {primary && <QueryDetails query={primary} />}
            {others.map((query) => (
              <div key={query.toolUseId || query.index} className="evidence-item">
                <QueryDetails query={query} />
                <ResultTable query={query} conversationId={conversationId} messageId={messageId} />
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

export function MessageBody({ message, onSuggest, showFollowUps = true }: { message: Message; onSuggest?: (text: string) => void; showFollowUps?: boolean }) {
  const content = message.content
  if (content.kind === 'user') return <p>{content.text}</p>
  if (content.kind === 'analysis') {
    return (
      <AnalysisView
        content={content}
        onSuggest={onSuggest}
        showFollowUps={showFollowUps}
        conversationId={message.conversationId}
        messageId={message.messageId}
      />
    )
  }
  if (content.kind === 'dataset') {
    return <DatasetView content={content} conversationId={message.conversationId} messageId={message.messageId} />
  }
  return <p className="fine">This response is not in a format this page can show.</p>
}
