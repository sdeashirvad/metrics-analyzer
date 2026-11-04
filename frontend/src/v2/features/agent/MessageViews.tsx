import { useState } from 'react'
import { exportQueryUrl } from '../../api/agents'
import type { AnalysisContent, DataExplorerContent, Message, QueryResult } from '../../api/types'
import { Markdown } from '../../components/markdown'
import { formatInt } from '../../format'
import { remainingProse } from './datasetText'

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

function QueryBlock({ query, conversationId, messageId }: { query: QueryResult; conversationId?: string; messageId?: string }) {
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
  const rows = query.rowCount == null ? null : `${formatInt(query.rowCount)} ${query.rowCount === 1 ? 'row' : 'rows'}`
  return (
    <div className="stack">
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
      {query.error && <p className="callout warn">{query.error.message}</p>}
      {query.sql && (
        <>
          <pre className="code" aria-label={`SQL for query ${query.index + 1}`}>
            {query.sql}
          </pre>
          <button type="button" className="btn btn-sm" onClick={() => void copySql()}>
            {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy SQL'}
          </button>
        </>
      )}
      {query.truncation.note && <p className="fine">{query.truncation.note}</p>}
      {query.columns.length > 0 && (
        <div className="table-wrap">
          <table className="mini-table">
            <thead>
              <tr>
                {query.columns.map((column) => (
                  <th key={column.name}>{column.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.rows.map((row, index) => (
                <tr key={index}>
                  {row.map((value, cell) => (
                    <td key={query.columns[cell]?.name ?? cell}>{cellText(value)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.exportable && conversationId && messageId && (
        <a href={exportQueryUrl(conversationId, messageId, query.index)}>Export</a>
      )}
    </div>
  )
}

export function AnalysisView({
  content,
  onSuggest,
  conversationId,
  messageId,
}: {
  content: AnalysisContent
  onSuggest?: (text: string) => void
  conversationId?: string
  messageId?: string
}) {
  return (
    <div className="stack">
      {content.notices.map((notice) => (
        <p key={notice.code} className="fine">
          {notice.text}
        </p>
      ))}
      <Markdown text={content.text} />
      {content.warnings.filter((warning) => warning.code !== 'UNKNOWN_BLOCK_TYPE' && warning.code !== 'CHART_NOT_RENDERED').map((warning) => (
        <p key={warning.code} className="callout warn">
          {warning.message}
        </p>
      ))}
      {content.toolActivity.length > 0 && (
        <ul className="list">
          {content.toolActivity.map((tool) => (
            <li key={tool.toolUseId}>
              <span className="grow">{toolLabel(tool.toolName) ?? 'Query'}</span>
              <span className="fine">{tool.status}</span>
            </li>
          ))}
        </ul>
      )}
      {content.evidence.map((query) => (
        <QueryBlock key={query.toolUseId} query={query} conversationId={conversationId} messageId={messageId} />
      ))}
      {content.suggestedFollowUps.length > 0 &&
        (onSuggest ? (
          <div className="sugg">
            {content.suggestedFollowUps.map((text) => (
              <button key={text} type="button" onClick={() => onSuggest(text)}>
                {text}
              </button>
            ))}
          </div>
        ) : (
          <ul className="list">
            {content.suggestedFollowUps.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        ))}
    </div>
  )
}

export function DatasetView({ content, conversationId, messageId }: { content: DataExplorerContent; conversationId?: string; messageId?: string }) {
  const prose = remainingProse(content.agentText)
  return (
    <div className="stack">
      {prose && <Markdown text={prose} />}
      {content.interpretedIntent && (
        <section className="stack">
          <h3 className="sec-label">Interpreted intent</h3>
          <p>{content.interpretedIntent}</p>
        </section>
      )}
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
      {content.warnings.filter((warning) => warning.code !== 'UNKNOWN_BLOCK_TYPE' && warning.code !== 'CHART_NOT_RENDERED').map((warning) => (
        <p key={warning.code} className="callout warn">
          {warning.message}
        </p>
      ))}
      {content.noQueryExecuted ? (
        <p>No query was run.</p>
      ) : (
        content.queries.map((query) => <QueryBlock key={query.toolUseId || query.index} query={query} conversationId={conversationId} messageId={messageId} />)
      )}
    </div>
  )
}

export function MessageBody({ message, onSuggest }: { message: Message; onSuggest?: (text: string) => void }) {
  const content = message.content
  if (content.kind === 'user') return <p>{content.text}</p>
  if (content.kind === 'analysis') {
    return <AnalysisView content={content} onSuggest={onSuggest} conversationId={message.conversationId} messageId={message.messageId} />
  }
  if (content.kind === 'dataset') {
    return <DatasetView content={content} conversationId={message.conversationId} messageId={message.messageId} />
  }
  return <p className="fine">This response is not in a format this page can show.</p>
}
