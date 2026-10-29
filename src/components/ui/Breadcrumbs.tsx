import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'

export interface Crumb {
  label: string
  to?: string
  state?: unknown
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      <ol>
        {items.map((item, index) => {
          const last = index === items.length - 1
          return (
            <li key={`${item.label}-${index}`}>
              {item.to && !last ? (
                <Link to={item.to} state={item.state} onClick={item.onClick}>
                  {item.label}
                </Link>
              ) : (
                <span aria-current={last ? 'page' : undefined}>{item.label}</span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
