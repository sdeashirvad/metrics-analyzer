import type { ReactNode } from 'react'
import type { MetricFamily } from '../../backend/contracts/types'

interface BookTileProps {
  family: MetricFamily
  title: string
  chip: ReactNode
  figure?: ReactNode
  figureLabel?: ReactNode
  aside?: ReactNode
  children?: ReactNode
  footnote?: ReactNode
  wide?: boolean
}

export function BookTile({ family, title, chip, figure, figureLabel, aside, children, footnote, wide = false }: BookTileProps) {
  return (
    <section className={`book-tile book-${family}${wide ? ' is-wide' : ''}`} aria-label={title}>
      <header className="book-tile-head">
        <h2>{title}</h2>
        {chip}
      </header>
      {figure != null && (
        <div className="book-figure-row">
          <div className="book-figure">
            <span className="hero-num num">{figure}</span>
            <span className="book-figure-label">{figureLabel}</span>
          </div>
          {aside && <div className="book-aside">{aside}</div>}
        </div>
      )}
      {children}
      {footnote && <p className="fine book-foot">{footnote}</p>}
    </section>
  )
}
