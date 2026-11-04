import type { ReactNode, RefObject } from 'react'

/**
 * The message box used on every Agent route.
 *
 * The activity indicator is a status element in the top-right corner of the box. It is announced
 * to assistive technology, never overlaps the text caret, and stops animating when the user
 * prefers reduced motion (see .composer-dot in components.css).
 */
export function Composer({
  value,
  onChange,
  onSubmit,
  placeholder,
  label = 'Message',
  disabled = false,
  canSend,
  sending = false,
  busyLabel,
  error,
  hint,
  inputRef,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  placeholder: string
  label?: string
  /** Blocks typing, for example while the Agent is answering. */
  disabled?: boolean
  canSend: boolean
  sending?: boolean
  /** Shown in the status corner while the Agent is working or a message is being sent. */
  busyLabel?: string | null
  error?: ReactNode
  hint?: ReactNode
  inputRef?: RefObject<HTMLTextAreaElement | null>
}) {
  const busy = Boolean(busyLabel) || sending
  return (
    <form
      className={`composer dock${busy ? ' is-busy' : ''}`}
      onSubmit={(event) => {
        event.preventDefault()
        if (canSend && !sending) onSubmit()
      }}
    >
      <span className="composer-status" role="status" aria-live="polite">
        {busy && (
          <>
            <span className="composer-dot" aria-hidden="true" />
            <span>{sending ? 'Sending…' : busyLabel}</span>
          </>
        )}
      </span>
      <label className="field">
        <span className="sr-only">{label}</span>
        <textarea
          ref={inputRef}
          value={value}
          maxLength={2000}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              if (canSend && !sending) onSubmit()
            }
          }}
        />
      </label>
      <div className="composer-bar">
        {hint && <p className="fine">{hint}</p>}
        {error && (
          <p className="callout warn" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="ask" disabled={!canSend || sending} title={canSend ? 'Send' : undefined}>
          {sending ? 'Sending…' : 'Send'}
        </button>
      </div>
    </form>
  )
}
