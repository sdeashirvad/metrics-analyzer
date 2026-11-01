import { Link } from 'react-router-dom'
import type { MetricFamily } from '../../backend/contracts/types'
import { accessLabel, actionCopy, liveRunNote, type InvestigationAccess } from './access'

export function InvestigationMark({
  access,
  family,
  etaLabel,
}: {
  access: InvestigationAccess
  family: MetricFamily
  etaLabel: string | null
}) {
  if (access === 'checking') {
    return (
      <span className="inv-state is-checking">
        <span className="inv-placeholder-dash" aria-hidden="true">
          —
        </span>
        <span className="sr-only">Checking</span>
      </span>
    )
  }
  return (
    <span className={`inv-state is-${access}`}>
      <i className="inv-dot" aria-hidden="true" />
      <span>
        {accessLabel(access)}
        {family === 'technology_risk' && access === 'ready' && <span className="fine inv-sub">Illustrative</span>}
        {access === 'not_run' && <span className="fine inv-sub">{liveRunNote(etaLabel)}</span>}
      </span>
    </span>
  )
}

export function InvestigationActions({
  id,
  access,
  state,
  length,
  detail = true,
}: {
  id: string
  access: InvestigationAccess
  state?: unknown
  length: 'short' | 'long'
  detail?: boolean
}) {
  const action = actionCopy(access, length)
  const size = length === 'short' ? 'btn-sm' : ''
  return (
    <div className="inv-actions">
      {action ? (
        <Link className={`btn ${size} ${action.variant === 'outline' ? 'btn-outline' : 'btn-primary'}`} to={`/investigations/${id}`} state={state}>
          {action.label}
        </Link>
      ) : (
        detail && (
          <span className="inv-placeholder" aria-hidden="true">
            —
          </span>
        )
      )}
      {detail && (
        <Link className={`btn btn-quiet ${size}`} to={`/metrics/${id}`} state={state}>
          Detail
        </Link>
      )}
    </div>
  )
}
