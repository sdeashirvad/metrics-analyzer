import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui/PageHeader'

export function NotFoundPage() {
  return (
    <div className="page">
      <PageHeader title="Page not found" subtitle="That address is not in Metrics Analyzer." />
      <Link className="btn" to="/">
        Dashboard
      </Link>
    </div>
  )
}
