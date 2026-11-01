export type SummaryErrorKind = 'load' | 'generate' | null

/** A failed summary keeps an explicit next step. Loading again never submits a run. */
export function summaryRetry(kind: SummaryErrorKind): 'reload' | 'generate' | 'none' {
  if (kind === 'load') return 'reload'
  if (kind === 'generate') return 'generate'
  return 'none'
}
