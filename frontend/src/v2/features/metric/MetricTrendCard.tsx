import { getMetricTrend } from '../../api/portfolio'
import type { ScopeFilters } from '../../api/types'
import { LineChart, MonthMix } from '../../components/charts/Charts'
import { Card, Provisional, QueryPanel } from '../../components/present'
import { formatMonth } from '../../format'
import { useApiQuery } from '../../hooks/useApiQuery'
import { scopeKey } from '../../scopePath'
import { Skeleton } from '../../components/Skeleton'

export function MetricTrendCard({ metricId, filters }: { metricId: string; filters: ScopeFilters }) {
  const query = useApiQuery('metric-trend', `${metricId}|${scopeKey(filters)}`, () => getMetricTrend(metricId, filters), { keep: metricId })
  return (
    <Card title="Rate over time">
      <p className="fine">
        <Provisional id="PD-01" of="trend note" /> A gap is a month that was not observed. It is not shown as zero.
      </p>
      <QueryPanel query={query} skeleton={<Skeleton shape="chart" label="Loading the rate over time" />}>
        {(data) => {
          const missing = data.points.filter((point) => !point.observed)
          return (
            <>
              <LineChart
                points={data.points.map((point) =>
                  point.observed
                    ? { label: formatMonth(point.month), value: point.rate }
                    : { label: formatMonth(point.month), value: null, unobserved: true },
                )}
              />
              {data.points.some((point) => point.observed) && (
                <>
                  <p className="fine">Status mix by month · metric rows</p>
                  <MonthMix
                    columns={data.points.flatMap((point) =>
                      point.observed
                        ? [
                            {
                              label: formatMonth(point.month).replace(' 20', ' '),
                              segments: [
                                { key: 'Compliant', value: point.complianceRows.compliant },
                                { key: 'Non_Compliant', value: point.complianceRows.nonCompliant },
                                { key: 'Pending', value: point.complianceRows.pending },
                                { key: 'Not_Applicable', value: point.complianceRows.notApplicable },
                              ],
                            },
                          ]
                        : [],
                    )}
                  />
                </>
              )}
              {missing.length > 0 && (
                <ul className="list">
                  {missing.map((point) => (
                    <li key={point.month}>
                      <span className="grow">{formatMonth(point.month)}</span>
                      <span>Not observed</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )
        }}
      </QueryPanel>
    </Card>
  )
}
