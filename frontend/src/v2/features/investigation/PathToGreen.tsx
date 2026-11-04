import type { ApplicationMetricRow, MetricInvestigation, RagStatus } from '../../api/types'
import { Card, RagPill } from '../../components/present'
import { formatInt, formatPercent, formatPp, labelOf } from '../../format'

const TARGET = 'Compliant, test complete, and Pass. Pending and Not applicable are not green.'

export function MetricPath({ data }: { data: MetricInvestigation }) {
  const rate = data.observations.rate.rate
  const gap = rate == null ? null : Math.max(0, rate - 0.45)
  const testing = data.observations.testing
  const actions = [
    testing.fail > 0 ? `Review the ${formatInt(testing.fail)} failed tests. This is a proposal, not completed work.` : null,
    testing.none > 0 ? `Complete a test for the ${formatInt(testing.none)} rows with no test.` : null,
    ...data.derived.largestContributors.slice(0, 3).map(
      (item) =>
        `Look first at ${item.key} (${item.dimension === 'org' ? 'organisation' : 'legal entity'}): ${formatInt(item.nonCompliantApplications)} non-compliant applications.`,
    ),
  ].filter((item): item is string => Boolean(item))
  return (
    <Card title="Path to green">
      <p className="fine">Proposed remediation. Nothing here is recorded as done, and no owner is assigned.</p>
      <dl className="kv">
        <dt>Current</dt>
        <dd>
          <RagPill rag={data.observations.rag} /> <span className="num">{rate == null ? '—' : formatPercent(rate)}</span>
        </dd>
        <dt>Target</dt>
        <dd>Provisional healthy band: rate below 45%.</dd>
        <dt>Gap</dt>
        <dd>{gap == null ? 'No rate, so the gap is unclassified.' : gap === 0 ? 'Already inside the healthy band.' : `${formatPp(gap * 100)} above the healthy band.`}</dd>
      </dl>
      <p className="fine">
        What the data shows: {formatInt(data.observations.applications)} applications, movement{' '}
        {data.derived.movement ? `${formatInt(data.derived.movement.newlyNonCompliant)} newly non-compliant and ${formatInt(data.derived.movement.persistentNonCompliant)} persistent.` : 'is not available for this month.'}
      </p>
      <p className="fine">What is only a hypothesis: concentration in a group does not by itself prove why the rate moved.</p>
      {actions.length > 0 && (
        <ul className="list">
          {actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      )}
      <p className="fine">
        Next month, a successful change would show a lower provisional rate
        {data.derived.movement ? ` and fewer persistent non-compliant applications than ${formatInt(data.derived.movement.persistentNonCompliant)}.` : '.'}
      </p>
    </Card>
  )
}

export function ApplicationPath({ rows, ragHint }: { rows: ApplicationMetricRow[]; ragHint?: RagStatus }) {
  const failing = rows.filter((row) => !(row.complianceStatus === 'Compliant' && row.testStatus === 'Test_Complete' && row.testResult === 'Pass'))
  const pending = failing.filter((row) => row.complianceStatus === 'Pending' || row.complianceStatus === 'Not_Applicable')
  return (
    <Card title="Path to green">
      <p className="fine">Proposed remediation. Nothing here is recorded as done, and no owner is assigned.</p>
      <dl className="kv">
        <dt>Current</dt>
        <dd>
          {rows.length === 0 ? 'No metric rows.' : failing.length === 0 ? 'Every row meets the provisional target.' : `${formatInt(failing.length)} of ${formatInt(rows.length)} rows do not.`}
          {ragHint ? <> <RagPill rag={ragHint} /></> : null}
        </dd>
        <dt>Target</dt>
        <dd>{TARGET}</dd>
        <dt>Gap</dt>
        <dd>
          {failing.length === 0
            ? 'No gap on the rows in this month.'
            : failing
                .slice(0, 4)
                .map((row) => `${row.metricId}: ${labelOf(row.complianceStatus)}, ${labelOf(row.testStatus)}, ${row.testResult ? labelOf(row.testResult) : 'no result'}`)
                .join(' · ')}
        </dd>
      </dl>
      {pending.length > 0 && <p className="fine">{formatInt(pending.length)} pending or not-applicable rows stay out of green.</p>}
      {failing.length > 0 && (
        <ul className="list">
          <li>Bring each listed row to Compliant, with a completed test whose result is Pass.</li>
        </ul>
      )}
    </Card>
  )
}
