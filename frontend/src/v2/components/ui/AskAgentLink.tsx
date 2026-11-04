import { Link } from 'react-router-dom'

const SPARK = 'M12 3l1.6 5.2L19 10l-5.4 1.8L12 17l-1.6-5.2L5 10l5.4-1.8L12 3z'

/**
 * The only way a page outside the Agent workspace offers the Agent.
 * It navigates to the central workspace and never opens a chat here.
 * Pass `to` only for the Register Preview, which seeds a bounded context.
 * `state` carries the origin so the workspace can offer a way back.
 */
export function AskAgentLink({
  to = '/agent',
  label = 'Ask Agent',
  variant = 'ask',
  state,
}: {
  to?: string
  label?: string
  variant?: 'ask' | 'button'
  state?: unknown
}) {
  return (
    <Link className={variant === 'ask' ? 'ask' : 'btn btn-agent'} to={to} state={state}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d={SPARK} />
      </svg>
      {label}
    </Link>
  )
}
