import type { ReactNode } from 'react'

export function SectionLoading({ label = 'Loading', lines = 3, tall = false }: { label?: string; lines?: number; tall?: boolean }) {
  return (
    <div className="section-loading" role="status">
      <span className="sr-only">{label}</span>
      {tall && <div className="skel skel-lg" />}
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className={`skel${index === lines - 1 ? ' skel-sm' : ''}`} />
      ))}
    </div>
  )
}

export function RefreshLine({ active }: { active: boolean }) {
  return <div className={`refresh-line${active ? ' is-active' : ''}`} aria-hidden="true" />
}

export function SectionError({ title = 'This section could not be loaded', message, onRetry }: { title?: string; message: string; onRetry: () => void }) {
  return (
    <div className="section-state is-error" role="alert">
      <h3>{title}</h3>
      <p className="muted">{message}</p>
      <button type="button" className="btn" onClick={onRetry}>
        Retry
      </button>
    </div>
  )
}

export function SectionEmpty({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="section-state">
      <h3>{title}</h3>
      {body && <p className="muted">{body}</p>}
      {action && <div className="row">{action}</div>}
    </div>
  )
}

export function SectionUnavailable({ title, body }: { title: string; body?: string }) {
  return (
    <div className="section-state is-unavailable">
      <h3>{title}</h3>
      {body && <p className="muted">{body}</p>}
    </div>
  )
}

export function PageLoading({ label }: { label: string }) {
  return (
    <div className="page">
      <SectionLoading label={label} lines={4} tall />
    </div>
  )
}

export function PageError({ title = 'This view could not be loaded', message, onRetry }: { title?: string; message: string; onRetry: () => void }) {
  return (
    <div className="page page-narrow">
      <SectionError title={title} message={message} onRetry={onRetry} />
    </div>
  )
}
