import { useId, useState, type ReactNode } from 'react'

interface DisclosureProps {
  summary: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  className?: string
}

export function Disclosure({ summary, children, defaultOpen = false, className }: DisclosureProps) {
  const [open, setOpen] = useState(defaultOpen)
  const id = useId()
  return (
    <div className={`disclosure${open ? ' is-open' : ''}${className ? ` ${className}` : ''}`}>
      <button type="button" className="disclosure-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((value) => !value)}>
        <span className="chevron" aria-hidden="true" />
        {summary}
      </button>
      <div id={id} className="disclosure-body" hidden={!open}>
        {children}
      </div>
    </div>
  )
}
