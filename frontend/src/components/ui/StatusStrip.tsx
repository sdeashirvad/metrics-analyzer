import { Link } from 'react-router-dom'
import type { RagStatus } from '../../backend/contracts/types'
import { statusLabel } from '../../domain/format'

export interface StripSegment {
  status: RagStatus
  count: number
  to?: string
}

const ORDER: RagStatus[] = ['red', 'amber', 'green', 'insufficient_data']

export function StatusStrip({ segments, label, size = 'md' }: { segments: StripSegment[]; label: string; size?: 'md' | 'sm' }) {
  const visible = ORDER.map((status) => segments.find((item) => item.status === status)).filter(
    (item): item is StripSegment => Boolean(item && item.count > 0),
  )
  const total = visible.reduce((sum, item) => sum + item.count, 0)
  const summary = visible.map((item) => `${item.count} ${statusLabel(item.status).toLowerCase()}`).join(', ')
  return (
    <div className={`strip strip-${size}`} role="group" aria-label={`${label}: ${summary}`}>
      {visible.map((item) => {
        const style = { flexGrow: item.count, flexBasis: 0 }
        const text = `${item.count} ${statusLabel(item.status)}`
        return item.to ? (
          <Link key={item.status} to={item.to} className={`strip-seg seg-${item.status}`} style={style} aria-label={`${label}: ${text}`} title={text}>
            {size === 'md' && total > 0 && <span className="num">{item.count}</span>}
          </Link>
        ) : (
          <span key={item.status} className={`strip-seg seg-${item.status}`} style={style} title={text}>
            {size === 'md' && total > 0 && <span className="num">{item.count}</span>}
          </span>
        )
      })}
    </div>
  )
}
