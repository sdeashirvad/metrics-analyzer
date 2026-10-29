import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { RagStatus } from '../../backend/contracts/types'
import { StatusBadge } from '../StatusBadge'

interface AttentionRowProps {
  id: string
  name: string
  status: RagStatus
  statusLabel?: string
  fact: ReactNode
  spark?: ReactNode
  to: string
  state?: unknown
  action: string
}

export function AttentionRow({ id, name, status, statusLabel, fact, spark, to, state, action }: AttentionRowProps) {
  return (
    <li className={`attention-row tone-${status}`}>
      <StatusBadge status={status} label={statusLabel} />
      <div className="attention-main">
        <Link className="attention-title" to={to} state={state}>
          <span className="mono">{id}</span> {name}
        </Link>
        <div className="attention-fact">{fact}</div>
      </div>
      {spark && <div className="attention-spark">{spark}</div>}
      <span className="attention-action" aria-hidden="true">
        {action} →
      </span>
    </li>
  )
}
