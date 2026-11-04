const intFmt = new Intl.NumberFormat('en-GB')
const pctFmt = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const signedFmt = new Intl.NumberFormat('en-GB', { signDisplay: 'exceptZero' })
const ppFmt = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })

export function formatInt(value: number): string {
  return intFmt.format(value)
}

export function formatSignedInt(value: number | null): string | null {
  if (value == null) return null
  return signedFmt.format(value)
}

/** Formats a 0–1 rate. Does not recompute it. */
export function formatPercent(rate: number | null): string | null {
  if (rate == null) return null
  return `${pctFmt.format(rate * 100)}%`
}

/** `deltaPp` is already in percentage points. */
export function formatPp(delta: number | null): string | null {
  if (delta == null) return null
  return `${ppFmt.format(delta)} pp`
}

export function formatMonth(month: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(month)
  if (!match) return month
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])))
  return new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date)
}

export function formatDuration(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000))
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (minutes === 0) return `${rest}s`
  return `${minutes}m ${rest}s`
}

const STATUS_LABEL: Record<string, string> = {
  Non_Compliant: 'Non-compliant',
  Compliant: 'Compliant',
  Pending: 'Pending',
  Not_Applicable: 'Not applicable',
  Test_Complete: 'Test complete',
  No_Test: 'No test',
  Test_Pending: 'Test pending',
  Exempt: 'Exempt',
  NO_PRIOR_MONTH: 'No prior month',
  NEWLY_NON_COMPLIANT: 'Newly non-compliant',
  RESOLVED: 'Resolved',
  PERSISTENT_NON_COMPLIANT: 'Persistent non-compliant',
  NOT_NON_COMPLIANT_BOTH_MONTHS: 'Not non-compliant in both months',
  OTHER: 'Other',
  INCLUDES_PENDING: 'Includes pending',
  EXCLUDES_PENDING: 'Excludes pending',
  MIXED: 'Mixed',
  UNDETERMINED: 'Undetermined',
}

export function labelOf(value: string): string {
  return STATUS_LABEL[value] ?? value
}
