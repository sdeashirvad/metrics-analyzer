import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { clearConversations, deleteConversation, groupByRecency, useConversations, type StoredConversation } from '../../agent/conversationStore'

const AGENT_LABEL = { analysis: 'Analysis', data: 'Data' } as const

export function matchesSearch(item: StoredConversation, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  const haystack = [item.title, AGENT_LABEL[item.agentKey], ...(item.contextSummary?.chips ?? [])].join(' ').toLowerCase()
  return haystack.includes(needle)
}

function updated(iso: string, now = new Date()): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const sameDay = date.toDateString() === now.toDateString()
  return sameDay
    ? date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

/**
 * Conversation history for this browser. Search, date groups, agent badge, last update,
 * per-conversation delete and clear-all, each with a confirmation. Nothing is removed on its own.
 */
export function HistoryRail({ activeId, onNavigate }: { activeId?: string; onNavigate?: () => void }) {
  const items = useConversations()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [confirming, setConfirming] = useState<string | 'all' | null>(null)
  const shown = useMemo(() => items.filter((item) => matchesSearch(item, query)), [items, query])
  const groups = useMemo(() => groupByRecency(shown), [shown])

  async function remove(id: string) {
    setConfirming(null)
    await deleteConversation(id)
    if (id === activeId) navigate('/agent')
  }

  async function clearAll() {
    setConfirming(null)
    await clearConversations()
    if (activeId) navigate('/agent')
  }

  return (
    <nav className="history-rail" aria-label="Conversation history">
      <div className="history-head">
        <h2>History</h2>
        <Link className="btn btn-sm btn-primary" to="/agent" onClick={onNavigate}>
          New conversation
        </Link>
      </div>
      <label className="field history-search">
        <span className="sr-only">Search conversations</span>
        <input type="search" value={query} placeholder="Search conversations" onChange={(event) => setQuery(event.target.value)} />
      </label>
      {items.length === 0 && (
        <p className="fine history-empty">No conversations yet. Ask a question and it will appear here.</p>
      )}
      {items.length > 0 && shown.length === 0 && <p className="fine history-empty">No conversation matches “{query}”.</p>}
      <div className="history-groups">
        {groups.map((group) => (
          <section key={group.name} aria-label={group.name}>
            <h3 className="history-group">{group.name}</h3>
            <ul className="history-list">
              {group.items.map((item) => {
                const active = item.conversationId === activeId
                return (
                  <li key={item.conversationId} className={active ? 'is-active' : undefined}>
                    {confirming === item.conversationId ? (
                      <div className="history-confirm" role="group" aria-label={`Delete ${item.title}`}>
                        <p className="fine">Delete this conversation from this browser?</p>
                        <div className="row">
                          <button type="button" className="btn btn-sm btn-danger" onClick={() => void remove(item.conversationId)}>
                            Delete
                          </button>
                          <button type="button" className="btn btn-sm" onClick={() => setConfirming(null)}>
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <Link
                          className="history-item"
                          to={`/agent/${item.agentKey}/${item.conversationId}`}
                          aria-current={active ? 'page' : undefined}
                          onClick={onNavigate}
                        >
                          <span className="history-title">{item.title}</span>
                          <span className="history-meta">
                            <span className={`history-badge ${item.agentKey}`}>{AGENT_LABEL[item.agentKey]}</span>
                            <span>{updated(item.lastActivityAt)}</span>
                            {item.unavailable && <span className="history-flag">Unavailable on server</span>}
                            {!item.unavailable && item.hasTranscript && <span className="history-flag">Saved here</span>}
                          </span>
                        </Link>
                        <button
                          type="button"
                          className="history-delete"
                          aria-label={`Delete conversation: ${item.title}`}
                          onClick={() => setConfirming(item.conversationId)}
                        >
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                            <path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" />
                          </svg>
                        </button>
                      </>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>
        ))}
      </div>
      <div className="history-foot">
        <p className="fine">Stored in this browser only. Nothing is deleted unless you delete it.</p>
        {items.length > 0 &&
          (confirming === 'all' ? (
            <div className="history-confirm" role="group" aria-label="Clear all conversations">
              <p className="fine">Delete all {items.length} conversations from this browser?</p>
              <div className="row">
                <button type="button" className="btn btn-sm btn-danger" onClick={() => void clearAll()}>
                  Delete all
                </button>
                <button type="button" className="btn btn-sm" onClick={() => setConfirming(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button type="button" className="btn btn-sm btn-quiet" onClick={() => setConfirming('all')}>
              Clear all history
            </button>
          ))}
      </div>
    </nav>
  )
}
