import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

export interface Origin {
  pathname: string
  search: string
  label: string
  idx: number | null
  from?: Origin
}

interface OriginState {
  from?: Origin
}

function historyIdx(): number | null {
  const value = (window.history.state as { idx?: unknown } | null)?.idx
  return typeof value === 'number' ? value : null
}

/** State to attach to a Link so the target page can return here. */
export function useLinkState(label: string): OriginState {
  const location = useLocation()
  const parent = (location.state as OriginState | null)?.from
  return {
    from: { pathname: location.pathname, search: location.search, label, idx: historyIdx(), from: parent },
  }
}

export interface BackTarget {
  to: string
  label: string
  state: OriginState | undefined
  fromOrigin: boolean
  go: (event: { preventDefault: () => void }) => void
}

/**
 * Where "back" should go. With an in-app origin it pops history to that entry,
 * which restores its scroll position; otherwise it links to the fallback.
 */
export function useBackTarget(fallback: { to: string; label: string }): BackTarget {
  const location = useLocation()
  const navigate = useNavigate()
  const origin = (location.state as OriginState | null)?.from
  const to = origin ? `${origin.pathname}${origin.search}` : fallback.to
  const go = useCallback(
    (event: { preventDefault: () => void }) => {
      const now = historyIdx()
      if (!origin || origin.idx == null || now == null || origin.idx >= now) return
      event.preventDefault()
      navigate(origin.idx - now)
    },
    [navigate, origin],
  )
  return {
    to,
    label: origin?.label ?? fallback.label,
    state: origin?.from ? { from: origin.from } : undefined,
    fromOrigin: Boolean(origin),
    go,
  }
}
