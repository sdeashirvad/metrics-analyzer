const MISSING_BASE = 'This build has no API address. Set VITE_API_BASE_URL to the deployed API before building.'

export class MissingApiBaseError extends Error {
  constructor() {
    super(MISSING_BASE)
    this.name = 'MissingApiBaseError'
  }
}

/** `VITE_API_BASE_URL` already ends with `/api/v1`. */
export function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  if (configured) return configured.replace(/\/$/, '')
  if (import.meta.env.PROD) throw new MissingApiBaseError()
  return 'http://localhost:8080/api/v1'
}

export function portfolioUrl(path: string): string {
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${apiBase()}/portfolio${suffix}`
}

export function agentsUrl(path: string): string {
  if (!path || path === '/') return `${apiBase()}/agents`
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${apiBase()}/agents${suffix}`
}
