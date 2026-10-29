import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MetricFamily, OverviewResponse } from '../../backend/contracts/types'
import { api } from '../../backend/services'
import { TrendChart } from '../../components/TrendChart'
import { FamilyChip, ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { SectionError, SectionLoading } from '../../components/ui/SectionState'
import { useLinkState } from '../../hooks/useOrigin'
import { useQuery } from '../../hooks/useQuery'

interface TrendExplorerProps {
  overview: OverviewResponse
  family: MetricFamily | null
}

interface SeriesOption {
  id: string
  family: MetricFamily
}

const GROUPS: Array<{ family: MetricFamily; label: string }> = [
  { family: 'technology_risk', label: 'Technology Risk · synthetic' },
  { family: 'data_quality', label: 'Data Quality · workbook' },
]

/** One control at a time. Never an aggregate of the portfolio. */
export function TrendExplorer({ overview, family }: TrendExplorerProps) {
  const linkState = useLinkState('Triage')
  const options: SeriesOption[] = [
    ...overview.investigations.map((item) => ({ id: item.metricId, family: 'technology_risk' as const })),
    ...overview.dataQuality.stories.map((story) => ({ id: story.id, family: 'data_quality' as const })),
  ].filter((option) => !family || option.family === family)
  const [chosen, setChosen] = useState<string | null>(null)
  const selected = options.find((option) => option.id === chosen) ?? options[0]
  const detail = useQuery('overview-series', selected?.id ?? '', () => api.getMetric(selected?.id ?? ''))
  if (!selected) return null
  const data = detail.data
  const events =
    selected.family === 'data_quality'
      ? overview.dataQuality.events
          .filter((event) => event.controlId === selected.id)
          .map((event) => ({ id: event.id, date: event.date, label: `${event.type}: ${event.description}` }))
      : []

  return (
    <section className="card trend-explorer" aria-labelledby="trend-explorer-title" aria-busy={detail.refreshing}>
      <div className="card-head">
        <h2 id="trend-explorer-title">Trend explorer</h2>
        <span className="fine">One control at a time</span>
      </div>
      <p className="fine">Each line is a single metric or control, not a portfolio total. Technology Risk and Data Quality are never combined.</p>

      <div className="series-picker" role="group" aria-label="Choose a series">
        {GROUPS.map((group) => {
          const inGroup = options.filter((option) => option.family === group.family)
          if (!inGroup.length) return null
          return (
            <div key={group.family} className={`series-group group-${group.family}`}>
              <span className="series-group-label">{group.label}</span>
              <div className="series-chips">
                {inGroup.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className={`series-chip${option.id === selected.id ? ' is-selected' : ''}`}
                    aria-pressed={option.id === selected.id}
                    onClick={() => setChosen(option.id)}
                  >
                    {option.id}
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {data ? (
        <>
          <div className="series-head">
            <p className="series-name">
              <Link to={`/metrics/${data.metric.id}`} state={linkState}>
                <span className="mono">{data.metric.id}</span> {data.metric.name}
              </Link>
            </p>
            <div className="chip-row">
              <FamilyChip family={data.family} />
              <ProvenanceChip kind={data.family === 'data_quality' ? 'workbook' : 'synthetic'} />
            </div>
          </div>
          <TrendChart
            compact
            points={data.trend}
            unit={data.metric.unit}
            thresholds={data.metric.thresholds}
            breachDate={data.reading.breachedOn}
            caption={data.trendCaption}
            family={data.family}
            frequency={data.metric.frequency}
            events={events}
          />
        </>
      ) : detail.error ? (
        <SectionError message={detail.error.message} onRetry={detail.retry} />
      ) : (
        <SectionLoading label="Loading series" />
      )}
    </section>
  )
}
