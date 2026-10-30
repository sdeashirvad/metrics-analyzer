import { useRef, type KeyboardEvent, type ReactNode } from 'react'

export interface TabItem<T extends string> {
  id: T
  label: ReactNode
}

interface TabsProps<T extends string> {
  label: string
  idPrefix: string
  tabs: TabItem<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
}

export function tabId(prefix: string, id: string) {
  return `${prefix}-tab-${id}`
}

export function panelId(prefix: string, id: string) {
  return `${prefix}-panel-${id}`
}

export function Tabs<T extends string>({ label, idPrefix, tabs, value, onChange, className }: TabsProps<T>) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = -1
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length
    if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = tabs.length - 1
    if (next < 0) return
    event.preventDefault()
    onChange(tabs[next].id)
    refs.current[next]?.focus()
  }

  return (
    <div className={`tabs${className ? ` ${className}` : ''}`} role="tablist" aria-label={label}>
      {tabs.map((tab, index) => {
        const selected = tab.id === value
        return (
          <button
            key={tab.id}
            ref={(node) => {
              refs.current[index] = node
            }}
            id={tabId(idPrefix, tab.id)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelId(idPrefix, tab.id)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

export function TabPanel({ idPrefix, id, children, className }: { idPrefix: string; id: string; children: ReactNode; className?: string }) {
  return (
    <div id={panelId(idPrefix, id)} role="tabpanel" aria-labelledby={tabId(idPrefix, id)} tabIndex={0} className={className}>
      {children}
    </div>
  )
}
