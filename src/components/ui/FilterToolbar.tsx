import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

interface FilterToolbarProps {
  label: string
  activeCount: number
  children: ReactNode
  summary?: ReactNode
  onClear?: () => void
}

export function FilterToolbar({ label, activeCount, children, summary, onClear }: FilterToolbarProps) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    const root = document.documentElement
    const measure = () => {
      const sticky = getComputedStyle(node).position === 'sticky'
      root.style.setProperty('--toolbar-h', sticky ? `${Math.round(node.getBoundingClientRect().height)}px` : '0px')
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => {
      observer.disconnect()
      root.style.removeProperty('--toolbar-h')
    }
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <section ref={ref} className={`filter-toolbar${open ? ' is-open' : ''}`} aria-label={label}>
      <div className="filter-toolbar-bar">
        <button type="button" className="btn filter-sheet-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((value) => !value)}>
          Filters{activeCount ? ` (${activeCount})` : ''}
        </button>
        <div id={id} className="filter-toolbar-fields">
          {children}
          {onClear && (
            <button type="button" className="btn btn-quiet" onClick={onClear} disabled={activeCount === 0}>
              Clear filters
            </button>
          )}
        </div>
      </div>
      {summary && <div className="filter-toolbar-summary">{summary}</div>}
    </section>
  )
}

export function Field({ label, children, grow = false }: { label: string; children: ReactNode; grow?: boolean }) {
  return (
    <label className={`field${grow ? ' field-grow' : ''}`}>
      <span className="field-label">{label}</span>
      {children}
    </label>
  )
}
