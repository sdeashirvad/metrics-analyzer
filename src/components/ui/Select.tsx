import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'

export interface SelectOption {
  value: string
  label: string
  group?: string
}

interface SelectProps {
  value: string
  options: SelectOption[]
  onChange: (value: string) => void
  /** id of the element that labels this control */
  labelledBy?: string
  ariaLabel?: string
  className?: string
}

const TYPEAHEAD_MS = 650
const MENU_MAX = 288

/**
 * Select-only combobox following the ARIA authoring practices pattern.
 * Keeps focus on the trigger and drives the list with aria-activedescendant.
 */
export function Select({ value, options, onChange, labelledBy, ariaLabel, className }: SelectProps) {
  const uid = useId()
  const listId = `${uid}-list`
  const optionId = (index: number) => `${uid}-opt-${index}`
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [placement, setPlacement] = useState<'down' | 'up'>('down')
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const typed = useRef({ text: '', timer: 0 })

  const selectedIndex = Math.max(
    0,
    options.findIndex((option) => option.value === value),
  )
  const selected = options[selectedIndex]

  const groups = useMemo(() => {
    const out: Array<{ label: string | null; items: Array<{ option: SelectOption; index: number }> }> = []
    options.forEach((option, index) => {
      const label = option.group ?? null
      const last = out[out.length - 1]
      if (last && last.label === label) last.items.push({ option, index })
      else out.push({ label, items: [{ option, index }] })
    })
    return out
  }, [options])

  const openMenu = useCallback(
    (at?: number) => {
      setActive(at ?? selectedIndex)
      setOpen(true)
    },
    [selectedIndex],
  )

  const close = useCallback(() => setOpen(false), [])

  const choose = useCallback(
    (index: number) => {
      const option = options[index]
      setOpen(false)
      triggerRef.current?.focus()
      if (option && option.value !== value) onChange(option.value)
    },
    [onChange, options, value],
  )

  // Decide whether the menu opens upward when there is not enough room below.
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const needed = Math.min(MENU_MAX, options.length * 34 + 12 + groups.filter((g) => g.label).length * 26)
    const below = window.innerHeight - rect.bottom
    setPlacement(below < needed + 8 && rect.top > below ? 'up' : 'down')
  }, [open, options.length, groups])

  // Keep the active option visible inside the list without scrolling the page.
  useEffect(() => {
    if (!open) return
    const list = listRef.current
    const node = document.getElementById(optionId(active))
    if (!list || !node) return
    const top = node.offsetTop
    const bottom = top + node.offsetHeight
    if (top < list.scrollTop) list.scrollTop = top - 4
    else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight + 4
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, active])

  // Close on outside pointer press.
  useEffect(() => {
    if (!open) return
    const onDown = (event: MouseEvent | TouchEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('touchstart', onDown)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('touchstart', onDown)
    }
  }, [open])

  function typeahead(char: string) {
    const state = typed.current
    window.clearTimeout(state.timer)
    state.text += char.toLowerCase()
    state.timer = window.setTimeout(() => {
      state.text = ''
    }, TYPEAHEAD_MS)
    const start = state.text.length === 1 ? (open ? active : selectedIndex) + 1 : open ? active : selectedIndex
    const order = [...options.keys()].map((i) => (start + i) % options.length)
    const hit = order.find((i) => options[i].label.toLowerCase().startsWith(state.text))
    if (hit === undefined) return
    if (open) setActive(hit)
    else openMenu(hit)
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const last = options.length - 1
    if (!open) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        openMenu()
      } else if (event.key === 'Home') {
        event.preventDefault()
        openMenu(0)
      } else if (event.key === 'End') {
        event.preventDefault()
        openMenu(last)
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault()
        typeahead(event.key)
      }
      return
    }
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        setActive((index) => Math.min(last, index + 1))
        break
      case 'ArrowUp':
        event.preventDefault()
        setActive((index) => Math.max(0, index - 1))
        break
      case 'Home':
        event.preventDefault()
        setActive(0)
        break
      case 'End':
        event.preventDefault()
        setActive(last)
        break
      case 'PageDown':
        event.preventDefault()
        setActive((index) => Math.min(last, index + 8))
        break
      case 'PageUp':
        event.preventDefault()
        setActive((index) => Math.max(0, index - 8))
        break
      case 'Enter':
      case ' ':
        event.preventDefault()
        choose(active)
        break
      case 'Escape':
        event.preventDefault()
        event.stopPropagation()
        close()
        break
      case 'Tab':
        close()
        break
      default:
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          event.preventDefault()
          typeahead(event.key)
        }
    }
  }

  return (
    <div ref={rootRef} className={`select${className ? ` ${className}` : ''}${open ? ' is-open' : ''}`}>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        className="select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-labelledby={labelledBy}
        aria-label={labelledBy ? undefined : ariaLabel}
        aria-activedescendant={open ? optionId(active) : undefined}
        onClick={() => (open ? close() : openMenu())}
        onKeyDown={onKeyDown}
        onBlur={(event) => {
          if (!rootRef.current?.contains(event.relatedTarget as Node | null)) close()
        }}
      >
        <span className="select-value">{selected?.label ?? ''}</span>
        <svg className="select-caret" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
          <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <ul
        ref={listRef}
        id={listId}
        role="listbox"
        tabIndex={-1}
        aria-labelledby={labelledBy}
        aria-label={labelledBy ? undefined : ariaLabel}
        className={`select-menu place-${placement}`}
        hidden={!open}
        onMouseDown={(event) => event.preventDefault()}
      >
        {open &&
          groups.map((group, groupIndex) => {
            const items = group.items.map(({ option, index }) => (
              <li
                key={`${option.value}-${index}`}
                id={optionId(index)}
                role="option"
                aria-selected={index === selectedIndex}
                className={`select-option${index === active ? ' is-active' : ''}${index === selectedIndex ? ' is-selected' : ''}`}
                onMouseMove={() => index !== active && setActive(index)}
                onClick={() => choose(index)}
              >
                <span className="select-option-label">{option.label}</span>
                {index === selectedIndex && (
                  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
                    <path d="m2.5 6.3 2.4 2.4 4.6-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </li>
            ))
            if (!group.label) return items
            const labelId = `${uid}-group-${groupIndex}`
            return (
              <li key={`g-${groupIndex}`} role="presentation" className="select-group">
                <span id={labelId} className="select-group-label" role="presentation">
                  {group.label}
                </span>
                <ul role="group" aria-labelledby={labelId}>
                  {items}
                </ul>
              </li>
            )
          })}
      </ul>
    </div>
  )
}

interface SelectFieldProps extends Omit<SelectProps, 'labelledBy' | 'ariaLabel'> {
  label: string
  grow?: boolean
  hideLabel?: boolean
  inline?: boolean
}

/** Label + custom select. Uses aria-labelledby so the accessible name is the label text. */
export function SelectField({ label, grow, hideLabel, inline, ...rest }: SelectFieldProps) {
  const id = useId()
  return (
    <div className={`field${grow ? ' field-grow' : ''}${inline ? ' field-inline' : ''}`}>
      <span id={id} className={hideLabel ? 'sr-only' : 'field-label'}>
        {label}
      </span>
      <Select {...rest} labelledBy={id} />
    </div>
  )
}
