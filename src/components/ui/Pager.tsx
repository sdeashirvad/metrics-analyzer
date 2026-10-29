import { useEffect, useRef } from 'react'

interface PagerProps {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
  label: string
}

export function rangeText(page: number, pageSize: number, total: number) {
  if (total === 0) return '0 of 0'
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  return `${start}–${end} of ${total}`
}

export function Pager({ page, pageSize, total, onPage, label }: PagerProps) {
  const prevRef = useRef<HTMLButtonElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const pendingFocus = useRef<'prev' | 'next' | null>(null)
  const pages = Math.max(1, Math.ceil(total / pageSize))

  useEffect(() => {
    const target = pendingFocus.current
    if (!target) return
    const button = target === 'prev' ? prevRef.current : nextRef.current
    if (button && !button.disabled) {
      button.focus()
      pendingFocus.current = null
    }
  })

  function go(next: number) {
    pendingFocus.current = next <= 1 ? 'next' : next >= pages ? 'prev' : null
    onPage(next)
  }

  if (total <= pageSize) return null
  return (
    <nav className="pager" aria-label={label}>
      <button ref={prevRef} type="button" className="btn" disabled={page <= 1} onClick={() => go(page - 1)}>
        Previous
      </button>
      <span className="pager-status num" aria-live="polite">
        {rangeText(page, pageSize, total)} · Page {page} of {pages}
      </span>
      <button ref={nextRef} type="button" className="btn" disabled={page >= pages} onClick={() => go(page + 1)}>
        Next
      </button>
    </nav>
  )
}
