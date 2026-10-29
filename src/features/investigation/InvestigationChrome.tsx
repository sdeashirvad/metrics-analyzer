import { Link } from 'react-router-dom'
import { Breadcrumbs, type Crumb } from '../../components/ui/Breadcrumbs'
import type { BackTarget } from '../../hooks/useOrigin'

export function InvestigationCrumbs({ back, metricId }: { back: BackTarget; metricId: string }) {
  const crumbs: Crumb[] = [{ label: back.label, to: back.to, state: back.state, onClick: back.go }]
  if (back.to.split('?')[0] !== `/metrics/${metricId}`) crumbs.push({ label: metricId, to: `/metrics/${metricId}` })
  return <Breadcrumbs items={[...crumbs, { label: 'Investigation' }]} />
}

export function BackButton({ back }: { back: BackTarget }) {
  return (
    <Link className="btn" to={back.to} state={back.state} onClick={back.go}>
      ← Back to {back.label}
    </Link>
  )
}
