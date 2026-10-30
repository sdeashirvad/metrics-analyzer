import type { RagStatus } from '../backend/contracts/types'
import { statusLabel } from '../domain/format'

export function StatusGlyph({ status, size = 10 }: { status: RagStatus; size?: number }) {
  return (
    <svg className={`glyph glyph-${status}`} width={size} height={size} viewBox="0 0 10 10" aria-hidden="true" focusable="false">
      {status === 'red' && <circle cx="5" cy="5" r="4.5" />}
      {status === 'amber' && <path d="M5 0.6 9.6 9.2H0.4Z" />}
      {status === 'green' && <path d="M1.2 5.4 3.9 8 8.8 2.2" fill="none" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />}
      {status === 'insufficient_data' && <circle cx="5" cy="5" r="3.8" fill="none" strokeWidth="1.6" />}
    </svg>
  )
}

export function StatusBadge({ status, label }: { status: RagStatus; label?: string }) {
  return (
    <span className={`badge badge-${status}`}>
      <StatusGlyph status={status} />
      {label ?? statusLabel(status)}
    </span>
  )
}
