import type { ApiErrorBody, Envelope, EnvelopeMeta, FieldError } from './types'
import { MissingApiBaseError } from './config'

const TIMEOUT_MS = 20_000

export interface ApiResult<T> {
  data: T
  meta: EnvelopeMeta
}

export class ApiError extends Error {
  readonly code: string
  readonly retryable: boolean
  readonly requestId: string
  readonly status: number
  readonly fieldErrors?: FieldError[]
  readonly retryAfterMs?: number
  readonly details?: Record<string, unknown>

  constructor(init: {
    code: string
    message: string
    retryable: boolean
    requestId: string
    status: number
    fieldErrors?: FieldError[]
    retryAfterMs?: number
    details?: Record<string, unknown>
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.code = init.code
    this.retryable = init.retryable
    this.requestId = init.requestId
    this.status = init.status
    this.fieldErrors = init.fieldErrors
    this.retryAfterMs = init.retryAfterMs
    this.details = init.details
  }
}

let contractWarned = false

function noteContract(meta: EnvelopeMeta | undefined) {
  if (!import.meta.env.DEV || contractWarned || !meta?.contractVersion) return
  const major = String(meta.contractVersion).split('.')[0]
  if (major !== '2') {
    contractWarned = true
    console.warn(`API contract major is ${meta.contractVersion}; this client expects 2.x.`)
  }
}

async function readError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null
  try {
    body = (await response.json()) as ApiErrorBody
  } catch {
    body = null
  }
  const error = body?.error
  const message = error?.message && error.message.length < 500 ? error.message : 'That request could not be completed.'
  return new ApiError({
    code: error?.code || (response.status === 404 ? 'NOT_FOUND' : 'UPSTREAM_ERROR'),
    message,
    retryable: error?.retryable ?? response.status >= 500,
    requestId: error?.requestId || '',
    status: response.status,
    fieldErrors: error?.fieldErrors,
    retryAfterMs: error?.retryAfterMs,
    details: error?.details,
  })
}

async function request<T>(url: string, method: 'GET' | 'POST', body: string | undefined, attempt: number): Promise<ApiResult<T>> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const response = await fetch(url, {
      method,
      body,
      signal: controller.signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
    })
    if (!response.ok) {
      if (method === 'GET' && response.status >= 500 && attempt < 1) {
        return request(url, method, body, attempt + 1)
      }
      throw await readError(response)
    }
    const payload = (await response.json()) as Envelope<T>
    noteContract(payload.meta)
    return { data: payload.data, meta: payload.meta }
  } catch (error) {
    if (error instanceof ApiError || error instanceof MissingApiBaseError) throw error
    if (method === 'GET' && attempt < 1) return request(url, method, body, attempt + 1)
    const timedOut = error instanceof DOMException && error.name === 'AbortError'
    throw new ApiError({
      code: 'UPSTREAM_ERROR',
      message: timedOut ? 'The request took too long. Try again.' : 'The service could not be reached. Check the connection and try again.',
      retryable: true,
      requestId: '',
      status: 0,
    })
  } finally {
    window.clearTimeout(timer)
  }
}

export function apiGet<T>(url: string): Promise<ApiResult<T>> {
  return request<T>(url, 'GET', undefined, 0)
}

export function apiSend<T>(url: string, body: unknown): Promise<ApiResult<T>> {
  return request<T>(url, 'POST', JSON.stringify(body), 0)
}
