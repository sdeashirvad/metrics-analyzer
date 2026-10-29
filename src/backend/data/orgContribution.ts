import type { OrgContribution, OrgGroup } from '../contracts/types'
import { evaluateStatus } from '../../domain/evaluateStatus'
import { metricById } from './metrics'

function groupsFor(
  metricId: string,
  rows: Array<{
    name: string
    weightPercent: number | null
    value: number
    shareOfGapPercent: number
    hotspot: boolean
  }>,
): OrgGroup[] {
  const metric = metricById.get(metricId)
  if (!metric) return []
  return rows.map((row) => ({
    ...row,
    status: evaluateStatus(row.value, metric.direction, metric.thresholds),
  }))
}

export const orgByMetricId: Record<string, OrgContribution> = {
  M001: {
    availability: 'available',
    origin: 'illustrative_synthetic',
    reason: 'Illustrative organizational contribution for the supplied Equities Technology hotspot.',
    methodNote:
      'Illustrative asset-weighted compliance, not a SMARTS extract. The portfolio reading of 90.4% is the weighted rate rounded to one decimal. Share of gap is the group’s share of the non-compliant mass; rounded shares are stored so they total 100. Equities Technology is the hotspot named in the supplied scenario.',
    shareLabel: 'of illustrative non-compliant mass',
    groups: groupsFor('M001', [
      { name: 'Equities Technology', weightPercent: 46, value: 81.8, shareOfGapPercent: 87.4, hotspot: true },
      { name: 'Markets Infrastructure', weightPercent: 15, value: 97.2, shareOfGapPercent: 4.4, hotspot: false },
      { name: 'Corporate Functions Technology', weightPercent: 13, value: 99, shareOfGapPercent: 1.3, hotspot: false },
      { name: 'Infrastructure Services', weightPercent: 16, value: 96.8, shareOfGapPercent: 5.3, hotspot: false },
      { name: 'Payments Technology', weightPercent: 10, value: 98.5, shareOfGapPercent: 1.6, hotspot: false },
    ]),
  },
  M003: {
    availability: 'available',
    origin: 'illustrative_synthetic',
    reason: 'Illustrative organizational contribution for the supplied Infrastructure Services hotspot.',
    methodNote:
      'Illustrative counts, not a SMARTS extract. Group counts sum to the portfolio reading of 41. Shares are each group’s portion of that total. Applying the portfolio thresholds to a group’s own count rates Infrastructure Services (24) as amber while the portfolio total (41) is red. The hotspot designation comes from the supplied scenario.',
    shareLabel: 'of illustrative total',
    groups: groupsFor('M003', [
      { name: 'Infrastructure Services', weightPercent: null, value: 24, shareOfGapPercent: 58.5, hotspot: true },
      { name: 'Equities Technology', weightPercent: null, value: 7, shareOfGapPercent: 17.1, hotspot: false },
      { name: 'Markets Infrastructure', weightPercent: null, value: 5, shareOfGapPercent: 12.2, hotspot: false },
      { name: 'Payments Technology', weightPercent: null, value: 3, shareOfGapPercent: 7.3, hotspot: false },
      { name: 'Corporate Functions Technology', weightPercent: null, value: 2, shareOfGapPercent: 4.9, hotspot: false },
    ]),
  },
}

export const hotspotCallouts = [
  {
    metricId: 'M001',
    group: 'Equities Technology',
    statement: 'Illustrative compliance 81.8%. Illustrative share of the non-compliant mass 87.4%.',
  },
  {
    metricId: 'M003',
    group: 'Infrastructure Services',
    statement: 'Illustrative count 24 of 41 aged critical vulnerabilities (58.5% of the total).',
  },
]
