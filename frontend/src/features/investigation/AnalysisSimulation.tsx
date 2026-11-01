import { useEffect, useState } from 'react'

interface AnalysisSimulationProps {
  stages: string[]
  onDone: () => void
  stageMs?: number
  note: string
  hold?: boolean
}

/**
 * Scripted "analysis in progress" sequence shown every time an investigation opens.
 * It is a fixed list of steps in the browser: no model, Snowflake Cortex or SMARTS call is made.
 */
export function AnalysisSimulation({ stages, onDone, note, stageMs = 1440, hold = false }: AnalysisSimulationProps) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    let current = 0
    const timer = window.setInterval(() => {
      current += 1
      if (current >= stages.length - 1) {
        setStep(stages.length - 1)
        if (hold) {
          window.clearInterval(timer)
          return
        }
      }
      if (current >= stages.length) {
        window.clearInterval(timer)
        onDone()
        return
      }
      setStep(current)
    }, stageMs)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stages.length, stageMs])

  return (
    <section className="card analysis no-print" aria-live="polite">
      <p className="eyebrow">
        Illustrative walkthrough · {step + 1} of {stages.length}
      </p>
      <h2>{stages[step]}</h2>
      <p className="fine">{note}</p>
      <div className="analysis-track" aria-hidden="true">
        <span key={step} style={{ animationDuration: `${stageMs}ms` }} />
      </div>
      {step > 0 && (
        <ol className="stages">
          {stages.slice(0, step).map((label) => (
            <li key={label} className="is-done">
              {label}
            </li>
          ))}
        </ol>
      )}
      <div className="actions">
        <button type="button" className="btn" onClick={onDone}>
          Skip to findings
        </button>
      </div>
    </section>
  )
}
