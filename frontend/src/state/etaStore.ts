export type AnalysisKind = 'INVESTIGATION' | 'SUMMARY'

export interface EtaEstimate {
  low: number
  high: number
  median: number
  label: string
}

const KEY = 'ma-eta-v1'
const MAX_SAMPLES = 20
const MIN_SAMPLES = 3

type Store = Record<AnalysisKind, number[]>

function empty(): Store {
  return { INVESTIGATION: [], SUMMARY: [] }
}

export function quantile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0
  if (sorted.length === 1) return sorted[0]
  const index = (sorted.length - 1) * p
  const lower = Math.floor(index)
  const upper = Math.ceil(index)
  if (lower === upper) return sorted[lower]
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower)
}

function round5(seconds: number): number {
  return Math.max(5, Math.round(seconds / 5) * 5)
}

/** Pure. `samples` are elapsed seconds of completed runs. */
export function estimateFromSamples(samples: number[]): EtaEstimate | null {
  const positive = samples.filter((value) => Number.isFinite(value) && value > 0)
  if (positive.length < MIN_SAMPLES) return null
  const sorted = [...positive].sort((a, b) => a - b)
  let usable = sorted
  if (sorted.length >= 5) {
    const mid = quantile(sorted, 0.5)
    const clamped = sorted.filter((value) => value >= mid * 0.25 && value <= mid * 3)
    if (clamped.length >= MIN_SAMPLES) usable = clamped
  }
  const median = quantile(usable, 0.5)
  const pad = median * 0.25
  const low = round5(Math.min(quantile(usable, 0.25), median - pad))
  const high = Math.max(low + 5, round5(Math.max(quantile(usable, 0.75), median + pad)))
  return {
    low,
    high,
    median: round5(median),
    label: `Usually about ${low} to ${high} seconds`,
  }
}

export function readSamples(kind: AnalysisKind): number[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw || raw.length > 4000) return []
    const parsed = JSON.parse(raw) as Partial<Store>
    const list = parsed[kind]
    if (!Array.isArray(list)) return []
    return list.filter((value) => typeof value === 'number' && value > 0).slice(-MAX_SAMPLES)
  } catch {
    return []
  }
}

export function recordSample(kind: AnalysisKind, seconds: number): void {
  if (!Number.isFinite(seconds) || seconds <= 0 || seconds > 20 * 60) return
  try {
    const current = empty()
    current.INVESTIGATION = readSamples('INVESTIGATION')
    current.SUMMARY = readSamples('SUMMARY')
    current[kind] = [...current[kind], seconds].slice(-MAX_SAMPLES)
    localStorage.setItem(KEY, JSON.stringify(current))
  } catch {
    /* Timing memory is optional. */
  }
}

export function estimateFor(kind: AnalysisKind): EtaEstimate | null {
  return estimateFromSamples(readSamples(kind))
}
