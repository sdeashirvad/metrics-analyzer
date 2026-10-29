import type { OrgGroup, Unit } from '../backend/contracts/types'
import { formatNumber } from '../domain/format'
import { StatusBadge } from './StatusBadge'

interface HotspotChartProps {
  groups: OrgGroup[]
  unit: Unit
  shareLabel: string
}

export function HotspotChart({ groups, unit, shareLabel }: HotspotChartProps) {
  return (
    <ul className="hot-list">
      {groups.map((group) => (
        <li key={group.name} className={group.hotspot ? 'hot-row is-hotspot' : 'hot-row'}>
          <div className="hot-name">
            <span>{group.name}</span>
            {group.hotspot && <span className="etag etag-fact">Scenario hotspot</span>}
            <StatusBadge status={group.status} />
          </div>
          <div className="hot-track" aria-hidden="true">
            <span style={{ width: `${group.shareOfGapPercent}%` }} />
          </div>
          <div className="hot-meta">
            {formatNumber(group.value, unit)}
            {group.weightPercent != null ? ` · ${group.weightPercent}% of illustrative assets` : ''}
            {' · '}
            {group.shareOfGapPercent.toFixed(1)}% {shareLabel}
          </div>
        </li>
      ))}
    </ul>
  )
}
