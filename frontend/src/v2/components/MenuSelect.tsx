import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

export interface MenuOption {
  value: string
  label: string
  /** Secondary text, such as a source id, shown after the label. */
  detail?: string
}

export function MenuSelect({
  label,
  options,
  selected,
  onChange,
  multiple = false,
  emptyLabel = 'All',
  disabled = false,
  allowEmpty = true,
}: {
  label: string
  options: MenuOption[]
  selected: string[]
  onChange: (next: string[]) => void
  multiple?: boolean
  emptyLabel?: string
  disabled?: boolean
  allowEmpty?: boolean
}) {
  const [open, setOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const labelId = useId()
  const popId = useId()
  const chosen = options.filter((option) => selected.includes(option.value))
  const summary = chosen.length === 0 ? emptyLabel : chosen.length === 1 ? chosen[0].label : `${chosen.length} selected`

  useEffect(() => {
    if (!open) return
    const button = buttonRef.current
    const menu = menuRef.current
    if (!button || !menu) return

    function place() {
      if (!button || !menu) return
      const rect = button.getBoundingClientRect()
      const width = Math.max(rect.width, 220)
      const spaceBelow = window.innerHeight - rect.bottom
      const spaceAbove = rect.top
      const openUp = spaceBelow < 220 && spaceAbove > spaceBelow
      const room = Math.max(120, Math.min(280, (openUp ? spaceAbove : spaceBelow) - 12))
      let left = rect.left
      if (left + width > window.innerWidth - 8) left = Math.max(8, window.innerWidth - width - 8)
      menu.style.width = `${width}px`
      menu.style.left = `${left}px`
      menu.style.maxHeight = `${room}px`
      if (openUp) {
        menu.style.top = 'auto'
        menu.style.bottom = `${window.innerHeight - rect.top + 4}px`
      } else {
        menu.style.bottom = 'auto'
        menu.style.top = `${rect.bottom + 4}px`
      }
    }

    place()
    menu.querySelector<HTMLElement>('input:checked, input')?.focus()
    const onPointer = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (button.contains(target) || menu.contains(target)) return
      setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        button.focus()
      }
    }
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function choose(value: string) {
    if (multiple) {
      onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])
      return
    }
    onChange([value])
    setOpen(false)
    buttonRef.current?.focus()
  }

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className={`select${open ? ' is-open' : ''}${chosen.length ? ' is-selected' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        aria-label={`${label}, ${summary}`}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="select-value">{summary}</span>
        <svg viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      </button>
      {open &&
        createPortal(
          <div ref={menuRef} id={popId} className="menu-pop" role="dialog" aria-label={label}>
            <div className="menu-pop-head">
              <span className="fine">{label}</span>
              {allowEmpty && (
                <button type="button" className="btn btn-quiet btn-sm" onClick={() => onChange([])}>
                  Clear
                </button>
              )}
            </div>
            {options.length === 0 && <p className="fine">No values in this scope.</p>}
            {options.map((option) => {
              const on = selected.includes(option.value)
              return (
                <label key={option.value} className={`menu-option${on ? ' is-selected' : ''}`}>
                  <input
                    type={multiple ? 'checkbox' : 'radio'}
                    name={multiple ? undefined : labelId}
                    checked={on}
                    onChange={() => choose(option.value)}
                  />
                  <span>{option.label}{option.detail && <span className="fine menu-detail"> {option.detail}</span>}</span>
                </label>
              )
            })}
          </div>,
          document.body,
        )}
    </>
  )
}
