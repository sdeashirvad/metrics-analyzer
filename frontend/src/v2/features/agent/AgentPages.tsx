import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
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
import type { AgentKey, AgentMetadata, ConversationContextSummary, ContextPreview, EnvelopeMeta, Message, Run } from '../../api/types'
import { buildContextRequest, saveReviewedContext } from '../../agent/contextClient'
import { QueryPanel, useElapsedMs, useFocusContain } from '../../components/present'
import { Skeleton } from '../../components/Skeleton'
import { describeFilters, useLegalEntityNames, type LegalEntityNames } from '../../components/scopeLabels'
import { formatDuration, formatMonth } from '../../format'
import { useAgentRun } from '../../hooks/useAgentRun'
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery'
import { useBackTarget, type Origin } from '../../hooks/useOrigin'
import { useScopeFilters } from '../../hooks/useScopeFilters'
import { contextScope, scopedTo } from '../../scopePath'
import { Composer } from './Composer'
import { HistoryRail } from './HistoryRail'
import { MessageBody } from './MessageViews'

function isAgentKey(value: string | undefined): value is AgentKey {
  return value === 'analysis' || value === 'data'
}

const AGENT_NAME: Record<AgentKey, string> = { analysis: 'Analysis & Investigation', data: 'Data Explorer' }
const AGENT_INITIAL: Record<AgentKey, string> = { analysis: 'A', data: 'D' }

const STARTERS: Record<AgentKey, string[]> = {
  analysis: ['What changed this month?', 'Which applications drive non-compliance?', 'Explain the movement in this scope.'],
  data: ['How many applications are non-compliant?', 'Show non-compliant counts by organisation.', 'List applications with a failed test.'],
}

/** Typical end-to-end time of one Agent run, shown while waiting. It is an expectation, not a measure of progress. */
const EXPECTED_MS = 35_000

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

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
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

/** The way back to the page the Agent was opened from, or to the metric the conversation is about. */
function BackLink({ metricId }: { metricId?: string | null }) {
  const { filters } = useScopeFilters()
  const fallback = metricId ? { to: scopedTo(`/register/${encodeURIComponent(metricId)}`, filters), label: `Back to ${metricId}` } : null
  const back = useBackTarget(fallback ?? { to: '/agent', label: '' })
  if (!back.fromOrigin && !fallback) return null
  return (
    <Link className="agent-back" to={back.to} state={back.state} onClick={back.go}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M15 18l-6-6 6-6" />
      </svg>
      {back.label}
    </Link>
  )
}

/**
 * The shared frame of every Agent route: history on the left (a collapsible column on wide screens,
 * a sheet on narrow ones), the conversation in the middle, the context on the right when opened.
 */
function AgentLayout({
  activeId,
  context,
  contextOpen,
  onContextToggle,
  thread = false,
  children,
}: {
  activeId?: string
  context: ReactNode
  contextOpen: boolean
  onContextToggle: () => void
  thread?: boolean
  children: ReactNode
}) {
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
  const classes = ['page', 'agent-workspace', !narrow && collapsed ? 'hist-collapsed' : '', contextOpen ? 'ctx-open' : '', thread ? 'is-thread' : '']
  return (
    <div className={classes.filter(Boolean).join(' ')}>
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
          <button type="button" className={`btn btn-sm context-toggle${contextOpen ? ' is-open' : ''}`} aria-expanded={contextOpen} aria-controls="agent-context" onClick={onContextToggle}>
            {contextOpen ? 'Hide context' : 'Context'}
          </button>
        </div>
        {children}
      </div>
      {contextOpen && context}
    </div>
  )
}

function ContextRail({ children }: { children: ReactNode }) {
  return (
    <aside id="agent-context" className="context-rail" aria-label="Conversation context">
      {children}
    </aside>
  )
}

function sourceLine(meta?: EnvelopeMeta, saved?: boolean): { text: string; detail?: string } | null {
  if (saved) return { text: 'Saved copy in this browser. It may be older than the live conversation.' }
  if (!meta) return null
  return {
    text: `${meta.source === 'packaged' ? 'Prepared copy, not live data' : 'Live data'}${meta.asOf ? ` · as of ${formatMonth(meta.asOf)}` : ''}`,
    detail: `Dataset ${meta.dataset.version} · definitions ${meta.definitionsVersion}`,
  }
}

function SourceRow({ meta, saved }: { meta?: EnvelopeMeta; saved?: boolean }) {
  const line = sourceLine(meta, saved)
  return (
    <div className="receives-source">
      <h3 className="sec-label">Source and freshness</h3>
      <p>{line?.text ?? 'Shown once the scope is ready.'}</p>
      {line?.detail && <p className="fine">{line.detail}</p>}
    </div>
  )
}

function scopeSummary(preview: ContextPreview | undefined, names: LegalEntityNames) {
  const scope = preview?.scope
  const filterText = scope ? describeFilters(scope.filters, names).join(' · ') || 'No additional filters' : 'No additional filters'
  return { scope, filterText }
}

/** One card for everything the Agent will be given with the first message. */
function ReceivesCard({ preview, metricId, names }: { preview: QueryState<ContextPreview>; metricId?: string; names: LegalEntityNames }) {
  const { scope, filterText } = scopeSummary(preview.data, names)
  const items = preview.data?.items.filter((item) => item.included) ?? []
  return (
    <section className="card context-card receives">
      <h2>What the Agent receives</h2>
      {metricId && preview.status === 'error' && (
        <p className="callout warn">
          Context for {metricId} could not be prepared ({errorMessage(preview.error)}). <Link to="/agent">Use portfolio context</Link>
        </p>
      )}
      {metricId && preview.status !== 'error' && (
        <p className="fine">
          Opened from the {metricId} preview, with the month and filters you had open. <Link to="/agent">Use portfolio context instead</Link>
        </p>
      )}
      <dl className="kv receives-kv">
        <dt>Scope</dt>
        <dd>{scope?.eonId ? `Application ${scope.eonId}` : scope?.metricId ? `Metric ${scope.metricId}` : scope ? 'Portfolio-wide' : metricId ? `Metric ${metricId}` : 'Portfolio-wide'}</dd>
        <dt>Period</dt>
        <dd>{scope ? `${formatMonth(scope.month)} · ${scope.monthSource === 'latest_available' ? 'latest available' : 'selected'}` : <span className="fine">Preparing…</span>}</dd>
        <dt>Filters</dt>
        <dd>{scope ? filterText : <span className="fine">Preparing…</span>}</dd>
      </dl>
      {preview.data ? (
        items.length > 0 && (
          <details className="receives-items">
            <summary>
              Included context <span className="fine">· {items.length} sections</span>
            </summary>
            <ul className="list">
              {items.map((item) => (
                <li key={item.key}>
                  <span className="grow">
                    <span className="t-title">{item.label}</span>
                    {item.summary && <span className="fine receives-summary">{item.summary}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )
      ) : preview.status === 'loading' ? (
        <Skeleton shape="lines" rows={2} label="Preparing the context" />
      ) : null}
      <SourceRow meta={preview.meta} />
    </section>
  )
}

function AgentSelector({ agents, selected, onSelect }: { agents: AgentMetadata[]; selected: AgentKey | null; onSelect: (key: AgentKey, moveFocus: boolean) => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0
    if (!step || agents.length === 0) return
    event.preventDefault()
    const next = (index + step + agents.length) % agents.length
    refs.current[next]?.focus()
    onSelect(agents[next].agentKey, false)
  }
  const focusable = Math.max(0, agents.findIndex((agent) => agent.agentKey === selected))
  return (
    <div className="agent-grid" role="radiogroup" aria-label="Choose an agent">
      {agents.map((agent, index) => {
        const checked = selected === agent.agentKey
        return (
          <button
            key={agent.agentKey}
            ref={(element) => {
              refs.current[index] = element
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={index === focusable ? 0 : -1}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={`agent-card ${agent.agentKey}${checked ? ' is-selected' : ''}`}
            onClick={() => onSelect(agent.agentKey, true)}
          >
            <span className="agent-card-head">
              <span className={`avatar ${agent.agentKey === 'data' ? 'av-d' : 'av-a'}`} aria-hidden="true">
                {AGENT_INITIAL[agent.agentKey]}
              </span>
              <h2>{agent.displayName}</h2>
              <span className="agent-check" aria-hidden="true" />
            </span>
            <p className="fine">{agent.description}</p>
          </button>
        )
      })}
    </div>
  )
}

function AgentWorkspace({ preset }: { preset?: AgentKey }) {
  const { filters, params } = useScopeFilters()
  const navigate = useNavigate()
  const location = useLocation()
  // Only the Register Preview seeds a contextual launch, and it must say so with ctx=preview.
  const seeded = params.get('ctx') === 'preview' ? params.get('focusMetric') || undefined : undefined
  const metricId = seeded
  const [selected, setSelected] = useState<AgentKey | null>(preset ?? null)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [contextOpen, setContextOpen] = useState(Boolean(metricId))
  const requestId = useRef<string | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const agents = useApiQuery('agents', 'list', listAgents)
  const request = buildContextRequest(metricId ? 'register_preview' : 'general', contextScope(filters, { metricId, eonId: undefined }))
  const preview = useApiQuery('agent-workspace-context', `${metricId ?? 'portfolio'}|${JSON.stringify(request)}`, () => previewContext(request))
  const names = useLegalEntityNames()
  const offline = agents.status === 'error' || preview.status === 'error'
  const origin = (location.state as { from?: Origin } | null)?.from

  function choose(key: AgentKey, moveFocus: boolean) {
    setSelected(key)
    if (moveFocus) window.setTimeout(() => input.current?.focus(), 0)
  }

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
      navigate(`/agent/${conversation.agentKey}/${conversation.conversationId}`, { state: { runId: result.data.run.runId, from: origin } })
    } catch (error) {
      // The draft stays in the box, no message is added to the page, and the request id is kept so a retry is the same request.
      setSendError(notSent(error))
      input.current?.focus()
    } finally {
      setSending(false)
    }
  }

  const canSend = Boolean(selected && preview.data && draft.trim())
  const hint = !selected ? 'Choose an Agent above to start.' : offline ? 'The live Agent is not reachable right now.' : null

  return (
    <AgentLayout
      context={
        <ContextRail>
          <ReceivesCard preview={preview} metricId={metricId} names={names} />
        </ContextRail>
      }
      contextOpen={contextOpen}
      onContextToggle={() => setContextOpen((value) => !value)}
    >
      <header className="agent-head">
        <BackLink metricId={metricId} />
        <p className="eyebrow">Agent</p>
        <h1>{metricId ? `Ask about ${metricId}` : 'Ask about this portfolio'}</h1>
        <p className="fine">Choose an agent, then ask in plain language. The choice stays fixed once the conversation starts.</p>
      </header>
      {offline && (
        <p className="callout warn" role="status">
          The live Agent is not reachable right now, so new messages cannot be sent. Saved conversations in History can still be read.
        </p>
      )}
      <QueryPanel query={agents} skeleton={<Skeleton shape="kpis" rows={2} label="Loading the agents" />}>
        {(data) => <AgentSelector agents={data.agents} selected={selected} onSelect={choose} />}
      </QueryPanel>
      <div className={`ask-panel${selected ? ` is-${selected}` : ''}`}>
        {selected && (
          <div className="sugg" aria-label="Suggested questions">
            {STARTERS[selected].map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => {
                  setDraft(prompt)
                  input.current?.focus()
                }}
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={() => void send()}
          placeholder={selected === 'data' ? 'Ask for a dataset' : selected === 'analysis' ? 'Ask for an explanation' : 'Choose an agent first'}
          canSend={canSend}
          sending={sending}
          error={sendError}
          hint={hint}
          inputRef={input}
        />
      </div>
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
  const [sent, setSent] = useState<{ conversationId: string; message: Message; runId: string } | null>(null)
  const [arrived, setArrived] = useState<string | null>(null)
  const requestId = useRef<string | null>(null)
  const draftKey = useRef(draft)
  const input = useRef<HTMLTextAreaElement>(null)
  if (draftKey.current !== draft) {
    draftKey.current = draft
    requestId.current = null
  }
  const stored = useConversations().find((item) => item.conversationId === conversationId)
  const detail = useApiQuery('conversation', `${conversationId}|${tick}`, () => getConversation(conversationId), { keep: conversationId, announce: false })
  const context = useApiQuery('conversation-context', conversationId, () => getConversationContext(conversationId))
  const live = detail.status === 'success'
  const pendingSend = sent?.conversationId === conversationId ? sent : null
  const runId = live ? (detail.data?.activeRun?.runId ?? pendingSend?.runId ?? null) : seeded
  const polled = useAgentRun(live || seeded ? runId : null)
  const run = polled.run ?? detail.data?.activeRun ?? null
  const refreshed = useRef<string | null>(null)

  useEffect(() => {
    let current = true
    setSaved(undefined)
    setSent(null)
    setArrived(null)
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
      if (run.message) setArrived(run.message.messageId)
      setTick((value) => value + 1)
    }
  }, [run?.status, run?.runId, run?.message])

  const messages: Message[] = live ? (detail.data?.messages ?? []) : (saved?.messages ?? [])
  const withSent = pendingSend && !messages.some((item) => item.messageId === pendingSend.message.messageId) ? [...messages, pendingSend.message] : messages
  const extra = live && run?.message && !withSent.some((item) => item.messageId === run.message?.messageId) ? [run.message] : []
  const thread = [...withSent, ...extra]
  const savedKey = live && !detail.stale ? `${thread.length}:${thread[thread.length - 1]?.messageId ?? ''}` : null
  const agent: AgentKey | null = isAgentKey(agentKey) ? agentKey : null
  const lastAssistant = [...thread].reverse().find((item) => item.role === 'assistant')?.messageId

  useEffect(() => {
    if (!savedKey || !agent || thread.length === 0) return
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

  const running = (live || Boolean(seeded)) && run?.status === 'RUNNING'
  const readOnlyCopy = !live && Boolean(saved)
  const unreadable = detail.status === 'error' && !saved && saved !== undefined
  const contextLines: ConversationContextSummary | null = context.data ?? saved?.context ?? null
  const title = detail.data?.conversation.title ?? stored?.title ?? 'Conversation'
  const scopeMetric = detail.data?.conversation.scope.metricId ?? null

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
      setSent({ conversationId, message: result.data.userMessage, runId: result.data.run.runId })
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
    <ContextRail>
      <section className="card context-card receives">
        <h2>What the Agent received</h2>
        {contextLines ? (
          <div className="stack">
            <div className="row">
              {contextLines.chips.map((chip) => (
                <span className="ctxchip" key={chip}>
                  {chip}
                </span>
              ))}
            </div>
            <details className="receives-items">
              <summary>View context sent</summary>
              <ul className="list">
                {contextLines.lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>
          </div>
        ) : context.status === 'error' ? (
          <p className="fine">The context could not be read right now.</p>
        ) : stored?.contextSummary ? (
          <p>{stored.contextSummary.chips.join(' · ')}</p>
        ) : (
          <Skeleton shape="lines" rows={2} label="Loading the context" />
        )}
        <div className="receives-source">
          <h3 className="sec-label">Storage</h3>
          <p>{saved ? `Saved in this browser · ${saved.messages.length} messages` : 'Saved in this browser once it loads.'}</p>
          {storageNote && <p className="callout warn">{storageNote}</p>}
        </div>
        <SourceRow meta={live ? detail.meta : undefined} saved={readOnlyCopy} />
      </section>
    </ContextRail>
  )

  return (
    <AgentLayout activeId={conversationId} context={rail} contextOpen={contextOpen} onContextToggle={() => setContextOpen((value) => !value)} thread>
      <header className="agent-head">
        <BackLink metricId={scopeMetric} />
        <p className="eyebrow agent-identity">
          <Link to="/agent">Agent</Link>
          <span aria-hidden="true">·</span>
          <span className={`agent-chip ${agent}`}>
            <span className={`avatar ${agent === 'data' ? 'av-d' : 'av-a'}`} aria-hidden="true">
              {AGENT_INITIAL[agent]}
            </span>
            {AGENT_NAME[agent]}
          </span>
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
      <div className="chat" aria-live="off">
        {!live && detail.status === 'loading' && !saved && <Skeleton shape="lines" rows={4} label="Loading the conversation" />}
        {thread.map((message) => (
          <article
            key={message.messageId}
            className={`msg ${message.role === 'user' ? 'user' : 'assistant'}${message.messageId === arrived ? ' msg-in' : ''}`}
          >
            <span className={`avatar ${message.role === 'user' ? 'av-u' : message.agentKey === 'data' ? 'av-d' : 'av-a'}`} aria-hidden="true">
              {message.role === 'user' ? 'Y' : message.agentKey === 'data' ? 'D' : 'A'}
            </span>
            <div className="bubble">
              <MessageBody
                message={message}
                onSuggest={message.role === 'assistant' && !readOnlyCopy ? setDraft : undefined}
                showFollowUps={message.messageId === lastAssistant}
              />
            </div>
          </article>
        ))}
        <RunState
          run={run}
          agentKey={agent}
          connectionLost={polled.connectionLost}
          stopped={polled.stopped}
          active={live || Boolean(seeded)}
          onStop={polled.stopWaiting}
          onRetry={() => void polled.retry()}
        />
      </div>
      <div className="composer-dock">
        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={() => void send()}
          placeholder={running ? 'You can type your follow-up while the Agent answers' : 'Ask a follow-up'}
          canSend={Boolean(draft.trim()) && !running}
          sending={sending}
          error={sendError}
          hint={readOnlyCopy ? 'Offline. You can read this conversation. Sending needs the live Agent.' : running ? 'Send is available once the reply arrives.' : null}
          inputRef={input}
        />
      </div>
    </AgentLayout>
  )
}

/** The Agent's reply slot while a run is in flight: expected time, elapsed time, and the server's own status. */
function PendingReply({ run, agentKey, stopped, onStop }: { run: Run; agentKey: AgentKey; stopped: boolean; onStop: () => void }) {
  const ms = useElapsedMs(run.submittedAt, !stopped, run.elapsedMs)
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    ref.current?.scrollIntoView({ block: 'nearest', behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
  }, [])
  const longer = ms >= EXPECTED_MS
  const who = agentKey === 'data' ? 'Data Explorer is working' : 'The Analysis agent is working'
  const phase = stopped ? 'Waiting stopped here' : run.overdue ? 'Taking much longer than usual' : longer ? 'Taking longer than usual' : who
  return (
    <article ref={ref} className={`msg assistant pending ${agentKey}${stopped ? ' is-stopped' : ''}${longer || run.overdue ? ' is-long' : ''}`}>
      <span className={`avatar ${agentKey === 'data' ? 'av-d' : 'av-a'}`} aria-hidden="true">
        {AGENT_INITIAL[agentKey]}
      </span>
      <div className="bubble pending-bubble">
        <div className="pending-line">
          <span className="thinking-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="pending-phase" role="status" aria-live="polite">
            {phase}
          </span>
        </div>
        <p className="fine pending-time">
          <span className="sr-only">Usually about 35 seconds.</span>
          <span aria-hidden="true">
            {longer ? 'Expected about 35 s' : 'Usually about 35 s'} · <span className="num">{formatDuration(ms)}</span> elapsed
          </span>
        </p>
        {stopped ? (
          <p className="fine">The run continues on the server. Reload this conversation to check for the reply.</p>
        ) : (
          <>
            {run.overdue && <p className="fine">The run continues on the server. The reply appears here when it finishes.</p>}
            <button type="button" className="btn btn-sm btn-quiet pending-stop" onClick={onStop}>
              Stop waiting
            </button>
          </>
        )}
      </div>
    </article>
  )
}

function RunState({
  run,
  agentKey,
  connectionLost,
  stopped,
  active,
  onStop,
  onRetry,
}: {
  run: Run | null
  agentKey: AgentKey
  connectionLost: boolean
  stopped: boolean
  active: boolean
  onStop: () => void
  onRetry: () => void
}) {
  if (!active) return null
  if (connectionLost) return <p className="callout warn">Connection lost. The run continues on the server. Reload to check.</p>
  if (!run) return null
  if (run.status === 'RUNNING') return <PendingReply key={run.runId} run={run} agentKey={agentKey} stopped={stopped} onStop={onStop} />
  if (run.status === 'FAILED') {
    return (
      <div className="msg assistant">
        <span className={`avatar ${agentKey === 'data' ? 'av-d' : 'av-a'}`} aria-hidden="true">
          {AGENT_INITIAL[agentKey]}
        </span>
        <div className="bubble run-failed">
          <p className="callout warn" role="alert">
            {run.error?.message ?? 'The agent run failed.'}
          </p>
          {run.error?.retryable && (
            <button type="button" className="btn btn-sm" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      </div>
    )
  }
  return null
}
