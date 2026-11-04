import type { ReactNode } from 'react'

export function PageHeader({
  title,
  subtitle,
  eyebrow,
  crumbs,
  chips,
  actions,
  children,
}: {
  title: ReactNode
  subtitle?: ReactNode
  eyebrow?: ReactNode
  crumbs?: ReactNode
  chips?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <header className="page-header">
      {crumbs}
      <div className="page-header-row">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h1>{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
          {chips && <div className="row">{chips}</div>}
        </div>
        {actions && <div className="row">{actions}</div>}
      </div>
      {children}
    </header>
  )
}
