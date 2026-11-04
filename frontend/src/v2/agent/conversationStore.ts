import { useEffect, useState } from 'react'
import type { AgentKey, ConversationContextSummary, Message, SavedConversation } from '../api/types'
import { clearTranscripts, deleteTranscript, loadTranscript, saveTranscript, type SaveResult } from './transcriptStore'

/**
 * Conversation history kept in this browser.
 *
 * The index (metadata only) is in localStorage under a versioned key. Messages are in IndexedDB
 * (transcriptStore.ts). Nothing is deleted unless the user deletes it, and no secrets are stored.
 */
const LIST_KEY = 'ma2:conversations:v2'
const LEGACY_KEY = 'ma2:conversations'
const VERSION = 2

export interface StoredConversation extends SavedConversation {
  unavailable?: boolean
  /** Number of messages saved in this browser, when a transcript exists. */
  messageCount?: number
  /** True once the messages are saved in this browser (IndexedDB). */
  hasTranscript?: boolean
}

type Memory = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

let override: Memory | null = null
const listeners = new Set<() => void>()

export function bindConversationStorage(store: Memory | null) {
  override = store
}

function memory(): Memory | null {
  if (override) return override
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

function isAgentKey(value: unknown): value is AgentKey {
  return value === 'analysis' || value === 'data'
}

function isStored(value: unknown): value is StoredConversation {
  if (!value || typeof value !== 'object') return false
  const row = value as StoredConversation
  return typeof row.conversationId === 'string' && isAgentKey(row.agentKey) && typeof row.title === 'string'
}

/** Index entries carry metadata only. Messages live in IndexedDB. */
function sanitize(item: StoredConversation): StoredConversation {
  const saved: StoredConversation = {
    conversationId: item.conversationId,
    threadId: item.threadId,
    agentKey: item.agentKey,
    title: item.title,
    createdAt: item.createdAt,
    lastActivityAt: item.lastActivityAt,
  }
  if (item.contextSummary) {
    saved.contextSummary = { chips: item.contextSummary.chips, entrySurface: item.contextSummary.entrySurface }
  }
  if (item.lastRunId) saved.lastRunId = item.lastRunId
  if (item.unavailable) saved.unavailable = true
  if (typeof item.messageCount === 'number') saved.messageCount = item.messageCount
  if (item.hasTranscript) saved.hasTranscript = true
  return saved
}

/** Order, and drop repeats of the same conversation id. The newest entry wins. */
function normalise(items: StoredConversation[]): StoredConversation[] {
  const byId = new Map<string, StoredConversation>()
  for (const item of items) {
    const current = byId.get(item.conversationId)
    if (!current || current.lastActivityAt <= item.lastActivityAt) byId.set(item.conversationId, item)
  }
  return [...byId.values()].sort((a, b) => (a.lastActivityAt < b.lastActivityAt ? 1 : a.lastActivityAt > b.lastActivityAt ? -1 : 0))
}

function parseList(text: string | null): StoredConversation[] | null {
  if (!text) return null
  try {
    const parsed = JSON.parse(text) as unknown
    const list = Array.isArray(parsed) ? parsed : (parsed as { items?: unknown })?.items
    if (!Array.isArray(list)) return null
    return list.filter(isStored).map(sanitize)
  } catch {
    return null
  }
}

/** Read the history index. The first read after an upgrade moves the old list to the versioned key. */
export function readConversations(): StoredConversation[] {
  const store = memory()
  if (!store) return []
  const current = parseList(store.getItem(LIST_KEY))
  if (current) return normalise(current)
  const legacy = parseList(store.getItem(LEGACY_KEY))
  if (!legacy) return []
  const migrated = normalise(legacy)
  try {
    store.setItem(LIST_KEY, JSON.stringify({ version: VERSION, items: migrated }))
    store.removeItem(LEGACY_KEY)
  } catch {
    // Keep the old list readable when the new one cannot be written.
  }
  return migrated
}

export type IndexWrite = { ok: true } | { ok: false; reason: 'quota' | 'unavailable' }

function writeConversations(items: StoredConversation[]): IndexWrite {
  const store = memory()
  if (!store) return { ok: false, reason: 'unavailable' }
  try {
    store.setItem(LIST_KEY, JSON.stringify({ version: VERSION, items: normalise(items).map(sanitize) }))
  } catch {
    return { ok: false, reason: 'quota' }
  }
  for (const listener of listeners) listener()
  return { ok: true }
}

export function upsertConversation(entry: StoredConversation): IndexWrite {
  const items = readConversations().filter((item) => item.conversationId !== entry.conversationId)
  items.push(sanitize(entry))
  return writeConversations(items)
}

export function patchConversation(conversationId: string, patch: Partial<StoredConversation>): IndexWrite {
  return writeConversations(
    readConversations().map((item) => (item.conversationId === conversationId ? sanitize({ ...item, ...patch, conversationId }) : item)),
  )
}

export function removeConversation(conversationId: string) {
  writeConversations(readConversations().filter((item) => item.conversationId !== conversationId))
}

/** Delete one conversation from this browser: the index entry and its saved messages. */
export async function deleteConversation(conversationId: string): Promise<void> {
  removeConversation(conversationId)
  await deleteTranscript(conversationId)
}

/** Delete every conversation saved in this browser. The caller asks for confirmation first. */
export async function clearConversations(): Promise<void> {
  writeConversations([])
  await clearTranscripts()
}

export function markConversationUnavailable(conversationId: string) {
  patchConversation(conversationId, { unavailable: true })
}

/**
 * Save the messages of a conversation in this browser and record that in the index.
 * Failures are reported, not hidden, and nothing else is deleted to make room.
 */
export async function saveConversationMessages(
  entry: Pick<StoredConversation, 'conversationId' | 'agentKey'>,
  messages: Message[],
  context: ConversationContextSummary | null,
): Promise<SaveResult> {
  const result = await saveTranscript({ conversationId: entry.conversationId, agentKey: entry.agentKey, messages, context })
  if (result.ok) {
    const saved = await loadTranscript(entry.conversationId)
    patchConversation(entry.conversationId, { hasTranscript: true, messageCount: saved?.messages.length ?? messages.length })
  }
  return result
}

/**
 * Fill in saved messages for index entries that have none, for example entries from before transcripts
 * were kept. Runs only when a fetch works, one at a time, and never removes anything.
 */
export async function hydrateTranscripts(
  fetchDetail: (conversationId: string) => Promise<{ messages: Message[]; context: ConversationContextSummary | null } | null>,
  limit = 5,
): Promise<number> {
  const pending = readConversations()
    .filter((item) => !item.hasTranscript && !item.unavailable)
    .slice(0, limit)
  let saved = 0
  for (const item of pending) {
    try {
      const detail = await fetchDetail(item.conversationId)
      if (!detail || detail.messages.length === 0) continue
      const result = await saveConversationMessages(item, detail.messages, detail.context)
      if (result.ok) saved += 1
      else if (result.reason === 'quota') break
    } catch {
      break
    }
  }
  return saved
}

export type HistoryGroupName = 'Today' | 'Yesterday' | 'Previous 7 days' | 'Older'

/** Group by the local calendar day of the last activity. Order inside a group is newest first. */
export function groupByRecency(items: StoredConversation[], now: Date = new Date()): Array<{ name: HistoryGroupName; items: StoredConversation[] }> {
  const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  const today = startOfDay(now)
  const day = 86_400_000
  const groups: Record<HistoryGroupName, StoredConversation[]> = { Today: [], Yesterday: [], 'Previous 7 days': [], Older: [] }
  for (const item of items) {
    const stamp = new Date(item.lastActivityAt).getTime()
    const age = Number.isNaN(stamp) ? Infinity : today - startOfDay(new Date(stamp))
    if (age <= 0) groups.Today.push(item)
    else if (age <= day) groups.Yesterday.push(item)
    else if (age <= 7 * day) groups['Previous 7 days'].push(item)
    else groups.Older.push(item)
  }
  return (Object.keys(groups) as HistoryGroupName[]).filter((name) => groups[name].length > 0).map((name) => ({ name, items: groups[name] }))
}

export function subscribeConversations(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useConversations(): StoredConversation[] {
  const [items, setItems] = useState(readConversations)
  useEffect(() => subscribeConversations(() => setItems(readConversations())), [])
  return items
}

export function analysisRunKey(kind: 'metric' | 'application', id: string, month: string) {
  return `ma2:analysisRun:${kind}:${id}:${month}`
}

export interface AnalysisLink {
  runId: string
  conversationId: string | null
  threadId: number | null
}

export function readAnalysisLink(kind: 'metric' | 'application', id: string, month: string): AnalysisLink | null {
  const raw = memory()?.getItem(analysisRunKey(kind, id, month))
  if (!raw) return null
  if (raw.startsWith('{')) {
    try {
      const parsed = JSON.parse(raw) as Partial<AnalysisLink>
      if (typeof parsed.runId !== 'string' || !parsed.runId) return null
      return {
        runId: parsed.runId,
        conversationId: typeof parsed.conversationId === 'string' ? parsed.conversationId : null,
        threadId: typeof parsed.threadId === 'number' ? parsed.threadId : null,
      }
    } catch {
      return null
    }
  }
  return { runId: raw, conversationId: null, threadId: null }
}

export function readAnalysisRun(kind: 'metric' | 'application', id: string, month: string): string | null {
  return readAnalysisLink(kind, id, month)?.runId ?? null
}

export function writeAnalysisLink(
  kind: 'metric' | 'application',
  id: string,
  month: string,
  link: AnalysisLink,
) {
  memory()?.setItem(analysisRunKey(kind, id, month), JSON.stringify(link))
}

export function writeAnalysisRun(kind: 'metric' | 'application', id: string, month: string, runId: string) {
  const current = readAnalysisLink(kind, id, month)
  writeAnalysisLink(kind, id, month, {
    runId,
    conversationId: current?.conversationId ?? null,
    threadId: current?.threadId ?? null,
  })
}
