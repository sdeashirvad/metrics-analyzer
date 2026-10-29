export class ApiError extends Error {
  code: 'NOT_FOUND' | 'BAD_REQUEST'
  status: number

  constructor(code: 'NOT_FOUND' | 'BAD_REQUEST', message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

export function notFound(message: string): ApiError {
  return new ApiError('NOT_FOUND', message, 404)
}
