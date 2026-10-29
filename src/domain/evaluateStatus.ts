import type { Direction, RagStatus } from '../backend/contracts/types'

export const THRESHOLD_BOUNDARY_NOTE =
  'Inclusive boundaries are provisional and must be confirmed with the client.'

const STATUS_RANK: Record<RagStatus, number> = {
  red: 0,
  amber: 1,
  green: 2,
  insufficient_data: 3,
}

export function evaluateStatus(
  value: number | null,
  direction: Direction,
  thresholds: { green: number; amber: number },
): RagStatus {
  if (value == null || Number.isNaN(value)) return 'insufficient_data'
  if (direction === 'higher_is_better') {
    if (value >= thresholds.green) return 'green'
    if (value >= thresholds.amber) return 'amber'
    return 'red'
  }
  if (value <= thresholds.green) return 'green'
  if (value <= thresholds.amber) return 'amber'
  return 'red'
}

export function statusRank(status: RagStatus): number {
  return STATUS_RANK[status]
}

export function isRagStatus(value: string): value is RagStatus {
  return value === 'green' || value === 'amber' || value === 'red' || value === 'insufficient_data'
}
