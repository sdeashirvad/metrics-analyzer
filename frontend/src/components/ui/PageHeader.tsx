import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  eyebrow?: ReactNode
  crumbs?: ReactNode
  chips?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}

export function PageHeader({ title, subtitle, eyebrow, crumbs, chips, actions, children }: PageHeaderProps) {
  return (
    <header className="page-header">
      {crumbs}
      <div className="page-header-row">
        <div className="page-header-text">
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h1>{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
          {chips && <div className="row page-header-chips">{chips}</div>}
        </div>
        {actions && <div className="page-header-actions">{actions}</div>}
      </div>
      {children}
    </header>
  )
}
