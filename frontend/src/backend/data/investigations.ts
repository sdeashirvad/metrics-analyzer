import type { Investigation } from '../contracts/types'
import { PATH_DISCLAIMER, SUMMARY_DISCLAIMER } from '../contracts/types'
import { M004_AMBER_NOTE } from './metrics'

export type InvestigationRecord = Omit<Investigation, 'orgContribution' | 'validationNote'>

const readingProvenance = 'Illustrative synthetic'
const factProvenance = 'Scenario fact'
const unconfirmedProvenance = 'Illustrative — not a confirmed event'

export const investigationRecords: Record<string, InvestigationRecord> = {
  M001: {
    metricId: 'M001',
    headline:
      'Critical patching is below the amber line, with the illustrative gap concentrated in Equities Technology.',
    summary: {
      disclaimer: SUMMARY_DISCLAIMER,
      text: 'Critical Patch Compliance is the percentage of in-scope critical assets with required critical patches applied within the control window (provisional definition, pending validation). The illustrative reading is 90.4% as of 27 October 2026. Green is 98% and amber is 95%; higher is better. The result is red because 90.4% is below 95%. The supplied scenario states that the metric went red on 14 October. For CTL-VM-01, critical-asset patching is below the control’s amber threshold. Owner function on the illustrative register is Technology Risk.',
    },
    whatChanged:
      'The illustrative series is 90.4% on 27 October, below the 95% amber threshold. The supplied scenario states the metric went red on 14 October. Earlier points on the chart are illustrative.',
    whyItMatters:
      'CTL-VM-01 expects critical assets to stay at or above 98% (green) and treats a fall through 95% as red. A reading of 90.4% means the control is outside its amber limit. The illustrative gap is concentrated in Equities Technology.',
    timelineNote:
      'Dated readings on this page are illustrative synthetic values. The red breach on 14 October and the two related signals are supplied scenario facts. Signal dates were not supplied.',
    timeline: [
      {
        date: '2026-10-10',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative reading 98.1% (green). Not a SMARTS result.',
      },
      {
        date: '2026-10-13',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative reading 95.6% (amber). Synthetic path only.',
      },
      {
        date: '2026-10-14',
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Went red. Supplied scenario date. The illustrative reading on this date is 93.8%.',
      },
      {
        date: '2026-10-27',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative current reading 90.4% (red).',
      },
      {
        date: null,
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Related signal: a patch freeze. Timing was not supplied.',
      },
      {
        date: null,
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Related signal: a failed patching-agent rollout. Timing was not supplied.',
      },
    ],
    signals: [
      {
        id: 'M001-breach',
        classification: 'scenario_fact',
        title: 'Red breach on 14 October',
        statement: 'The supplied scenario states Critical Patch Compliance went red on 14 October.',
        evidenceNote:
          'Supplied scenario statement only. The illustrative reading on that date is 93.8%, which is synthetic.',
        gaps: ['The SMARTS series is not connected. The 93.8% figure is not an operational extract.'],
      },
      {
        id: 'M001-freeze',
        classification: 'scenario_fact',
        title: 'Patch freeze',
        statement: 'The supplied scenario names a patch freeze as a related signal.',
        evidenceNote: 'Named in the scenario. No record id, scope, system of record, or dates were supplied.',
        gaps: [
          'Freeze scope, whether it covers Equities Technology, and whether it was in force on 14 October are unvalidated.',
        ],
      },
      {
        id: 'M001-agent',
        classification: 'scenario_fact',
        title: 'Failed patching-agent rollout',
        statement: 'The supplied scenario names a failed patching-agent rollout as a related signal.',
        evidenceNote: 'Named in the scenario. Population, error rates, and a deployment id were not supplied.',
        gaps: ['Affected estate, timing, and whether the rollout is still failing are unvalidated.'],
      },
      {
        id: 'M001-hypothesis',
        classification: 'hypothesis',
        title: 'Equities Technology concentration',
        statement:
          'The freeze and the failed rollout are a plausible explanation for the drop, concentrated in Equities Technology. This is a hypothesis. The signal dates were not supplied, so timing is not established.',
        evidenceNote:
          'Equities Technology is the hotspot named in the scenario. The organizational percentages are illustrative.',
        gaps: [
          'Join of freeze and agent telemetry to the metric.',
          'Confirmation that SMARTS can produce a metric-by-organization breakdown.',
        ],
      },
    ],
    lineage: [
      { label: 'Breach date', detail: 'Supplied scenario. Red on 14 October 2026.' },
      { label: 'Readings and chart', detail: 'Illustrative synthetic series. Not a SMARTS extract.' },
      { label: 'Patch freeze and agent rollout', detail: 'Supplied scenario signals. Dates and record ids were not supplied.' },
      { label: 'Organizational split', detail: 'Illustrative weights and rates. Hotspot name is from the scenario.' },
      { label: 'Owner function', detail: 'Technology Risk, from the supplied illustrative register.' },
      { label: 'Control statement', detail: 'Not supplied.' },
    ],
    pathToGreen: {
      disclaimer: PATH_DISCLAIMER,
      checks: [
        'Confirm whether a patch freeze was in force, which assets it covered, and whether Equities Technology was inside that scope. The scenario names the freeze and does not give dates or a record id.',
        'Confirm the patching-agent rollout failure: affected estate, start, and whether it is still failing.',
        'Validate the illustrative organizational split against a SMARTS metric-by-organization extract. Whether that extract exists is still to be verified.',
      ],
      possibleActions: [
        'Restore patching-agent coverage on the affected estate before treating the compliance gap as closed.',
        'Re-read critical patch compliance after any freeze exception is lifted. This chart is not evidence of a return to green.',
      ],
    },
  },
  M003: {
    metricId: 'M003',
    headline:
      'Aged critical vulnerabilities are above the amber limit; the illustrative count is concentrated in Infrastructure Services.',
    summary: {
      disclaimer: SUMMARY_DISCLAIMER,
      text: 'Critical Vulnerabilities older than 30 days is the count of critical vulnerabilities unresolved beyond that age (provisional definition, pending validation). The illustrative reading is 41 as of 27 October 2026. Green is 10 and amber is 25; lower is better. The result is red because 41 is above 25. The supplied scenario states that the metric went red on 16 October. For CTL-VM-02, the aged critical backlog is above the control’s amber limit. Owner function on the illustrative register is Technology Risk.',
    },
    whatChanged:
      'The illustrative count is 41 on 27 October, above the amber threshold of 25. The supplied scenario states the metric went red on 16 October.',
    whyItMatters:
      'CTL-VM-02 is a lower-is-better control. An aged critical backlog of 41 is above the amber limit of 25. The illustrative count is concentrated in Infrastructure Services (24 of 41).',
    timelineNote:
      'Dated readings on this page are illustrative synthetic values. The red breach on 16 October, the vendor advisory, and the three vacant roles are supplied scenario facts. Signal dates were not supplied.',
    timeline: [
      {
        date: '2026-10-12',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative reading 12 (amber). Not a SMARTS result.',
      },
      {
        date: '2026-10-16',
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Went red. Supplied scenario date. The illustrative reading on this date is 27.',
      },
      {
        date: '2026-10-27',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative current reading 41 (red).',
      },
      {
        date: null,
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Related signal: a vendor advisory for which no fix is available yet. Timing and advisory id were not supplied.',
      },
      {
        date: null,
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Related signal: three vacant roles. Team, dates, and location were not supplied.',
      },
    ],
    signals: [
      {
        id: 'M003-breach',
        classification: 'scenario_fact',
        title: 'Red breach on 16 October',
        statement: 'The supplied scenario states this metric went red on 16 October.',
        evidenceNote: 'Supplied scenario statement only. The illustrative count of 27 on that date is synthetic.',
        gaps: ['The SMARTS series is not connected.'],
      },
      {
        id: 'M003-advisory',
        classification: 'scenario_fact',
        title: 'Vendor advisory with no fix yet',
        statement: 'The supplied scenario names a vendor advisory for which no fix is available yet.',
        evidenceNote: 'Named in the scenario. No advisory id and no mapping from the advisory to the aged count were supplied.',
        gaps: ['Which of the illustrative 41 items match that advisory is unvalidated.'],
      },
      {
        id: 'M003-roles',
        classification: 'scenario_fact',
        title: 'Three vacant roles',
        statement: 'The supplied scenario names three vacant roles as a related signal.',
        evidenceNote: 'Named in the scenario. The roles, the team, and the dates were not supplied.',
        gaps: ['Whether the vacancies sit in Infrastructure Services is unvalidated.'],
      },
      {
        id: 'M003-hypothesis',
        classification: 'hypothesis',
        title: 'Infrastructure Services concentration',
        statement:
          'The Infrastructure Services concentration may reflect the no-fix advisory plus a capacity gap. This is a hypothesis. The 24 illustrative items are not confirmed to be the advisory’s vulnerabilities, and the vacancies are not confirmed to sit in that group.',
        evidenceNote:
          'Infrastructure Services is the hotspot named in the scenario. The 24 / 41 split is illustrative.',
        gaps: [
          'CVE-to-count mapping.',
          'Role location.',
          'Confirmation that SMARTS can produce a metric-by-organization breakdown.',
        ],
      },
    ],
    lineage: [
      { label: 'Breach date', detail: 'Supplied scenario. Red on 16 October 2026.' },
      { label: 'Readings and chart', detail: 'Illustrative synthetic series. Not a SMARTS extract.' },
      { label: 'Advisory and vacancies', detail: 'Supplied scenario signals. Ids, dates, and team location were not supplied.' },
      { label: 'Organizational split', detail: 'Illustrative counts. Hotspot name is from the scenario.' },
      { label: 'Owner function', detail: 'Technology Risk, from the supplied illustrative register.' },
      { label: 'Control statement', detail: 'Not supplied.' },
    ],
    pathToGreen: {
      disclaimer: PATH_DISCLAIMER,
      checks: [
        'Identify whether the aged critical vulnerabilities match the vendor advisory that has no fix yet.',
        'Confirm the three vacant roles and whether they sit in Infrastructure Services vulnerability handling.',
        'Separate items aged because no fix exists from items aged for other reasons.',
      ],
      possibleActions: [
        'Track any accepted exposure through the real control process. This demo does not record a risk acceptance.',
        'Treat the capacity gap as a hypothesis until the vacancies are tied to this backlog.',
      ],
    },
  },
  M007: {
    metricId: 'M007',
    headline:
      'Weekly change failure is above 10%. A Payments release with rollbacks is the named signal. No organizational breakdown is available.',
    summary: {
      disclaimer: SUMMARY_DISCLAIMER,
      text: 'Change Failure Rate is the percentage of changes that failed, were rolled back, or required emergency remediation (provisional definition, pending validation). The illustrative reading for the week ending 25 October 2026 is 14.1%, and the week ending 18 October is 12.6%. Green is 5% and amber is 10%; lower is better. The result is red because the rate is above 10%. The supplied scenario states that the metric went red on 18 October. For CTL-CM-02, failed change is above the control tolerance. Owner function on the illustrative register is Technology Risk.',
    },
    whatChanged:
      'The illustrative weekly rate is 14.1% for the week ending 25 October, and 12.6% for the week ending 18 October. Both are above the 10% amber threshold. The supplied scenario states the metric went red on 18 October.',
    whyItMatters:
      'CTL-CM-02 treats change failure above 10% as red. The named signal is a Payments release associated with rollbacks. That release is a change signal, not an organizational hotspot. No group breakdown was supplied.',
    timelineNote:
      'Weekly points are illustrative synthetic values. The red breach on 18 October and the Payments release are supplied scenario facts. The release date and change id were not supplied. Organizational contribution was not supplied.',
    timeline: [
      {
        date: '2026-10-11',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative week-ending reading 8.7% (amber). Not a SMARTS result.',
      },
      {
        date: '2026-10-18',
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Went red. Supplied scenario date. The illustrative week-ending reading is 12.6%.',
      },
      {
        date: '2026-10-25',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative current week-ending reading 14.1% (red).',
      },
      {
        date: null,
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Related signal: a Payments release associated with rollbacks. This is not an organizational breakdown. Release id and date were not supplied.',
      },
    ],
    signals: [
      {
        id: 'M007-breach',
        classification: 'scenario_fact',
        title: 'Red breach on 18 October',
        statement: 'The supplied scenario states Change Failure Rate went red on 18 October.',
        evidenceNote: 'Supplied scenario statement only. The illustrative 12.6% week-ending value is synthetic.',
        gaps: ['The SMARTS series is not connected. Numerator and denominator were not supplied.'],
      },
      {
        id: 'M007-release',
        classification: 'scenario_fact',
        title: 'Payments release associated with rollbacks',
        statement:
          'The supplied scenario names a Payments release associated with rollbacks. This is a change signal. It is not an organizational contribution.',
        evidenceNote: 'Named in the scenario. No change id, rollback count, or release date was supplied.',
        gaps: ['The release record and the share of the weekly rate it explains are unvalidated.'],
      },
      {
        id: 'M007-hypothesis',
        classification: 'hypothesis',
        title: 'One release may explain the weekly breach',
        statement:
          'That Payments release may be large enough to move the weekly rate through 10%. This is a hypothesis. Other changes in the same week are unknown, so causation is not established.',
        evidenceNote: 'The only related signal in the scenario is the Payments release. No other failure was named.',
        gaps: [
          'Change id, failure count, and weekly denominator.',
          'Whether other changes failed in the same week.',
          'A join from change records to this metric, which is still to be verified.',
        ],
      },
    ],
    lineage: [
      { label: 'Breach date', detail: 'Supplied scenario. Red on 18 October 2026.' },
      { label: 'Readings and chart', detail: 'Illustrative synthetic weekly series. Not a SMARTS extract.' },
      { label: 'Payments release', detail: 'Supplied scenario signal. Not an organizational breakdown. Id and date were not supplied.' },
      { label: 'Organizational split', detail: 'Not supplied. No group chart is shown for M007.' },
      { label: 'Owner function', detail: 'Technology Risk, from the supplied illustrative register.' },
      { label: 'Control statement', detail: 'Not supplied.' },
    ],
    pathToGreen: {
      disclaimer: PATH_DISCLAIMER,
      checks: [
        'Obtain the Payments release identity and its rollback count. No change id was supplied.',
        'Check whether other changes in the same week also failed.',
        'Join change records to the metric. That join is a Monday verification item, not a completed analysis.',
      ],
      possibleActions: [
        'If one release dominates the weekly rate, containment is release-specific.',
        'If other changes also failed, the week reflects a broader change-quality issue. That fork is unresolved.',
      ],
    },
  },
  M004: {
    metricId: 'M004',
    headline:
      'Backup success moved through amber and is red as of 22 October, alongside a degraded storage-array incident. No organizational breakdown is available.',
    summary: {
      disclaimer: SUMMARY_DISCLAIMER,
      text: 'Backup Success Rate is the percentage of scheduled backup jobs that completed successfully (provisional definition, pending validation). The illustrative reading is 97.0% as of 27 October 2026. Green is 99.5% and amber is 98%; higher is better. The result is red because 97.0% is below 98%. The supplied scenario states that the metric went amber and then red on 22 October. It does not state the date the series first entered amber. Any earlier amber point is illustrative and is not a confirmed historical event. For CTL-RS-03, backup reliability is below the control’s amber line. Owner function on the illustrative register is Technology Risk.',
    },
    whatChanged:
      'The illustrative reading is 97.0% on 27 October, below the 98% amber threshold. The supplied scenario states the metric went amber and then red on 22 October. The chart’s earlier amber points are synthetic. They are not the confirmed date the metric first entered amber.',
    whyItMatters:
      'CTL-RS-03 expects backup success at or above 99.5% (green). A reading below 98% is red. A degraded storage-array incident is the named signal. No organizational breakdown was supplied.',
    timelineNote: M004_AMBER_NOTE,
    timeline: [
      {
        date: '2026-10-18',
        kind: 'illustrative_reading',
        provenanceLabel: unconfirmedProvenance,
        label:
          'Illustrative synthetic amber point, 99.2%. Not a confirmed historical event. The date the metric first entered amber was not supplied.',
      },
      {
        date: '2026-10-21',
        kind: 'illustrative_reading',
        provenanceLabel: unconfirmedProvenance,
        label:
          'Illustrative synthetic amber point, 98.2%. Not a confirmed historical event. This date is not the established start of the amber period.',
      },
      {
        date: '2026-10-22',
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label:
          'Went red on 22 October, after an amber period. Supplied scenario fact. The first amber date was not supplied. The illustrative reading on this date is 97.6%.',
      },
      {
        date: '2026-10-27',
        kind: 'illustrative_reading',
        provenanceLabel: readingProvenance,
        label: 'Illustrative current reading 97.0% (red).',
      },
      {
        date: null,
        kind: 'scenario_fact',
        provenanceLabel: factProvenance,
        label: 'Related signal: a degraded storage-array incident. Incident id and timing were not supplied.',
      },
    ],
    signals: [
      {
        id: 'M004-breach',
        classification: 'scenario_fact',
        title: 'Amber, then red on 22 October',
        statement:
          'The supplied scenario states Backup Success went amber and then red on 22 October. It does not state the date the metric first entered amber.',
        evidenceNote:
          'Supplied scenario statement for the 22 October red breach and for the existence of an earlier amber period. The illustrative 97.6% reading is synthetic.',
        gaps: [
          'The first amber date was not supplied.',
          'Amber points before 22 October in the chart are not confirmed historical events.',
        ],
      },
      {
        id: 'M004-array',
        classification: 'scenario_fact',
        title: 'Degraded storage-array incident',
        statement: 'The supplied scenario names a degraded storage-array incident as a related signal.',
        evidenceNote: 'Named in the scenario. No incident id, job list, or incident window was supplied.',
        gaps: ['Overlap between the incident and the 22 October breach is unvalidated.'],
      },
      {
        id: 'M004-hypothesis',
        classification: 'hypothesis',
        title: 'Array degradation may explain the failed backups',
        statement:
          'Array degradation may have caused the backup jobs to fail. This is a hypothesis. The illustrative amber points before 22 October are not evidence of when degradation started.',
        evidenceNote: 'The scenario places the incident alongside the amber-then-red path. It does not prove the join.',
        gaps: [
          'Incident id and failed job list.',
          'Whether the incident window covers 22 October.',
          'A later reading after restoration. None is in this demo.',
        ],
      },
    ],
    lineage: [
      { label: 'Red breach', detail: 'Supplied scenario. Red on 22 October 2026, after an amber period.' },
      { label: 'First amber date', detail: 'Not supplied. Not a confirmed historical event.' },
      {
        label: 'Amber points before 22 October',
        detail: 'Illustrative synthetic values. They are not confirmed historical events.',
      },
      { label: 'Current reading and chart', detail: 'Illustrative synthetic series. Not a SMARTS extract.' },
      { label: 'Storage-array incident', detail: 'Supplied scenario signal. Id and timing were not supplied.' },
      { label: 'Organizational split', detail: 'Not supplied. No group chart is shown for M004.' },
      { label: 'Owner function', detail: 'Technology Risk, from the supplied illustrative register.' },
      { label: 'Control statement', detail: 'Not supplied.' },
    ],
    pathToGreen: {
      disclaimer: PATH_DISCLAIMER,
      checks: [
        'Obtain the storage-array incident record and the backup jobs that failed. No incident id was supplied.',
        'Compare the incident window with 22 October. The scenario does not date the incident, and it does not date the first amber reading.',
        'Do not treat illustrative amber points before 22 October as the incident start or as the date amber began.',
      ],
      possibleActions: [
        'Restore the array and rerun the failed jobs, then reassess the control from a later reading.',
        'Keep the organizational view closed until a breakdown is actually supplied.',
      ],
    },
  },
}
