import type { MetricFamily } from '../../backend/contracts/types'

export type Provenance = 'synthetic' | 'workbook' | 'proposed' | 'simulated'

export const WORKBOOK_STAMP = 'Workbook snapshot'

const PROVENANCE_LABEL: Record<Provenance, string> = {
  synthetic: 'Synthetic scenario',
  workbook: WORKBOOK_STAMP,
  proposed: 'Proposed — not built',
  simulated: 'Simulated analysis',
}

export function provenanceOf(family: MetricFamily): Provenance {
  return family === 'data_quality' ? 'workbook' : 'synthetic'
}

/** The whole demo is synthetic, so the generic "Synthetic scenario" / "Workbook snapshot" pills are intentionally not rendered. */
function isGenericSourcePill(kind: Provenance, label?: string) {
  if (kind !== 'synthetic' && kind !== 'workbook') return false
  return !label || label.startsWith('Workbook snapshot') || label.startsWith('Synthetic scenario')
}

export function ProvenanceChip({ kind, label }: { kind: Provenance; label?: string }) {
  if (isGenericSourcePill(kind, label)) return null
  return (
    <span className={`prov prov-${kind}`}>
      {kind === 'simulated' && (
        <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
          <circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" strokeWidth="1.3" />
          <path d="M6 3v3.2l2 1.3" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
      )}
      {label ?? PROVENANCE_LABEL[kind]}
    </span>
  )
}

export function FamilyChip({ family }: { family: MetricFamily }) {
  return <span className={`family-chip family-${family}`}>{family === 'data_quality' ? 'Data Quality' : 'Technology Risk'}</span>
}

export type Evidence = 'established' | 'fact' | 'hypothesis' | 'not_supplied' | 'recommendation' | 'workbook' | 'linked'

const EVIDENCE_LABEL: Record<Evidence, string> = {
  established: 'Established',
  fact: 'Scenario fact',
  hypothesis: 'Hypothesis',
  not_supplied: 'Not supplied',
  recommendation: 'Illustrative recommendation',
  workbook: 'Workbook result',
  linked: 'Linked by control ID, not causal',
}

export function EvidenceTag({ kind, label }: { kind: Evidence; label?: string }) {
  return <span className={`etag etag-${kind}`}>{label ?? EVIDENCE_LABEL[kind]}</span>
}
