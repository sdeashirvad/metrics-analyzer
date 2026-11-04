import type { ComplianceRowCounts, TestRowCounts } from '../../api/types'
import { formatInt } from '../../format'

type TestingCounts = TestRowCounts & { pass: number; fail: number; resultNotRecorded: number }

export function MetricFunnel({ compliance, testing }: { compliance: ComplianceRowCounts; testing: TestingCounts }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Status and testing</h2>
      </div>
      <p className="fine">Each block is metric rows for this month. These counts are not application counts.</p>
      <div className="grid g3">
        <ShareBlocks
          label="Compliance status"
          items={[
            { key: 'compliant', label: 'Compliant', value: compliance.compliant, tone: 'tone-green' },
            { key: 'non', label: 'Non-compliant', value: compliance.nonCompliant, tone: 'tone-red' },
            { key: 'pending', label: 'Pending', value: compliance.pending, tone: 'tone-amber' },
            { key: 'na', label: 'Not applicable', value: compliance.notApplicable, tone: 'tone-na' },
          ]}
        />
        <ShareBlocks
          label="Test status"
          items={[
            { key: 'complete', label: 'Test complete', value: testing.complete, tone: 'tone-green' },
            { key: 'pending', label: 'Test pending', value: testing.pending, tone: 'tone-amber' },
            { key: 'none', label: 'No test', value: testing.none, tone: 'tone-na' },
            { key: 'exempt', label: 'Exempt', value: testing.exempt, tone: 'tone-na' },
          ]}
        />
        <ShareBlocks
          label="Completed test result"
          items={[
            { key: 'pass', label: 'Pass', value: testing.pass, tone: 'tone-green' },
            { key: 'fail', label: 'Fail', value: testing.fail, tone: 'tone-red' },
            { key: 'missing', label: 'Not recorded', value: testing.resultNotRecorded, tone: 'tone-na' },
          ]}
        />
      </div>
    </section>
  )
}

function ShareBlocks({ label, items }: { label: string; items: Array<{ key: string; label: string; value: number; tone: string }> }) {
  const total = items.reduce((sum, item) => sum + item.value, 0)
  return (
    <div className="stack">
      <p className="fine">{label}</p>
      {total <= 0 ? (
        <p className="fine">No metric rows in this scope.</p>
      ) : (
        <div className="share-bar">
          {items
            .filter((item) => item.value > 0)
            .map((item) => (
              <div key={item.key} className={item.tone} style={{ flexGrow: item.value }}>
                <span>{item.label}</span>
                <span className="num">{formatInt(item.value)}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
