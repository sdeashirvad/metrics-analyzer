import { useEffect, useState, type KeyboardEvent } from 'react'
import type { ArchStep } from './model'

interface WalkthroughProps {
  title: string
  steps: ArchStep[]
  step: number
  onStep: (next: number) => void
  held: boolean
}

export function Walkthrough({ title, steps, step, onStep, held }: WalkthroughProps) {
  const [playing, setPlaying] = useState(false)
  const current = step >= 0 ? steps[step] : null
  const last = steps.length - 1

  useEffect(() => {
    if (!playing || held) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setPlaying(false)
      return
    }
    const timer = window.setTimeout(() => {
      if (step >= last) setPlaying(false)
      else onStep(step < 0 ? 0 : step + 1)
    }, 1400)
    return () => window.clearTimeout(timer)
  }, [playing, held, step, last, onStep])

  function prev() {
    onStep(Math.max(0, step - 1))
  }

  function next() {
    onStep(step < 0 ? 0 : Math.min(last, step + 1))
  }

  function togglePlay() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      next()
      return
    }
    if (!playing && step >= last) onStep(0)
    setPlaying((value) => !value)
  }

  function replay() {
    setPlaying(false)
    onStep(0)
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowRight') {
      event.preventDefault()
      next()
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault()
      prev()
    } else if (event.key === ' ') {
      event.preventDefault()
      togglePlay()
    }
  }

  const progress = step < 0 ? 0 : ((step + 1) / steps.length) * 100

  return (
    <div className="arch-dock no-print" role="group" aria-label={`${title} walkthrough`} onKeyDown={onKeyDown}>
      <div className="arch-dock-progress" aria-hidden="true">
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className="arch-dock-row">
        <div className="arch-dock-caption">
          <p className="arch-dock-title">
            {title}
            <span className="fine num"> · {step < 0 ? `${steps.length} steps` : `Step ${step + 1} of ${steps.length}`}</span>
          </p>
          {current ? (
            <p>
              <strong>{current.title}.</strong> <span className="muted">{current.badge}.</span> {current.caption}
            </p>
          ) : (
            <p className="muted">Optional. Highlights the nodes involved in each step. Arrow keys step; Space plays or pauses.</p>
          )}
        </div>
        <div className="arch-dock-actions">
          <button type="button" className="btn btn-sm" onClick={prev} disabled={step <= 0}>
            Previous
          </button>
          <button type="button" className="btn btn-sm" onClick={next} disabled={step >= last}>
            Next
          </button>
          <button type="button" className="btn btn-sm btn-primary" onClick={togglePlay} aria-pressed={playing}>
            {playing ? 'Pause' : 'Play'}
          </button>
          <button type="button" className="btn btn-sm btn-quiet" onClick={replay}>
            Replay
          </button>
        </div>
      </div>
    </div>
  )
}
