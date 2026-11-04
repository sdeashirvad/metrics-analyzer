import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { bindConversationStorage, upsertConversation, type StoredConversation } from '../../agent/conversationStore'
import { HistoryRail, matchesSearch } from './HistoryRail'

function storage() {
  const data = new Map<string, string>()
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value)
    },
    removeItem: (key: string) => {
      data.delete(key)
    },
  }
}

const entry = (id: string, title: string, agentKey: 'analysis' | 'data', at: string): StoredConversation => ({
  conversationId: id,
  threadId: 1,
  agentKey,
  title,
  createdAt: at,
  lastActivityAt: at,
  contextSummary: { chips: ['Oct 2026'], entrySurface: 'general' },
})

describe('HistoryRail', () => {
  beforeEach(() => bindConversationStorage(storage()))
  afterEach(() => bindConversationStorage(null))

  it('shows an empty state with a New conversation link', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <HistoryRail />
      </MemoryRouter>,
    )
    expect(html).toContain('No conversations yet')
    expect(html).toContain('New conversation')
    expect(html).toContain('Stored in this browser only')
    expect(html).not.toContain('Clear all history')
  })

  it('groups conversations, badges the agent, highlights the active one and offers delete', () => {
    const now = new Date().toISOString()
    upsertConversation(entry('a', 'What changed this month?', 'analysis', now))
    upsertConversation(entry('b', 'List failed tests', 'data', '2020-01-01T00:00:00Z'))
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <HistoryRail activeId="a" />
      </MemoryRouter>,
    )
    expect(html).toContain('Today')
    expect(html).toContain('Older')
    expect(html).toContain('history-badge analysis')
    expect(html).toContain('history-badge data')
    expect(html).toContain('aria-current="page"')
    expect(html).toContain('Delete conversation: What changed this month?')
    expect(html).toContain('Clear all history')
  })

  it('matches search on title, agent and context chips', () => {
    const item = entry('a', 'What changed this month?', 'analysis', '2026-11-04T00:00:00Z')
    expect(matchesSearch(item, 'changed')).toBe(true)
    expect(matchesSearch(item, 'analysis')).toBe(true)
    expect(matchesSearch(item, 'oct 2026')).toBe(true)
    expect(matchesSearch(item, 'tier')).toBe(false)
    expect(matchesSearch(item, '   ')).toBe(true)
  })
})
