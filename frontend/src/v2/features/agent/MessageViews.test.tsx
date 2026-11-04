import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { AnalysisContent, DataExplorerContent, Message, QueryResult } from '../../api/types'
import { MessageBody } from './MessageViews'

const query: QueryResult = {
  index: 0,
  toolUseId: 'tool-1',
  toolName: 'system_execute_sql',
  sql: 'SELECT COUNT(*) AS N FROM APPLICATION_COMPLIANCE',
  queryId: '01b2-query-id',
  status: 'success',
  error: null,
  columns: [{ name: 'N', type: 'FIXED', nullable: false, scale: 0 }],
  rows: [['923']],
  rowCount: 1,
  rowsReturned: 1,
  truncated: false,
  truncation: { reason: null, limit: null, note: null },
  exportable: false,
}

function message(content: Message['content'], agentKey: 'analysis' | 'data'): Message {
  return { messageId: 'm1', conversationId: 'c1', role: 'assistant', agentKey, runId: null, createdAt: '2026-11-04T10:00:00Z', content }
}

describe('Data Explorer message', () => {
  const content: DataExplorerContent = {
    kind: 'dataset',
    interpretedIntent: 'Count the applications reporting.',
    assumptions: ['Latest month', 'Business organisation tree'],
    agentText:
      'Here is the count.\n\n**Interpreted intent**\nCount the applications reporting.\n\n**Assumptions**\n- Latest month\n- Business organisation tree\n\n**Generated SQL**\n```sql\nSELECT COUNT(*) AS N FROM APPLICATION_COMPLIANCE\n```\n\n**Result dataset**\n| N |\n| - |\n| 923 |',
    noQueryExecuted: false,
    queries: [query],
    primaryQueryIndex: 0,
    warnings: [],
  }

  it('shows the intent, the SQL, the query id and the rows once each', () => {
    const html = renderToStaticMarkup(<MessageBody message={message(content, 'data')} />)
    expect(html.match(/Count the applications reporting\./g)).toHaveLength(1)
    expect(html.match(/SELECT COUNT\(\*\) AS N FROM APPLICATION_COMPLIANCE/g)).toHaveLength(1)
    expect(html).toContain('01b2-query-id')
    expect(html).toContain('<th scope="col" class="num" title="N">N</th>')
    expect(html).toContain('<td class="num">923</td>')
    expect(html).toContain('Here is the count.')
    expect(html).toContain('Assumptions')
    expect(html.match(/Latest month/g)).toHaveLength(1)
  })

  it('says no query ran when none did', () => {
    const html = renderToStaticMarkup(<MessageBody message={message({ ...content, queries: [], noQueryExecuted: true }, 'data')} />)
    expect(html).toContain('No query was run.')
  })
})

describe('Analysis message', () => {
  const content: AnalysisContent = {
    kind: 'analysis',
    text: '## What changed\nThe rate fell to **44.5%**.\n\n1. First reason\n2. Second reason\n\n| Group | Rows |\n| --- | --- |\n| A | 3 |',
    evidence: [query],
    toolActivity: [],
    suggestedFollowUps: ['Which division moved most?'],
    notices: [{ code: 'AGENT_GENERATED', text: 'Agent-generated. Explanations of cause are hypotheses until validated.' }],
    warnings: [],
  }

  it('renders Markdown, the evidence query and follow-up suggestions', () => {
    const html = renderToStaticMarkup(<MessageBody message={message(content, 'analysis')} onSuggest={() => undefined} />)
    expect(html).toContain('<strong>44.5%</strong>')
    expect(html).not.toContain('##')
    expect(html).toContain('<ol class="md-list">')
    expect(html).toContain('<th>Group</th>')
    expect(html).toContain('01b2-query-id')
    expect(html).toContain('Which division moved most?')
    expect(html).toContain('Agent-generated.')
  })
})
