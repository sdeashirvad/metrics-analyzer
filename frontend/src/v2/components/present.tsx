import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { errorMessage, isUnsupportedScope } from '../agent/errors'
import type { Page, RagStatus } from '../api/types'
import { formatDuration, formatInt, labelOf } from '../format'
import type { QueryState } from '../hooks/useApiQuery'

const SCOPE_PARAMS = ['month', 'orgTree', 'l1', 'l2', 'legalEntity', 'tier', 'risk', 'lifecycle', 'ma', 'page', 'preview']

/** Shown offline when the exact month and filter combination was not packaged. Nothing is approximated. */
function UnsupportedScope({ message }: { message: string }) {
  const location = useLocation()
  const navigate = useNavigate()
  function showDefault() {
    const next = new URLSearchParams(location.search)
    for (const key of SCOPE_PARAMS) next.delete(key)
    navigate({ pathname: location.pathname, search: next.toString() ? `?${next}` : '' }, { replace: true })
  }
  return (
    <div className="callout warn" role="alert">
      <p>
        <strong>Not available offline for this scope.</strong> {message}
      </p>
      <button type="button" className="btn btn-sm" onClick={showDefault}>
        Show the default scope
      </button>
    </div>
  )
}

export function QueryPanel<T>({ query, children }: { query: QueryState<T>; children: (data: T) => ReactNode }) {
  if (query.status === 'error') {
    if (isUnsupportedScope(query.error)) return <UnsupportedScope message={errorMessage(query.error)} />
    return (
      <div className="callout warn">
        <p>{errorMessage(query.error)}</p>
        <button type="button" className="btn btn-sm" onClick={query.retry}>
          Retry
        </button>
      </div>
    )
  }
  if (!query.data) return <p className="fine">Loading…</p>
  return <>{children(query.data)}</>
}

export function Card({ title, action, children }: { title?: ReactNode; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || action) && (
        <div className="card-head">
          {title ? <h2>{title}</h2> : <span />}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

const RAG_LABEL: Record<RagStatus, string> = {
  red: 'Needs attention',
  amber: 'Watch',
  green: 'Healthy',
  unclassified: 'Unclassified',
}

export function RagPill({ rag }: { rag: RagStatus | undefined }) {
  const value = rag ?? 'unclassified'
  return (
    <span className={value === 'unclassified' ? 'chip' : `rag rag-${value}`} title="Provisional PD-01 band. A rate of 0.45 is 45%.">
      {RAG_LABEL[value]}
    </span>
  )
}

export function Dash({ value }: { value: string | null | undefined }) {
  return <span className="num">{value == null || value === '' ? '—' : value}</span>
}

/** `of` names what the marker qualifies, so repeated markers on one page have distinct link names. */
export function Provisional({ id, of }: { id?: string; of?: string }) {
  const base = id ? `Provisional definition ${id}` : 'Provisional definition'
  const label = of ? `${base}, ${of}` : base
  return id ? (
    <Link className="info-mark" to={`/definitions#${id}`} aria-label={label} title={label}>
      i
    </Link>
  ) : (
    <span className="info-mark" title={label} aria-label={label}>
      i
    </span>
  )
}

export function Pager({ page, onPage, noun }: { page: Page; onPage: (page: number) => void; noun?: string }) {
  const total = noun ? `${formatInt(page.totalItems)} ${noun}` : formatInt(page.totalItems)
  if (page.totalPages <= 1) return <p className="fine num">{total}</p>
  return (
    <div className="pager">
      <button type="button" className="btn btn-sm" disabled={page.page <= 1} onClick={() => onPage(page.page - 1)}>
        Previous
      </button>
      <span className="fine num">
        {formatInt(page.page)} / {formatInt(page.totalPages)} · {total}
      </span>
      <button type="button" className="btn btn-sm" disabled={page.page >= page.totalPages} onClick={() => onPage(page.page + 1)}>
        Next
      </button>
    </div>
  )
}

const STATUS_TONE: Record<string, string> = {
  Non_Compliant: 'red',
  NEWLY_NON_COMPLIANT: 'red',
  PERSISTENT_NON_COMPLIANT: 'red',
  Fail: 'red',
  Failed: 'red',
  Compliant: 'green',
  RESOLVED: 'green',
  Pass: 'green',
  Test_Complete: 'green',
  Pending: 'amber',
  Test_Pending: 'amber',
  Not_Applicable: 'na',
  Exempt: 'na',
  No_Test: 'na',
  NO_PRIOR_MONTH: 'na',
  OTHER: 'na',
  NOT_NON_COMPLIANT_BOTH_MONTHS: 'na',
}

export function StatusChip({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="fine">—</span>
  return (
    <span className={`chip ${STATUS_TONE[value] ?? 'na'}`}>
      <i />
      {labelOf(value)}
    </span>
  )
}

function focusable(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])')].filter((element) => {
    if (element.getAttribute('aria-hidden') === 'true') return false
    const style = window.getComputedStyle(element)
    return style.display !== 'none' && style.visibility !== 'hidden'
  })
}

/** Moves focus into a dialog, keeps Tab inside it, and restores focus on close. */
export function useFocusContain(containerRef: RefObject<HTMLElement | null>, onEscape: () => void) {
  const escapeRef = useRef(onEscape)
  escapeRef.current = onEscape
  useEffect(() => {
    const root = containerRef.current
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const initial = root?.querySelector<HTMLElement>('[data-initial-focus]') ?? root?.querySelector<HTMLElement>('h2, button')
    initial?.focus()
    function onKey(event: KeyboardEvent) {
      const current = containerRef.current
      if (!current) return
      const top = document.querySelector<HTMLElement>('.dialog, .menu-pop')
      if (top && top !== current && !current.contains(top)) return
      if (event.key === 'Escape') {
        event.preventDefault()
        escapeRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const items = focusable(current)
      if (!items.length) {
        event.preventDefault()
        return
      }
      const index = items.indexOf(document.activeElement as HTMLElement)
      if (event.shiftKey) {
        if (index <= 0) {
          event.preventDefault()
          items[items.length - 1].focus()
        }
      } else if (index === -1 || index === items.length - 1) {
        event.preventDefault()
        items[0].focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      if (previous && document.contains(previous)) previous.focus()
    }
  }, [containerRef])
}

export function Elapsed({ submittedAt, running, serverMs }: { submittedAt: string; running: boolean; serverMs: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])
  const local = Math.max(0, now - Date.parse(submittedAt))
  return <span className="fine num">{formatDuration(running ? Math.max(serverMs, local) : serverMs)}</span>
}

export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusContain(ref, onClose)
  return createPortal(
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <div ref={ref} className="dialog" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}>
        <div className="spread">
          <h2 tabIndex={-1} data-initial-focus>
            {title}
          </h2>
          <button type="button" className="btn btn-quiet btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}
