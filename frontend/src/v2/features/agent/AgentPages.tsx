import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { errorMessage } from '../../agent/errors'
import {
  hydrateTranscripts,
  markConversationUnavailable,
  patchConversation,
  saveConversationMessages,
  upsertConversation,
  useConversations,
} from '../../agent/conversationStore'
import { loadTranscript, type Transcript } from '../../agent/transcriptStore'
import { createConversation, getConversation, getConversationContext, listAgents, previewContext, sendMessage } from '../../api/agents'
import { ApiError } from '../../api/http'
import type { AgentKey, ConversationContextSummary, ContextPreview, EnvelopeMeta, Message, Run } from '../../api/types'
import { buildContextRequest, saveReviewedContext } from '../../agent/contextClient'
import { Elapsed, QueryPanel, useFocusContain } from '../../components/present'
import { describeFilters, useLegalEntityNames, type LegalEntityNames } from '../../components/scopeLabels'
import { formatMonth } from '../../format'
import { useAgentRun } from '../../hooks/useAgentRun'
import { useApiQuery } from '../../hooks/useApiQuery'
import { useScopeFilters } from '../../hooks/useScopeFilters'
import { contextScope } from '../../scopePath'
import { Composer } from './Composer'
import { HistoryRail } from './HistoryRail'
import { MessageBody } from './MessageViews'

function isAgentKey(value: string | undefined): value is AgentKey {
  return value === 'analysis' || value === 'data'
}

const AGENT_NAME: Record<AgentKey, string> = { analysis: 'Analysis & Investigation', data: 'Data Explorer' }

const STARTERS: Record<AgentKey, string[]> = {
  analysis: ['What changed this month?', 'Which applications drive non-compliance?', 'Explain the movement in this scope.'],
  data: ['How many applications are non-compliant?', 'Show non-compliant counts by organisation.', 'List applications with a failed test.'],
}

const NARROW = '(max-width: 1100px)'

function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(NARROW).matches : false))
  useEffect(() => {
    if (!window.matchMedia) return
    const media = window.matchMedia(NARROW)
    const update = () => setNarrow(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return narrow
}

function HistorySheet({ activeId, onClose }: { activeId?: string; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusContain(ref, onClose)
  return (
    <>
      <button type="button" className="sheet-backdrop" aria-label="Close history" tabIndex={-1} onClick={onClose} />
      <div ref={ref} className="history-sheet dialog" role="dialog" aria-modal="true" aria-label="Conversation history">
        <button type="button" className="btn btn-sm sheet-close" data-initial-focus onClick={onClose}>
          Close
        </button>
        <HistoryRail activeId={activeId} onNavigate={onClose} />
      </div>
    </>
  )
}

/**
 * The shared frame of every Agent route: history on the left (a collapsible column on wide screens,
 * a sheet on narrow ones), the conversation in the middle, the context on the right.
 */
function AgentLayout({ activeId, context, contextOpen, onContextToggle, children }: { activeId?: string; context: ReactNode; contextOpen: boolean; onContextToggle: () => void; children: ReactNode }) {
  const narrow = useNarrow()
  const [collapsed, setCollapsed] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const toggleRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!narrow) setSheetOpen(false)
  }, [narrow])

  useEffect(() => {
    let live = true
    void hydrateTranscripts(async (id) => {
      try {
        const [detail, context] = await Promise.all([getConversation(id), getConversationContext(id).then((result) => result.data, () => null)])
        return live ? { messages: detail.data.messages, context } : null
      } catch (error) {
        if (error instanceof ApiError && error.code === 'CONVERSATION_NOT_FOUND') {
          markConversationUnavailable(id)
          return null
        }
        throw error
      }
    })
    return () => {
      live = false
    }
  }, [])

  function closeSheet() {
    setSheetOpen(false)
    window.setTimeout(() => toggleRef.current?.focus(), 0)
  }

  const historyShown = narrow ? sheetOpen : !collapsed
  return (
    <div className={`page agent-workspace${!narrow && collapsed ? ' hist-collapsed' : ''}`}>
      {!narrow && !collapsed && (
        <aside className="history-pane" aria-label="History">
          <HistoryRail activeId={activeId} />
        </aside>
      )}
      {narrow && sheetOpen && <HistorySheet activeId={activeId} onClose={closeSheet} />}
      <div className="agent-stage">
        <div className="agent-toolbar">
          <button
            ref={toggleRef}
            type="button"
            className="btn btn-sm"
            aria-expanded={historyShown}
            onClick={() => (narrow ? setSheetOpen(true) : setCollapsed((value) => !value))}
          >
            {narrow ? 'History' : collapsed ? 'Show history' : 'Hide history'}
          </button>
          <button type="button" className="btn btn-sm context-toggle" aria-expanded={contextOpen} onClick={onContextToggle}>
            {contextOpen ? 'Hide context' : 'Context'}
          </button>
        </div>
        {children}
      </div>
      {context}
    </div>
  )
}

function ContextCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card context-card">
      <h2>{title}</h2>
      {children}
    </section>
  )
}

function SourceCard({ meta, saved }: { meta?: EnvelopeMeta; saved?: boolean }) {
  return (
    <ContextCard title="Source and freshness">
      {saved ? (
        <p>Saved copy in this browser. It may be older than the live conversation.</p>
      ) : meta ? (
        <>
          <p>
            {meta.source === 'packaged' ? 'Prepared copy, not live data' : 'Live data'}
            {meta.asOf ? ` · as of ${formatMonth(meta.asOf)}` : ''}
          </p>
          <p className="fine">
            Dataset {meta.dataset.version} · definitions {meta.definitionsVersion}
          </p>
        </>
      ) : (
        <p>Shown once the scope is ready.</p>
      )}
    </ContextCard>
  )
}

function scopeSummary(preview: ContextPreview | undefined, names: LegalEntityNames) {
  const scope = preview?.scope
  const filterText = scope
    ? describeFilters(scope.filters, names).join(' · ') || 'No additional filters'
    : 'No additional filters'
  return { scope, filterText }
}

function AgentWorkspace({ preset }: { preset?: AgentKey }) {
  const { filters, params } = useScopeFilters()
  const navigate = useNavigate()
  // Only the Register Preview seeds a contextual launch, and it must say so with ctx=preview.
  const seeded = params.get('ctx') === 'preview' ? params.get('focusMetric') || undefined : undefined
  const metricId = seeded
  const [selected, setSelected] = useState<AgentKey | null>(preset ?? null)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [contextOpen, setContextOpen] = useState(false)
  const requestId = useRef<string | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const agents = useApiQuery('agents', 'list', listAgents)
  const request = buildContextRequest(metricId ? 'register_preview' : 'general', contextScope(filters, { metricId, eonId: undefined }))
  const preview = useApiQuery('agent-workspace-context', `${metricId ?? 'portfolio'}|${JSON.stringify(request)}`, () => previewContext(request))
  const names = useLegalEntityNames()
  const { scope, filterText } = scopeSummary(preview.data, names)
  const offline = agents.status === 'error' || preview.status === 'error'

  async function send() {
    const message = draft.trim()
    if (!selected || !preview.data || !message || sending) return
    const clientRequestId = requestId.current ?? crypto.randomUUID()
    requestId.current = clientRequestId
    setSending(true)
    setSendError(null)
    try {
      const result = await createConversation({
        agentKey: selected,
        message,
        context: request,
        contextHash: preview.data.contextHash,
        clientRequestId,
      })
      saveReviewedContext({ request, contextHash: preview.data.contextHash, agentKey: selected })
      const conversation = result.data.conversation
      upsertConversation({
        conversationId: conversation.conversationId,
        threadId: conversation.threadId,
        agentKey: conversation.agentKey,
        title: conversation.title,
        createdAt: conversation.createdAt,
        lastActivityAt: conversation.updatedAt,
        contextSummary: { chips: conversation.chips, entrySurface: conversation.entrySurface },
        lastRunId: result.data.run.runId,
      })
      void saveConversationMessages(conversation, [result.data.userMessage], null)
      navigate(`/agent/${conversation.agentKey}/${conversation.conversationId}`, { state: { runId: result.data.run.runId } })
    } catch (error) {
      // The draft stays in the box, no message is added to the page, and the request id is kept so a retry is the same request.
      setSendError(notSent(error))
      input.current?.focus()
    } finally {
      setSending(false)
    }
  }

  const contextCards = (
    <aside className={`context-rail${contextOpen ? ' is-open' : ''}`} aria-label="Conversation context">
      {metricId && (
        <ContextCard title="Launched from preview">
          {preview.status === 'error' ? (
            <p className="fine">
              Context for {metricId} could not be prepared ({errorMessage(preview.error)}). <Link to="/agent">Use portfolio context</Link>
            </p>
          ) : (
            <p className="fine">
              Metric {metricId} with the month and filters you had open. <Link to="/agent">Use portfolio context instead</Link>
            </p>
          )}
        </ContextCard>
      )}
      <ContextCard title="Scope">
        <p>{scope?.eonId ? `Application ${scope.eonId}` : scope?.metricId ? 'Metric' : 'Portfolio-wide scope'}</p>
      </ContextCard>
      <ContextCard title="Reporting period">
        <p>{scope ? `${formatMonth(scope.month)} · ${scope.monthSource === 'latest_available' ? 'latest available' : 'selected'}` : 'Latest available month'}</p>
      </ContextCard>
      <ContextCard title="Selected entity">
        <p>{scope?.metricId ? `Metric ${scope.metricId}` : scope?.eonId ? `Application ${scope.eonId}` : 'No specific metric or application selected.'}</p>
      </ContextCard>
      <ContextCard title="Filters">
        <p>{filterText}</p>
      </ContextCard>
      <ContextCard title="Definitions and assumptions">
        <p>{preview.data ? 'Provisional definitions for this scope.' : 'Definitions load with the scope.'}</p>
        {preview.data && preview.data.items.length > 0 && (
          <details>
            <summary className="fine">Assumptions</summary>
            <ul className="list">
              {preview.data.items.slice(0, 6).map((item) => (
                <li key={item.key}>{item.label}</li>
              ))}
            </ul>
          </details>
        )}
      </ContextCard>
      <SourceCard meta={preview.meta} />
    </aside>
  )

  const canSend = Boolean(selected && preview.data && draft.trim())
  const hint = !selected ? 'Choose an Agent above to enable sending.' : offline ? 'The live Agent is not reachable right now.' : null

  return (
    <AgentLayout context={contextCards} contextOpen={contextOpen} onContextToggle={() => setContextOpen((value) => !value)}>
      <header>
        <p className="eyebrow">Agent</p>
        <h1>{metricId ? `Ask about ${metricId}` : 'Ask about this portfolio'}</h1>
        <p className="fine">Choose an agent, then ask in plain language. The choice stays fixed once the conversation starts.</p>
      </header>
      {offline && (
        <p className="callout warn" role="status">
          The live Agent is not reachable right now, so new messages cannot be sent. Saved conversations in History can still be read.
        </p>
      )}
      <QueryPanel query={agents}>
        {(data) =>
          selected ? (
            <div className="row" role="radiogroup" aria-label="Choose an agent">
              {data.agents.map((agent) => (
                <button
                  key={agent.agentKey}
                  type="button"
                  role="radio"
                  aria-checked={selected === agent.agentKey}
                  className={selected === agent.agentKey ? 'btn btn-primary btn-sm' : 'btn btn-sm'}
                  onClick={() => setSelected(agent.agentKey)}
                >
                  {agent.displayName}
                </button>
              ))}
            </div>
          ) : (
            <div className="agent-grid" role="radiogroup" aria-label="Choose an agent">
              {data.agents.map((agent) => (
                <button
                  key={agent.agentKey}
                  type="button"
                  role="radio"
                  aria-checked={false}
                  className={`agent-card ${agent.agentKey}`}
                  onClick={() => setSelected(agent.agentKey)}
                >
                  <h2>{agent.displayName}</h2>
                  <p className="fine">{agent.description}</p>
                </button>
              ))}
            </div>
          )
        }
      </QueryPanel>
      <div className="sugg">
        {(selected ? STARTERS[selected] : STARTERS.analysis).map((prompt) => (
          <button key={prompt} type="button" onClick={() => setDraft(prompt)}>
            {prompt}
          </button>
        ))}
      </div>
      <Composer
        value={draft}
        onChange={setDraft}
        onSubmit={() => void send()}
        placeholder={selected === 'data' ? 'Ask for a dataset' : selected === 'analysis' ? 'Ask for an explanation' : 'Ask about this portfolio'}
        canSend={canSend}
        sending={sending}
        error={sendError}
        hint={hint}
        inputRef={input}
      />
    </AgentLayout>
  )
}

export function AgentHome() {
  return <AgentWorkspace />
}

export function NewConversationPage() {
  const { agentKey } = useParams()
  const location = useLocation()
  if (!isAgentKey(agentKey)) {
    return (
      <p>
        Unknown agent. <Link to={{ pathname: '/agent', search: location.search }}>Back to Agent</Link>
      </p>
    )
  }
  return <AgentWorkspace preset={agentKey} />
}

/** A clear message for a send that did not start. The draft and the transcript are untouched. */
function notSent(error: unknown): string {
  const reason = errorMessage(error).replace(/\s*Your message is still here\.?/, '')
  return `${reason} Your message was not sent. Your draft is still here.`
}

function isReadFailure(error: Error | null): boolean {
  return Boolean(error) && !(error instanceof ApiError && error.code === 'CONVERSATION_NOT_FOUND')
}

export function ConversationPage() {
  const { agentKey, conversationId = '' } = useParams()
  const location = useLocation()
  const seeded = (location.state as { runId?: string } | null)?.runId ?? null
  const [tick, setTick] = useState(0)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [contextOpen, setContextOpen] = useState(false)
  const [saved, setSaved] = useState<Transcript | null | undefined>(undefined)
  const [storageNote, setStorageNote] = useState<string | null>(null)
  const requestId = useRef<string | null>(null)
  const draftKey = useRef(draft)
  const input = useRef<HTMLTextAreaElement>(null)
  if (draftKey.current !== draft) {
    draftKey.current = draft
    requestId.current = null
  }
  const stored = useConversations().find((item) => item.conversationId === conversationId)
  const detail = useApiQuery('conversation', `${conversationId}|${tick}`, () => getConversation(conversationId))
  const context = useApiQuery('conversation-context', conversationId, () => getConversationContext(conversationId))
  const live = detail.status === 'success'
  const runId = live ? (detail.data?.activeRun?.runId ?? null) : seeded
  const polled = useAgentRun(live || seeded ? runId : null)
  const run = polled.run ?? detail.data?.activeRun ?? null
  const refreshed = useRef<string | null>(null)

  useEffect(() => {
    let current = true
    setSaved(undefined)
    void loadTranscript(conversationId).then((value) => {
      if (current) setSaved(value)
    })
    return () => {
      current = false
    }
  }, [conversationId])

  useEffect(() => {
    if (detail.error instanceof ApiError && detail.error.code === 'CONVERSATION_NOT_FOUND') markConversationUnavailable(conversationId)
  }, [detail.error, conversationId])

  useEffect(() => {
    if (run?.status === 'COMPLETED' && refreshed.current !== run.runId) {
      refreshed.current = run.runId
      setTick((value) => value + 1)
    }
  }, [run?.status, run?.runId])

  const messages: Message[] = live ? (detail.data?.messages ?? []) : (saved?.messages ?? [])
  const extra = live && run?.message && !messages.some((item) => item.messageId === run.message?.messageId) ? [run.message] : []
  const thread = [...messages, ...extra]
  const savedKey = live ? `${thread.length}:${thread[thread.length - 1]?.messageId ?? ''}` : null
  const agent: AgentKey | null = isAgentKey(agentKey) ? agentKey : null

  useEffect(() => {
    if (!live || !agent || thread.length === 0) return
    let current = true
    void saveConversationMessages({ conversationId, agentKey: agent }, thread, context.data ?? null).then((result) => {
      if (!current) return
      if (result.ok) setStorageNote(null)
      else
        setStorageNote(
          result.reason === 'quota'
            ? 'This browser has no room left to save this conversation. Nothing was deleted. Delete conversations you no longer need from History.'
            : 'This conversation could not be saved in this browser.',
        )
    })
    return () => {
      current = false
    }
    // thread is derived from the fields in savedKey and the context.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedKey, conversationId, agent, context.data])

  if (!agent) {
    return (
      <p>
        Unknown agent. <Link to="/agent">Back to Agent</Link>
      </p>
    )
  }

  const running = live && run?.status === 'RUNNING'
  const readOnlyCopy = !live && Boolean(saved)
  const unreadable = detail.status === 'error' && !saved && saved !== undefined
  const contextLines: ConversationContextSummary | null = context.data ?? saved?.context ?? null
  const title = detail.data?.conversation.title ?? stored?.title ?? 'Conversation'

  async function send() {
    const text = draft.trim()
    if (!text || sending || running) return
    const clientRequestId = requestId.current ?? crypto.randomUUID()
    requestId.current = clientRequestId
    setSending(true)
    setSendError(null)
    try {
      const result = await sendMessage(conversationId, { message: text, clientRequestId })
      requestId.current = null
      setDraft('')
      patchConversation(conversationId, { lastActivityAt: new Date().toISOString(), lastRunId: result.data.run.runId })
      setTick((value) => value + 1)
    } catch (error) {
      // The draft stays, the transcript is unchanged, and no progress is shown for a message that never started.
      setSendError(notSent(error))
      input.current?.focus()
    } finally {
      setSending(false)
    }
  }

  const rail = (
    <aside className={`context-rail${contextOpen ? ' is-open' : ''}`} aria-label="Conversation context">
      <ContextCard title="Context">
        {contextLines ? (
          <div className="stack">
            <div className="row">
              {contextLines.chips.map((chip) => (
                <span className="ctxchip" key={chip}>
                  {chip}
                </span>
              ))}
            </div>
            <details>
              <summary className="fine">View context sent</summary>
              <ul className="list">
                {contextLines.lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>
          </div>
        ) : context.status === 'error' ? (
          <p className="fine">The context could not be read right now.</p>
        ) : (
          <p className="fine">Loading…</p>
        )}
      </ContextCard>
      {stored?.contextSummary && !contextLines && (
        <ContextCard title="Scope">
          <p>{stored.contextSummary.chips.join(' · ')}</p>
        </ContextCard>
      )}
      <ContextCard title="Storage">
        <p>{saved ? `Saved in this browser · ${saved.messages.length} messages` : 'Saved in this browser once it loads.'}</p>
        {storageNote && <p className="callout warn">{storageNote}</p>}
      </ContextCard>
      <SourceCard meta={live ? detail.meta : undefined} saved={readOnlyCopy} />
    </aside>
  )

  return (
    <AgentLayout activeId={conversationId} context={rail} contextOpen={contextOpen} onContextToggle={() => setContextOpen((value) => !value)}>
      <header>
        <p className="eyebrow">
          <Link to="/agent">Agent</Link> · <span className={`history-badge ${agent}`}>{AGENT_NAME[agent]}</span>
        </p>
        <h1>{title}</h1>
        <p className="fine">The agent is fixed for this conversation. Start a new one from History to use the other.</p>
      </header>
      {readOnlyCopy && (
        <p className="callout warn" role="status">
          Showing the copy saved in this browser. The live conversation could not be read ({errorMessage(detail.error)}). You can read it here. New messages need the live Agent.
        </p>
      )}
      {unreadable && (
        <div className="callout warn" role="status">
          <p>
            {isReadFailure(detail.error)
              ? 'This conversation is not saved in this browser and the live service could not be reached.'
              : 'This conversation is no longer available.'}
          </p>
          <button type="button" className="btn btn-sm" onClick={detail.retry}>
            Retry
          </button>
        </div>
      )}
      <div className="stack">
        {!live && detail.status === 'loading' && !saved && <p className="fine">Loading…</p>}
        <div className="chat" aria-live="off">
          {thread.map((message) => (
            <article key={message.messageId} className={`msg ${message.role === 'user' ? 'user' : ''}`}>
              <span className={`avatar ${message.role === 'user' ? 'av-u' : message.agentKey === 'data' ? 'av-d' : 'av-a'}`} aria-hidden="true">
                {message.role === 'user' ? 'Y' : message.agentKey === 'data' ? 'D' : 'A'}
              </span>
              <div className="bubble">
                <MessageBody message={message} onSuggest={message.role === 'assistant' && !readOnlyCopy ? setDraft : undefined} />
              </div>
            </article>
          ))}
        </div>
        {live && <RunNote run={run} agentKey={agent} connectionLost={polled.connectionLost} stopped={polled.stopped} onStop={polled.stopWaiting} onRetry={() => void polled.retry()} />}
      </div>
      <Composer
        value={draft}
        onChange={setDraft}
        onSubmit={() => void send()}
        placeholder="Ask a follow-up"
        disabled={running || sending}
        canSend={Boolean(draft.trim()) && !running}
        sending={sending}
        busyLabel={running ? (agent === 'data' ? 'Data Explorer is working' : 'Analysis agent is working') : null}
        error={sendError}
        hint={readOnlyCopy ? 'Offline. You can read this conversation. Sending needs the live Agent.' : null}
        inputRef={input}
      />
    </AgentLayout>
  )
}

function RunNote({
  run,
  agentKey,
  connectionLost,
  stopped,
  onStop,
  onRetry,
}: {
  run: Run | null
  agentKey: AgentKey
  connectionLost: boolean
  stopped: boolean
  onStop: () => void
  onRetry: () => void
}) {
  if (connectionLost) return <p className="callout warn">Connection lost. The run continues on the server. Reload to check.</p>
  if (!run) return null
  if (run.status === 'RUNNING') {
    return (
      <div className="stack">
        <p className="run-note">
          {agentKey === 'data' ? 'Working on your request…' : 'Analysing your request…'}{' '}
          <Elapsed submittedAt={run.submittedAt} running serverMs={run.elapsedMs} />
          {run.overdue ? ' · Overdue' : ''}
        </p>
        {!stopped && (
          <button type="button" className="btn btn-sm" onClick={onStop}>
            Stop waiting
          </button>
        )}
        {stopped && <p className="fine">Waiting stopped here. The run continues on the server.</p>}
      </div>
    )
  }
  if (run.status === 'FAILED') {
    return (
      <div className="stack">
        <p className="callout warn">{run.error?.message ?? 'The agent run failed.'}</p>
        {run.error?.retryable && (
          <button type="button" className="btn btn-sm" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    )
  }
  return null
}
