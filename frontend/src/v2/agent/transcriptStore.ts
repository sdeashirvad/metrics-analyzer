import type { AgentKey, ConversationContextSummary, Message } from '../api/types'

/**
 * Browser-local conversation transcripts.
 *
 * IndexedDB holds the messages. localStorage holds only the small history index (conversationStore.ts).
 * Nothing here is sent anywhere, nothing is deleted without a user action, and no secrets are stored:
 * run tokens are stripped from messages.
 */

export interface Transcript {
  conversationId: string
  agentKey: AgentKey
  savedAt: string
  messages: Message[]
  context: ConversationContextSummary | null
}

export interface TranscriptBackend {
  get(id: string): Promise<Transcript | null>
  put(value: Transcript): Promise<void>
  delete(id: string): Promise<void>
  clear(): Promise<void>
}

export type SaveResult = { ok: true } | { ok: false; reason: 'quota' | 'unavailable' | 'error' }

const DB_NAME = 'ma2-agent'
const STORE = 'transcripts'
const VERSION = 1

let override: TranscriptBackend | null = null
let cached: TranscriptBackend | null | undefined

export function bindTranscriptBackend(backend: TranscriptBackend | null) {
  override = backend
  cached = undefined
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'conversationId' })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('IndexedDB could not be opened'))
    request.onblocked = () => reject(new Error('IndexedDB is blocked'))
  })
}

function run<T>(db: IDBDatabase, mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE, mode)
    const request = action(transaction.objectStore(STORE))
    let value: T
    request.onsuccess = () => {
      value = request.result
    }
    transaction.oncomplete = () => resolve(value)
    transaction.onabort = () => reject(transaction.error ?? request.error ?? new Error('IndexedDB transaction aborted'))
    transaction.onerror = () => reject(transaction.error ?? request.error ?? new Error('IndexedDB transaction failed'))
  })
}

function indexedBackend(): TranscriptBackend | null {
  if (typeof indexedDB === 'undefined') return null
  let opened: Promise<IDBDatabase> | null = null
  const db = () => (opened ??= openDatabase())
  return {
    get: async (id) => ((await run(await db(), 'readonly', (store) => store.get(id))) as Transcript | undefined) ?? null,
    put: async (value) => {
      await run(await db(), 'readwrite', (store) => store.put(value))
    },
    delete: async (id) => {
      await run(await db(), 'readwrite', (store) => store.delete(id))
    },
    clear: async () => {
      await run(await db(), 'readwrite', (store) => store.clear())
    },
  }
}

function backend(): TranscriptBackend | null {
  if (override) return override
  if (cached === undefined) cached = indexedBackend()
  return cached
}

/** In-memory backend. Used by tests and as a stand-in when IndexedDB is not available. */
export function memoryBackend(options: { failWith?: Error } = {}): TranscriptBackend & { size: () => number } {
  const data = new Map<string, Transcript>()
  return {
    get: async (id) => data.get(id) ?? null,
    put: async (value) => {
      if (options.failWith) throw options.failWith
      data.set(value.conversationId, structuredClone(value))
    },
    delete: async (id) => {
      data.delete(id)
    },
    clear: async () => {
      data.clear()
    },
    size: () => data.size,
  }
}

export function isQuotaError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const named = error as { name?: string; code?: number }
  return named.name === 'QuotaExceededError' || named.code === 22 || named.name === 'NS_ERROR_DOM_QUOTA_REACHED'
}

/** Add new messages, keep the old ones, drop repeats by message id, and keep the original order. */
export function mergeMessages(existing: Message[], incoming: Message[]): Message[] {
  const seen = new Map<string, Message>()
  for (const message of existing) seen.set(message.messageId, message)
  for (const message of incoming) seen.set(message.messageId, message)
  return [...seen.values()].sort((a, b) => (a.createdAt === b.createdAt ? 0 : a.createdAt < b.createdAt ? -1 : 1))
}

function scrub(message: Message): Message {
  return { ...message, runId: null }
}

export async function loadTranscript(conversationId: string): Promise<Transcript | null> {
  const store = backend()
  if (!store) return null
  try {
    return await store.get(conversationId)
  } catch {
    return null
  }
}

export async function saveTranscript(input: {
  conversationId: string
  agentKey: AgentKey
  messages: Message[]
  context?: ConversationContextSummary | null
}): Promise<SaveResult> {
  const store = backend()
  if (!store) return { ok: false, reason: 'unavailable' }
  try {
    const previous = await store.get(input.conversationId)
    const messages = mergeMessages(previous?.messages ?? [], input.messages.map(scrub))
    await store.put({
      conversationId: input.conversationId,
      agentKey: input.agentKey,
      savedAt: new Date().toISOString(),
      messages,
      context: input.context ?? previous?.context ?? null,
    })
    return { ok: true }
  } catch (error) {
    return { ok: false, reason: isQuotaError(error) ? 'quota' : 'error' }
  }
}

export async function deleteTranscript(conversationId: string): Promise<void> {
  try {
    await backend()?.delete(conversationId)
  } catch {
    // The index entry is removed by the caller either way.
  }
}

export async function clearTranscripts(): Promise<void> {
  try {
    await backend()?.clear()
  } catch {
    // Nothing else to do. The caller reports the index as cleared.
  }
}
