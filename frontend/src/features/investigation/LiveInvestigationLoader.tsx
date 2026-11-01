import { useEffect, useState } from 'react'
import type { EtaEstimate } from '../../state/etaStore'

const PHASES = [
  'Reading the stored Data Quality facts from Snowflake',
  'Drafting findings from those facts',
  'Checking every cited figure against the retrieved evidence',
  'Saving a result that can be shown again',
]

export function LiveInvestigationLoader({ startedAt, estimate }: { startedAt: number; estimate: EtaEstimate | null }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(timer)
  }, [])

  const elapsed = Math.max(0, now - startedAt)
  const phaseMs = estimate ? Math.max(3000, Math.round((estimate.median * 1000) / PHASES.length)) : 4000
  const sequenceMs = phaseMs * PHASES.length
  const extended = elapsed >= sequenceMs
  const index = Math.min(PHASES.length - 1, Math.floor(elapsed / phaseMs))
  const overdue = estimate ? elapsed > estimate.high * 1000 : elapsed > 30_000
  const seconds = Math.floor(elapsed / 1000)
  const headline = extended
    ? overdue
      ? 'Taking longer than usual. Still working.'
      : 'Still working'
    : PHASES[index]
  const note = extended
    ? 'Results are checked against Snowflake facts before they are shown.'
    : 'What happens in each run. These steps describe the pipeline. They are not a live feed from the agent.'

  return (
    <section className={`card analysis${extended ? ' is-waiting' : ''}`} aria-live="polite">
      <p className="eyebrow">Investigation in progress</p>
      <h2>{headline}</h2>
      <p className="fine">{note}</p>
      <p className="fine num">
        Elapsed {seconds}s{estimate ? ` · ${estimate.label}` : ''}
      </p>
      <div className="analysis-track" aria-hidden="true">
        <span className={extended ? 'is-loop' : ''} style={extended ? undefined : { animationDuration: `${phaseMs}ms` }} key={extended ? 'wait' : index} />
      </div>
      <ol className="stages">
        {PHASES.slice(0, extended ? PHASES.length - 1 : index).map((label) => (
          <li key={label} className="is-done">
            {label}
          </li>
        ))}
      </ol>
    </section>
  )
}

export function CacheCheckLoader() {
  return (
    <section className="card analysis" aria-live="polite">
      <p className="eyebrow">Saved investigation</p>
      <h2>Checking for a saved investigation</h2>
      <p className="fine">This looks up a completed result. It does not start a new one.</p>
      <div className="analysis-track" aria-hidden="true">
        <span className="is-loop" />
      </div>
    </section>
  )
}

export function AwaitingAcceptanceLoader() {
  return (
    <section className="card analysis" aria-live="polite">
      <p className="eyebrow">Investigation</p>
      <h2>Sending the investigation</h2>
      <p className="fine">A new run starts only after the service accepts it.</p>
      <div className="analysis-track" aria-hidden="true">
        <span className="is-loop" />
      </div>
    </section>
  )
}

export function CachedRetrievalLoader() {
  return (
    <section className="card analysis is-cached-load" aria-live="polite">
      <p className="eyebrow">Saved investigation</p>
      <h2>Retrieving the saved investigation</h2>
      <p className="fine">This opens the completed result. It does not start a new one.</p>
      <div className="analysis-track" aria-hidden="true">
        <span className="is-loop" />
      </div>
    </section>
  )
}
