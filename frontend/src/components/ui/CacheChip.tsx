export function CacheChip() {
  return <span className="cache-chip">Cached</span>
}

export function LiveRunHint({ label }: { label: string | null }) {
  return <span className="fine live-run-hint">{label ? `Starts a live run, ${label.charAt(0).toLowerCase()}${label.slice(1)}` : 'Starts a live run'}</span>
}
