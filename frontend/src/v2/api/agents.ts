import { agentsUrl } from './config'
import { apiGet, apiSend, type ApiResult } from './http'
import type {
  AgentsList,
  ContextPreview,
  ContextRequest,
  ConversationContextSummary,
  ConversationDetail,
  CreateConversationRequest,
  CreateConversationResult,
  RetryRunResult,
  Run,
  SendMessageRequest,
  SendMessageResult,
} from './types'

export function listAgents(): Promise<ApiResult<AgentsList>> {
  return apiGet(agentsUrl(''))
}

export function previewContext(request: ContextRequest): Promise<ApiResult<ContextPreview>> {
  return apiSend(agentsUrl('/context/preview'), request)
}

export function createConversation(request: CreateConversationRequest): Promise<ApiResult<CreateConversationResult>> {
  return apiSend(agentsUrl('/conversations'), request)
}

export function getConversation(conversationId: string): Promise<ApiResult<ConversationDetail>> {
  return apiGet(agentsUrl(`/conversations/${encodeURIComponent(conversationId)}`))
}

export function getConversationContext(conversationId: string): Promise<ApiResult<ConversationContextSummary>> {
  return apiGet(agentsUrl(`/conversations/${encodeURIComponent(conversationId)}/context`))
}

export function sendMessage(conversationId: string, request: SendMessageRequest): Promise<ApiResult<SendMessageResult>> {
  return apiSend(agentsUrl(`/conversations/${encodeURIComponent(conversationId)}/messages`), request)
}

export function getRun(runId: string): Promise<ApiResult<Run>> {
  return apiGet(agentsUrl(`/runs/${encodeURIComponent(runId)}`))
}

export function retryRun(runId: string): Promise<ApiResult<RetryRunResult>> {
  return apiSend(agentsUrl(`/runs/${encodeURIComponent(runId)}/retry`), {})
}

export function exportQueryUrl(conversationId: string, messageId: string, index: number): string {
  return agentsUrl(
    `/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/queries/${index}/export`,
  )
}
