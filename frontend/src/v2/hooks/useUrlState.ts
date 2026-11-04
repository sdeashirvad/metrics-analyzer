import { useCallback } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

export type ParamPatch = Record<string, string | null | undefined>

/**
 * In-page URL state. `commit: false` (default) replaces the history entry, `commit: true`
 * pushes one. Scroll position is never reset and the location's origin state is kept.
 */
/**
 * Filter changes can shrink the page and make the browser shift the scroll offset. Re-apply the
 * pre-change offset for a moment unless the user starts scrolling themselves.
 */
function holdScroll(y: number) {
  if (y <= 0) return
  let active = true
  const stop = () => {
    active = false
    cleanup()
  }
  const cleanup = () => {
    window.removeEventListener('wheel', stop)
    window.removeEventListener('touchstart', stop)
    window.removeEventListener('keydown', stop)
  }
  window.addEventListener('wheel', stop, { passive: true })
  window.addEventListener('touchstart', stop, { passive: true })
  window.addEventListener('keydown', stop)
  const apply = () => {
    if (!active) return
    const max = document.documentElement.scrollHeight - window.innerHeight
    const target = Math.min(y, Math.max(0, max))
    if (Math.abs(window.scrollY - target) > 1) window.scrollTo({ top: target, behavior: 'instant' as ScrollBehavior })
  }
  for (const delay of [0, 30, 80, 160, 320]) window.setTimeout(apply, delay)
  window.setTimeout(stop, 360)
}

export function useUrlState() {
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const state = location.state as unknown

  const update = useCallback(
    (patch: ParamPatch, options: { commit?: boolean } = {}) => {
      holdScroll(window.scrollY)
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          for (const [name, value] of Object.entries(patch)) {
            if (value) next.set(name, value)
            else next.delete(name)
          }
          return next
        },
        { replace: !options.commit, preventScrollReset: true, state },
      )
    },
    [setParams, state],
  )

  return [params, update] as const
}
