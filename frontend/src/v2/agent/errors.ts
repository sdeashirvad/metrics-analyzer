import { MissingApiBaseError } from '../api/config'
import { ApiError } from '../api/http'

export function errorMessage(error: unknown): string {
  if (error instanceof MissingApiBaseError) return error.message
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : 'That request could not be completed.'
  switch (error.code) {
    case 'AGENT_BUSY':
      return 'The agents are busy. Your message is still here.'
    case 'RATE_LIMITED':
      return 'Too many requests. Wait, then try again.'
    case 'AGENT_BUDGET_EXHAUSTED':
      return error.retryAfterMs ? 'The agent budget is exhausted.' : 'The agent budget is exhausted.'
    case 'CONTEXT_STALE':
      return 'The context changed. Review it again before sending.'
    case 'THREAD_UNAVAILABLE':
      return 'The conversation could not be read. Retry the read.'
    case 'CONVERSATION_NOT_FOUND':
      return 'This conversation is no longer available.'
    case 'MESSAGE_TOO_LONG':
      return 'That message is too long.'
    case 'CONTEXT_TOO_LARGE':
      return 'The context is too large. Turn off an optional item.'
    case 'RUN_IN_PROGRESS':
      return 'A run is already in progress.'
    case 'AGENT_UNAVAILABLE':
      return 'The agent is unavailable.'
    case 'RUN_NOT_RETRYABLE':
      return 'That run cannot be retried.'
    default:
      return error.message || 'That request could not be completed.'
  }
}

/** Offline, and the request is for a month and filter combination that was not packaged. */
export function isUnsupportedScope(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'FALLBACK_UNSUPPORTED'
}

export function isContextStale(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'CONTEXT_STALE'
}

export function isRefusal(error: unknown): boolean {
  return error instanceof ApiError && (error.code === 'AGENT_BUSY' || error.code === 'AGENT_BUDGET_EXHAUSTED' || error.code === 'AGENT_UNAVAILABLE' || error.code === 'RATE_LIMITED')
}
