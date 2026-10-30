import { Link, useLocation } from 'react-router-dom'

export function NotFoundPage() {
  const location = useLocation()
  return (
    <div className="page page-narrow">
      <section className="state-card">
        <p className="eyebrow">Not found</p>
        <h1>This page is not in the demo</h1>
        <p className="lede">
          <span className="mono">{location.pathname}</span> does not match a Metrics Analyzer route.
        </p>
        <div className="actions">
          <Link className="btn btn-primary" to="/dashboard">
            Go to Dashboard
          </Link>
          <Link className="btn" to="/metrics">
            Open the metric register
          </Link>
        </div>
      </section>
    </div>
  )
}
