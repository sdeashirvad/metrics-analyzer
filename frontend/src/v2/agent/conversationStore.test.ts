import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Message } from '../api/types'
import {
  bindConversationStorage,
  clearConversations,
  deleteConversation,
  groupByRecency,
  hydrateTranscripts,
  patchConversation,
  readConversations,
  saveConversationMessages,
  upsertConversation,
  type StoredConversation,
} from './conversationStore'
import { bindTranscriptBackend, loadTranscript, memoryBackend, mergeMessages } from './transcriptStore'

function memory() {
  const data = new Map<string, string>()
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value)
    },
    removeItem: (key: string) => {
      data.delete(key)
    },
    raw: (key = 'ma2:conversations:v2') => data.get(key) ?? '',
    seed: (key: string, value: string) => data.set(key, value),
  }
}

const sample = (id: string, at: string): StoredConversation => ({
  conversationId: id,
  threadId: 1,
  agentKey: 'analysis',
  title: 'Portfolio summary',
  createdAt: at,
  lastActivityAt: at,
  contextSummary: { chips: ['Oct'], entrySurface: 'general' },
})

function message(id: string, at: string, role: 'user' | 'assistant' = 'user'): Message {
  return {
    messageId: id,
    conversationId: 'c',
    role,
    agentKey: 'analysis',
    runId: 'secret-run-token',
    createdAt: at,
    content: role === 'user' ? { kind: 'user', text: `question ${id}`, contextHash: null } : { kind: 'analysis', text: 'answer', evidence: [], toolActivity: [], suggestedFollowUps: [], notices: [], warnings: [] },
  }
}

describe('conversationStore', () => {
  let backend = memoryBackend()
  beforeEach(() => {
    backend = memoryBackend()
    bindTranscriptBackend(backend)
  })
  afterEach(() => {
    bindConversationStorage(null)
    bindTranscriptBackend(null)
  })

  it('keeps metadata only in the index and drops anything else', () => {
    const store = memory()
    bindConversationStorage(store)
    upsertConversation({
      ...sample('handle-a', '2025-11-01T00:00:00Z'),
      ...({ message: 'secret text', sql: 'select 1', rows: [[1]] } as object),
    })
    const raw = store.raw()
    expect(raw).not.toContain('secret text')
    expect(raw).not.toContain('select 1')
    expect(JSON.parse(raw)).toEqual({
      version: 2,
      items: [
        {
          conversationId: 'handle-a',
          threadId: 1,
          agentKey: 'analysis',
          title: 'Portfolio summary',
          createdAt: '2025-11-01T00:00:00Z',
          lastActivityAt: '2025-11-01T00:00:00Z',
          contextSummary: { chips: ['Oct'], entrySurface: 'general' },
        },
      ],
    })
  })

  it('moves a version 1 list to the versioned key without losing entries', () => {
    const store = memory()
    store.seed('ma2:conversations', JSON.stringify([sample('old-1', '2025-01-01T00:00:00Z'), sample('old-2', '2025-01-02T00:00:00Z')]))
    bindConversationStorage(store)
    expect(readConversations().map((item) => item.conversationId)).toEqual(['old-2', 'old-1'])
    expect(JSON.parse(store.raw()).version).toBe(2)
    expect(store.raw('ma2:conversations')).toBe('')
  })

  it('never drops conversations to stay under a count, and shows each id once', () => {
    bindConversationStorage(memory())
    for (let index = 0; index < 120; index += 1) {
      upsertConversation(sample(`c-${index}`, new Date(Date.UTC(2025, 0, 1, 0, index)).toISOString()))
    }
    upsertConversation({ ...sample('c-5', '2026-01-01T00:00:00Z'), title: 'Renamed' })
    const saved = readConversations()
    expect(saved).toHaveLength(120)
    expect(saved[0]?.conversationId).toBe('c-5')
    expect(saved.filter((item) => item.conversationId === 'c-5')).toHaveLength(1)
  })

  it('saves messages in the transcript store, strips run tokens and de-duplicates', async () => {
    bindConversationStorage(memory())
    upsertConversation(sample('c', '2025-11-01T00:00:00Z'))
    const first = [message('1', '2025-11-01T00:00:01Z'), message('2', '2025-11-01T00:00:02Z', 'assistant')]
    expect((await saveConversationMessages({ conversationId: 'c', agentKey: 'analysis' }, first, null)).ok).toBe(true)
    await saveConversationMessages({ conversationId: 'c', agentKey: 'analysis' }, [...first, message('3', '2025-11-01T00:00:03Z')], null)
    const saved = await loadTranscript('c')
    expect(saved?.messages.map((item) => item.messageId)).toEqual(['1', '2', '3'])
    expect(JSON.stringify(saved)).not.toContain('secret-run-token')
    expect(readConversations()[0]).toMatchObject({ hasTranscript: true, messageCount: 3 })
  })

  it('reports a full browser without deleting anything', async () => {
    bindConversationStorage(memory())
    upsertConversation(sample('keep', '2025-11-01T00:00:00Z'))
    await saveConversationMessages({ conversationId: 'keep', agentKey: 'analysis' }, [message('1', '2025-11-01T00:00:01Z')], null)
    const full = Object.assign(new Error('full'), { name: 'QuotaExceededError' })
    bindTranscriptBackend(memoryBackend({ failWith: full }))
    const result = await saveConversationMessages({ conversationId: 'keep', agentKey: 'analysis' }, [message('2', '2025-11-01T00:00:02Z')], null)
    expect(result).toEqual({ ok: false, reason: 'quota' })
    expect(readConversations().map((item) => item.conversationId)).toEqual(['keep'])
  })

  it('deletes one conversation and clears all on request', async () => {
    bindConversationStorage(memory())
    for (const id of ['a', 'b', 'c']) {
      upsertConversation(sample(id, '2025-11-01T00:00:00Z'))
      await saveConversationMessages({ conversationId: id, agentKey: 'analysis' }, [message('1', '2025-11-01T00:00:01Z')], null)
    }
    await deleteConversation('b')
    expect(readConversations().map((item) => item.conversationId).sort()).toEqual(['a', 'c'])
    expect(await loadTranscript('b')).toBeNull()
    expect(await loadTranscript('a')).not.toBeNull()
    await clearConversations()
    expect(readConversations()).toEqual([])
    expect(backend.size()).toBe(0)
  })

  it('fills in missing transcripts from the server and stops when a fetch fails', async () => {
    bindConversationStorage(memory())
    upsertConversation(sample('one', '2025-11-01T00:00:00Z'))
    upsertConversation(sample('two', '2025-11-02T00:00:00Z'))
    patchConversation('two', { unavailable: true })
    const seen: string[] = []
    const saved = await hydrateTranscripts(async (id) => {
      seen.push(id)
      return { messages: [message('1', '2025-11-01T00:00:01Z')], context: { chips: ['Oct'], lines: [] } }
    })
    expect(saved).toBe(1)
    expect(seen).toEqual(['one'])
    expect((await loadTranscript('one'))?.context?.chips).toEqual(['Oct'])
    upsertConversation(sample('three', '2025-11-03T00:00:00Z'))
    expect(await hydrateTranscripts(async () => Promise.reject(new Error('offline')))).toBe(0)
    expect(readConversations().some((item) => item.conversationId === 'three' && item.hasTranscript)).toBe(false)
  })

  it('merges messages by id in time order', () => {
    const merged = mergeMessages([message('2', '2025-01-01T00:00:02Z')], [message('1', '2025-01-01T00:00:01Z'), message('2', '2025-01-01T00:00:02Z')])
    expect(merged.map((item) => item.messageId)).toEqual(['1', '2'])
  })

  it('groups history by local calendar day', () => {
    const now = new Date(2026, 10, 4, 15, 0, 0)
    const at = (days: number) => new Date(2026, 10, 4 - days, 9, 0, 0).toISOString()
    const groups = groupByRecency(
      [sample('t', at(0)), sample('y', at(1)), sample('w', at(5)), sample('o', at(12))],
      now,
    )
    expect(groups.map((group) => [group.name, group.items.map((item) => item.conversationId)])).toEqual([
      ['Today', ['t']],
      ['Yesterday', ['y']],
      ['Previous 7 days', ['w']],
      ['Older', ['o']],
    ])
  })
})
