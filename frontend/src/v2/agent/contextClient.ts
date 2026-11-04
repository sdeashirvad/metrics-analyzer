import type { AgentKey, ContextRequest, EntrySurface } from '../api/types'

const KEY = 'ma2:ctx'

export interface ReviewedContext {
  request: ContextRequest
  contextHash: string
  agentKey?: AgentKey
}

export function buildContextRequest(
  entrySurface: EntrySurface,
  scope: ContextRequest['scope'],
  items?: { include?: string[]; exclude?: string[] },
): ContextRequest {
  const request: ContextRequest = { entrySurface, scope }
  const include = items?.include?.filter(Boolean)
  const exclude = items?.exclude?.filter(Boolean)
  if (include?.length || exclude?.length) {
    request.items = {}
    if (include?.length) request.items.include = include
    if (exclude?.length) request.items.exclude = exclude
  }
  return request
}

export function saveReviewedContext(value: ReviewedContext) {
  const payload: ReviewedContext = {
    request: value.request,
    contextHash: value.contextHash,
    agentKey: value.agentKey,
  }
  sessionStorage.setItem(KEY, JSON.stringify(payload))
}

export function readReviewedContext(): ReviewedContext | null {
  try {
    const text = sessionStorage.getItem(KEY)
    if (!text) return null
    const parsed = JSON.parse(text) as ReviewedContext
    if (!parsed?.request || typeof parsed.contextHash !== 'string') return null
    return { request: parsed.request, contextHash: parsed.contextHash, agentKey: parsed.agentKey }
  } catch {
    return null
  }
}

export function clearReviewedContext() {
  sessionStorage.removeItem(KEY)
}
