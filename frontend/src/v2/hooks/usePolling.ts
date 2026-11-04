import { useEffect, useState } from 'react'

export const POLL_BACKOFF_MS = [2000, 4000, 8000, 15000] as const
export const POLL_GIVE_UP_MS = 5 * 60 * 1000

export function nextBackoffMs(failureIndex: number): number {
  const index = Math.min(Math.max(failureIndex, 0), POLL_BACKOFF_MS.length - 1)
  return POLL_BACKOFF_MS[index]
}

export function usePageVisible(): boolean {
  const [visible, setVisible] = useState(() => typeof document === 'undefined' || document.visibilityState !== 'hidden')
  useEffect(() => {
    const apply = () => setVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', apply)
    return () => document.removeEventListener('visibilitychange', apply)
  }, [])
  return visible
}
