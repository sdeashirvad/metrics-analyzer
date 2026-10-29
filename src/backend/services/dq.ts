import summaryJson from '../data/dq/summary.json'
import definitionsJson from '../data/dq/definitions.json'
import hierarchyJson from '../data/dq/hierarchy.json'
import eventsJson from '../data/dq/events.json'
import commentaryJson from '../data/dq/commentary.json'
import type {
  ControlNote,
  DataQualityOverview,
  DeskBreakdown,
  DqInvestigation,
  ExceptionPage,
  ExceptionQuery,
  MetricDetailResponse,
  MetricListItem,
  RagStatus,
  TrendPoint,
} from '../contracts/types'
import { notFound } from './errors'

const STORIES = ['DQ-001', 'DQ-010', 'DQ-015', 'DQ-020', 'DQ-025']
const DESK_NOTE =
  'Desk rows exist for eight controls. Bars sum failed records on the latest shared date. A lower pass rate is not the same as a larger failure count.'

interface Definition {
  id: string
  name: string
  dimension: string
  frequency: 'Daily' | 'Weekly' | 'Monthly'
  green: number
  amber: number
  severity: string
  regulation: string
  report: string
  cde: string
  sourceSystem: string
  checkLogic: string
  principle: string
  owner: string
}

interface ResultRow {
  date: string
  controlId: string
  total: number
  failed: number
  passRate: number
  status: RagStatus
}

interface DeskRow {
  date: string
  controlId: string
  deskId: string
  total: number
  failed: number
  passRate: number
  status: RagStatus
}

interface ExceptionRow {
  id: string
  date: string
  controlId: string
  deskId: string
  tradeId: string
  field: string
  value: string
  reason: string
  severity: string
  status: string
  ageingDays: number
  team: string
}

const definitions = definitionsJson as Definition[]
const definitionById = new Map(definitions.map((item) => [item.id, item]))
const hierarchy = hierarchyJson as Array<{ id: string; name: string; line: string; region: string }>
const deskById = new Map(hierarchy.map((item) => [item.id, item]))

let resultsPromise: Promise<ResultRow[]> | null = null
let desksPromise: Promise<DeskRow[]> | null = null
let exceptionsPromise: Promise<ExceptionRow[]> | null = null

function loadResults() {
  resultsPromise ??= import('../data/dq/results.json').then((mod) => mod.default as ResultRow[])
  return resultsPromise
}

function loadDesks() {
  desksPromise ??= import('../data/dq/results-by-desk.json').then((mod) => mod.default as DeskRow[])
  return desksPromise
}

function loadExceptions() {
  exceptionsPromise ??= import('../data/dq/exceptions.json').then((mod) => mod.default as ExceptionRow[])
  return exceptionsPromise
}

function asStatus(value: string): RagStatus {
  if (value === 'green' || value === 'amber' || value === 'red') return value
  return 'insufficient_data'
}

export function dataQualityOverview(): DataQualityOverview {
  const summary = summaryJson
  return {
    asOf: summary.asOf,
    dateFrom: summary.dateFrom,
    dateTo: summary.dateTo,
    controls: summary.controls,
    withResults: summary.withResults,
    latest: summary.latest,
    openExceptions: summary.openExceptions,
    byDimension: summary.byDimension.map((item) => ({
      name: item.name,
      red: item.red,
      amber: item.amber,
      green: item.green,
    })),
    hotspots: summary.hotspots.map((item) => ({ ...item, passRate: item.passRate })),
    stories: summary.stories.map((item) => ({
      ...item,
      status: asStatus(item.status),
      recent: item.recent.map((point) => ({ ...point, status: asStatus(point.status) })),
    })),
    deskNote: DESK_NOTE,
    atRisk: atRiskControls(),
    events: allEvents.map(({ id, date, type, controlId, description }) => ({ id, date, type, controlId, description })),
    coverage: { ...summary.coverage, discrepancy: DQ020_DISCREPANCY },
  }
}

const DQ020_DISCREPANCY =
  'DQ-020: the README names Commodities and Securitised Products as hotspots. The supplied commentary mentions Treasury & Funding. Both are shown and not reconciled.'

type EventRow = { id: string; date: string; type: string; deskIds: string; description: string; controlId: string }
const allEvents = eventsJson as EventRow[]
const STATUS_RANK: Record<RagStatus, number> = { red: 0, amber: 1, insufficient_data: 2, green: 3 }

function atRiskControls() {
  const readme = new Map(summaryJson.stories.map((item) => [item.id, item.readme]))
  return summaryJson.latestByControl
    .filter((row) => row.status === 'red' || row.status === 'amber' || (STORIES.includes(row.id) && row.firstRed))
    .map((row) => {
      const status = asStatus(row.status)
      return {
        id: row.id,
        name: row.name,
        dimension: row.dimension,
        status,
        passRate: row.passRate,
        failed: row.failed,
        total: row.total,
        asOf: row.asOf,
        firstRed: row.firstRed,
        lastRed: row.lastRed,
        recovered: status === 'green' && row.firstRed !== null,
        hasDeskSplit: summaryJson.deskControls.includes(row.id),
        investigationAvailable: STORIES.includes(row.id),
        eventCount: allEvents.filter((event) => event.controlId === row.id).length,
        readme: readme.get(row.id) ?? null,
      }
    })
    .sort(
      (a, b) =>
        Number(a.recovered) - Number(b.recovered) ||
        STATUS_RANK[a.status] - STATUS_RANK[b.status] ||
        (a.firstRed ?? '9999').localeCompare(b.firstRed ?? '9999') ||
        a.id.localeCompare(b.id),
    )
}

export function dqListItems(): MetricListItem[] {
  return summaryJson.latestByControl.map((row) => {
    const definition = definitionById.get(row.id)
    return {
      family: 'data_quality',
      investigationAvailable: STORIES.includes(row.id),
      metric: {
        id: row.id,
        name: row.name,
        domain: row.dimension,
        controlId: row.id,
        frequency: row.frequency as 'Daily' | 'Weekly' | 'Monthly',
        direction: 'higher_is_better',
        unit: '%',
        thresholds: { green: row.green, amber: row.amber },
        provisionalDefinition: definition?.checkLogic ?? row.name,
        definitionStatus: 'provisional_pending_validation',
        ownerFunction: row.owner,
        controlStatement: definition?.checkLogic ?? null,
      },
      reading: {
        value: row.passRate,
        asOf: row.asOf,
        origin: 'workbook',
        status: asStatus(row.status),
        statusBasis: 'workbook_rag',
        breachedOn: row.firstRed,
      },
    }
  })
}

export async function dqMetric(controlId: string): Promise<MetricDetailResponse> {
  const definition = definitionById.get(controlId)
  const latest = summaryJson.latestByControl.find((row) => row.id === controlId)
  if (!definition || !latest) throw notFound(`No data-quality control ${controlId} is in the workbook.`)
  const series = (await loadResults())
    .filter((row) => row.controlId === controlId)
    .sort((a, b) => (a.date < b.date ? -1 : 1))
  const trend: TrendPoint[] = series.map((row) => ({
    date: row.date,
    value: row.passRate,
    status: row.status,
    origin: 'workbook',
    unconfirmedAmber: false,
    pointNote: 'Supplied dq_results row. The RAG value is the workbook status. Missing dates are not filled.',
  }))
  return {
    family: 'data_quality',
    investigationAvailable: STORIES.includes(controlId),
    metric: {
      id: definition.id,
      name: definition.name,
      domain: definition.dimension,
      controlId: definition.id,
      frequency: definition.frequency,
      direction: 'higher_is_better',
      unit: '%',
      thresholds: { green: definition.green, amber: definition.amber },
      provisionalDefinition: definition.checkLogic,
      definitionStatus: 'provisional_pending_validation',
      ownerFunction: definition.owner,
      controlStatement: definition.checkLogic,
    },
    reading: {
      value: latest.passRate,
      asOf: latest.asOf,
      origin: 'workbook',
      status: asStatus(latest.status),
      statusBasis: 'workbook_rag',
      breachedOn: latest.firstRed,
    },
    trend,
    coverageNote: `${series.length} supplied dq_results points from ${series[0]?.date ?? 'n/a'} to ${series.at(-1)?.date ?? 'n/a'}. Dates with no row are omitted.`,
    trendCaption: 'Workbook pass rate from dq_results. Status is the supplied RAG, not a recomputed Technology Risk rule. Not connected to SMARTS.',
    workbook: {
      regulation: definition.regulation,
      report: definition.report,
      cde: definition.cde,
      sourceSystem: definition.sourceSystem,
      checkLogic: definition.checkLogic,
      principle: definition.principle,
      severity: definition.severity,
      failed: latest.failed,
      total: latest.total,
      firstRed: latest.firstRed,
      lastRed: latest.lastRed,
      pointCount: series.length,
      hasDeskSplit: summaryJson.deskControls.includes(controlId),
    },
  }
}

export async function deskBreakdown(controlId: string, date?: string): Promise<DeskBreakdown> {
  if (!summaryJson.deskControls.includes(controlId)) {
    return {
      controlId,
      date: date ?? null,
      available: false,
      reason: 'dq_results_by_desk does not include this control. The workbook supplies a desk split for eight controls only.',
      rows: [],
    }
  }
  const rows = (await loadDesks()).filter((row) => row.controlId === controlId)
  const chosen = date ?? rows.reduce((max, row) => (row.date > max ? row.date : max), '')
  const day = rows.filter((row) => row.date === chosen)
  const failedSum = day.reduce((sum, row) => sum + row.failed, 0)
  return {
    controlId,
    date: chosen || null,
    available: day.length > 0,
    reason: day.length ? 'Failed-record share uses the desk rows for this control and date.' : 'No desk row for that date.',
    rows: day
      .map((row) => {
        const desk = deskById.get(row.deskId)
        return {
          deskId: row.deskId,
          deskName: desk?.name ?? row.deskId,
          line: desk?.line ?? '',
          region: desk?.region ?? '',
          failed: row.failed,
          total: row.total,
          passRate: row.passRate,
          status: row.status,
          shareOfFailures: failedSum ? (row.failed / failedSum) * 100 : 0,
        }
      })
      .sort((a, b) => b.failed - a.failed || a.deskName.localeCompare(b.deskName)),
  }
}

export async function exceptionPage(query: ExceptionQuery = {}): Promise<ExceptionPage> {
  const pageSize = query.pageSize ?? 25
  const page = query.page ?? 1
  let rows = await loadExceptions()
  if (query.controlId) rows = rows.filter((row) => row.controlId === query.controlId)
  if (query.status) rows = rows.filter((row) => row.status === query.status)
  const statuses = [...new Set((await loadExceptions()).filter((row) => !query.controlId || row.controlId === query.controlId).map((row) => row.status))].sort()
  const start = (page - 1) * pageSize
  return {
    total: rows.length,
    page,
    pageSize,
    statuses,
    items: rows.slice(start, start + pageSize).map((row) => ({
      ...row,
      deskName: deskById.get(row.deskId)?.name ?? row.deskId,
    })),
  }
}

export function controlNotes(controlId: string): ControlNote {
  return {
    events: allEvents
      .filter((row) => row.controlId === controlId)
      .map(({ controlId: _id, ...event }) => event),
    commentary: (commentaryJson as Array<{ date: string; controlId: string; ragAtTime: RagStatus; text: string; cause: string; path: string; author: string }>)
      .filter((row) => row.controlId === controlId)
      .map(({ controlId: _id, ...note }) => note),
  }
}

export async function dqInvestigation(controlId: string): Promise<DqInvestigation> {
  const story = summaryJson.stories.find((item) => item.id === controlId)
  const definition = definitionById.get(controlId)
  if (!story || !definition) throw notFound(`No planted data-quality investigation is available for ${controlId}.`)
  const desks = await deskBreakdown(controlId, story.asOf)
  const notes = controlNotes(controlId)
  const exceptions = (await loadExceptions()).filter((row) => row.controlId === controlId)
  const open = exceptions.filter((row) => row.status === 'Open')
  const oldest = open.reduce((max, row) => Math.max(max, row.ageingDays), 0)
  const top = desks.rows[0]
  const second = desks.rows[1]
  const established = [
    `${definition.name} (${definition.id}) measures ${definition.cde}. Check logic from the workbook: ${definition.checkLogic}`,
    `Latest supplied result on ${story.asOf} is ${story.passRate.toFixed(2)}% (${story.failed.toLocaleString()} failed of ${story.total.toLocaleString()}), RAG ${story.status}. Green is ${definition.green}% and amber is ${definition.amber}%.`,
    story.firstRed
      ? `The first red row in dq_results is ${story.firstRed}.`
      : 'The supplied series has no red row.',
  ]
  if (top && second) {
    established.push(
      `On ${desks.date}, ${top.deskName} has the most failed records (${top.failed.toLocaleString()}, ${top.shareOfFailures.toFixed(1)}% of this control's failures). ${second.deskName} is next at ${second.failed.toLocaleString()}. This ranking uses failure volume, not the lowest pass rate.`,
    )
  }
  established.push(
    `${exceptions.length} exception rows link to ${controlId} by control id. ${open.length} are Open${open.length ? `, oldest ageing ${oldest} days` : ''}.`,
  )
  if (notes.events.length) {
    established.push(
      `${notes.events.length} change or incident rows list related_control_id ${controlId}. That is a supplied link, not a proof that the event caused the RAG.`,
    )
  }
  const hypothesis = [
    `README planted story: ${story.readme}`,
    ...notes.commentary.map(
      (note) =>
        `Commentary on ${note.date} by ${note.author} states cause “${note.cause}” and path “${note.path}”. This is the supplied note, not a confirmed root cause.`,
    ),
  ]
  const notSupplied = [
    'No live SMARTS, Snowflake, or Cortex call produced this page.',
    'A related event is not treated as the cause only because its date is near a red reading.',
  ]
  const discrepancy =
    controlId === 'DQ-020' && notes.commentary.some((note) => note.text.includes('Treasury')) ? DQ020_DISCREPANCY : null
  if (discrepancy) {
    notSupplied.push(
      'The DQ-020 commentary mentions Treasury & Funding. The README hotspot is Commodities and Securitised. Both texts are shown; they are not reconciled into one cause.',
    )
  }
  return {
    kind: 'data_quality',
    metricId: controlId,
    name: definition.name,
    dimension: definition.dimension,
    readme: story.readme,
    established,
    hypothesis,
    notSupplied,
    discrepancy,
    disclaimer: 'Deterministic summary of workbook rows. Not a Snowflake Cortex response. Not connected to SMARTS.',
    desks,
    notes,
    exceptions: { total: exceptions.length, open: open.length, oldestAge: open.length ? oldest : null },
  }
}
