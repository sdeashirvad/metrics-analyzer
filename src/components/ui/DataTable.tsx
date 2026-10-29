import type { ReactNode } from 'react'
import { RefreshLine } from './SectionState'

interface DataTableProps {
  caption: string
  head: ReactNode
  children: ReactNode
  refreshing?: boolean
  minWidth?: number
  className?: string
}

export function DataTable({ caption, head, children, refreshing = false, minWidth, className }: DataTableProps) {
  return (
    <div className={`table-shell${className ? ` ${className}` : ''}`} aria-busy={refreshing}>
      <RefreshLine active={refreshing} />
      <div className="table-wrap">
        <table className="data-table" style={minWidth ? { minWidth } : undefined}>
          <caption className="sr-only">{caption}</caption>
          <thead>{head}</thead>
          <tbody>{children}</tbody>
        </table>
      </div>
    </div>
  )
}
