export function ProvenanceChip({ kind, label }: { kind: string; label?: string }) {
  const text = label ?? (kind === 'proposed' ? 'Proposed' : 'In this release')
  return <span className={kind === 'proposed' ? 'etag prov' : 'chip info'}>{text}</span>
}
