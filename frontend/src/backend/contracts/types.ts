export const DATA_NOTICE = 'Illustrative demo data — not connected to SMARTS'

export const SUMMARY_DISCLAIMER =
  'Deterministic illustrative summary. Not a Snowflake Cortex response. Not connected to SMARTS.'

export const PATH_DISCLAIMER =
  'Illustrative checks only. No owner, deadline, or approved plan is implied.'

export const VALIDATION_NOTE =
  'Pending verification: whether SMARTS holds metric-by-organization breakdowns, and whether change and incident records can be joined to metrics.'

export type Direction = 'higher_is_better' | 'lower_is_better'
export type RagStatus = 'green' | 'amber' | 'red' | 'insufficient_data'
export type DataOrigin = 'supplied_scenario' | 'illustrative_synthetic' | 'not_supplied' | 'workbook'
export type MetricFamily = 'technology_risk' | 'data_quality'
export type Availability = 'available' | 'unavailable'
export type Frequency = 'Daily' | 'Weekly' | 'Monthly'
export type Unit = '%' | 'count' | 'hrs'
export type DefinitionStatus = 'provisional_pending_validation'

export interface MetricDefinition {
  id: string
  name: string
  domain: string
  controlId: string
  frequency: Frequency
  direction: Direction
  unit: Unit
  thresholds: { green: number; amber: number }
  provisionalDefinition: string
  definitionStatus: DefinitionStatus
  ownerFunction: string | null
  controlStatement: string | null
}

export interface MetricReading {
  value: number | null
  asOf: string | null
  origin: DataOrigin
  status: RagStatus
  statusBasis: 'illustrative_reading' | 'not_evaluable' | 'workbook_rag'
  breachedOn: string | null
}

export interface TrendPoint {
  date: string
  value: number
  status: RagStatus
  origin: 'illustrative_synthetic' | 'workbook'
  unconfirmedAmber: boolean
  pointNote: string
}

export interface OrgGroup {
  name: string
  weightPercent: number | null
  value: number
  shareOfGapPercent: number
  status: RagStatus
  hotspot: boolean
}

export interface OrgContribution {
  availability: Availability
  origin: 'illustrative_synthetic' | 'not_supplied'
  reason: string
  methodNote: string | null
  shareLabel: string
  groups: OrgGroup[]
}

export interface Signal {
  id: string
  classification: 'scenario_fact' | 'hypothesis'
  title: string
  statement: string
  evidenceNote: string
  gaps: string[]
}

export interface TimelineEvent {
  date: string | null
  label: string
  kind: 'illustrative_reading' | 'scenario_fact'
  provenanceLabel: string
}

export interface LineageItem {
  label: string
  detail: string
}

export interface Investigation {
  metricId: string
  headline: string
  summary: { text: string; disclaimer: string }
  whatChanged: string
  whyItMatters: string
  timelineNote: string
  timeline: TimelineEvent[]
  signals: Signal[]
  lineage: LineageItem[]
  orgContribution: OrgContribution
  pathToGreen: { disclaimer: string; checks: string[]; possibleActions: string[] }
  validationNote: string
}

export interface InvestigationSummary {
  metricId: string
  name: string
  domain: string
  controlId: string
  frequency: Frequency
  direction: Direction
  status: RagStatus
  breachedOn: string
  illustrativeValueLabel: string
  hotspotLabel: string | null
  headline: string
}

export interface OverviewResponse {
  dataNotice: string
  asOfLabel: string
  portfolio: {
    red: number
    amber: number
    green: number
    insufficientData: number
    total: number
  }
  investigations: InvestigationSummary[]
  investigationDomains: string[]
  deterioration: Array<{ date: string; metricId: string; label: string }>
  hotspotCallouts: Array<{ metricId: string; group: string; statement: string }>
  validationNote: string
  dataQuality: DataQualityOverview
}

export interface MetricListQuery {
  q?: string
  domain?: string
  status?: RagStatus
  frequency?: Frequency
  family?: MetricFamily
  investigation?: boolean
  page?: number
  pageSize?: number
}

export interface OverviewQuery {
  domain?: string
}

export interface MetricListItem {
  family: MetricFamily
  metric: MetricDefinition
  reading: MetricReading
  investigationAvailable: boolean
}

export interface MetricListResponse {
  items: MetricListItem[]
  total: number
  page: number
  pageSize: number
  facets: {
    domains: string[]
    frequencies: Frequency[]
    statuses: RagStatus[]
    families: MetricFamily[]
    domainsByFamily: Record<MetricFamily, string[]>
  }
}

export interface WorkbookControlInfo {
  regulation: string
  report: string
  cde: string
  sourceSystem: string
  checkLogic: string
  principle: string
  severity: string
  failed: number
  total: number
  firstRed: string | null
  lastRed: string | null
  pointCount: number
  hasDeskSplit: boolean
}

export interface MetricDetailResponse {
  family: MetricFamily
  metric: MetricDefinition
  reading: MetricReading
  trend: TrendPoint[]
  coverageNote: string
  trendCaption: string | null
  investigationAvailable: boolean
  workbook?: WorkbookControlInfo
}

export interface DeskBreakdownRow {
  deskId: string
  deskName: string
  line: string
  region: string
  failed: number
  total: number
  passRate: number
  status: RagStatus
  shareOfFailures: number
}

export interface DeskBreakdown {
  controlId: string
  date: string | null
  available: boolean
  reason: string
  rows: DeskBreakdownRow[]
}

export interface ExceptionRecord {
  id: string
  date: string
  controlId: string
  deskId: string
  deskName: string
  tradeId: string
  field: string
  value: string
  reason: string
  severity: string
  status: string
  ageingDays: number
  team: string
}

export interface ExceptionQuery {
  controlId?: string
  status?: string
  page?: number
  pageSize?: number
}

export interface ExceptionPage {
  items: ExceptionRecord[]
  total: number
  page: number
  pageSize: number
  statuses: string[]
}

export interface ControlNote {
  events: Array<{ id: string; date: string; type: string; deskIds: string; description: string }>
  commentary: Array<{ date: string; ragAtTime: RagStatus; text: string; cause: string; path: string; author: string }>
}

export interface DataQualityStory {
  id: string
  name: string
  readme: string
  status: RagStatus
  asOf: string
  passRate: number
  failed: number
  total: number
  firstRed: string | null
  recent: Array<{ date: string; passRate: number; status: RagStatus }>
}

export interface DataQualityAtRisk {
  id: string
  name: string
  dimension: string
  status: RagStatus
  passRate: number
  failed: number
  total: number
  asOf: string
  firstRed: string | null
  lastRed: string | null
  recovered: boolean
  hasDeskSplit: boolean
  investigationAvailable: boolean
  eventCount: number
  readme: string | null
}

export interface DataQualityEvent {
  id: string
  date: string
  type: string
  controlId: string
  description: string
}

export interface DataQualityCoverage {
  deskControls: number
  controlDatesWithoutDesk: number
  controlsWithoutNarrative: number
  discrepancy: string
}

export interface DataQualityOverview {
  asOf: string
  dateFrom: string
  dateTo: string
  controls: number
  withResults: number
  latest: { red: number; amber: number; green: number }
  openExceptions: number
  byDimension: Array<{ name: string; red: number; amber: number; green: number }>
  hotspots: Array<{ deskId: string; deskName: string; failed: number; total: number; passRate: number | null; date: string; basis: string }>
  stories: DataQualityStory[]
  deskNote: string
  atRisk: DataQualityAtRisk[]
  events: DataQualityEvent[]
  coverage: DataQualityCoverage
}

export interface DqInvestigation {
  kind: 'data_quality'
  metricId: string
  name: string
  dimension: string
  readme: string
  established: string[]
  hypothesis: string[]
  notSupplied: string[]
  discrepancy: string | null
  disclaimer: string
  desks: DeskBreakdown
  notes: ControlNote
  exceptions: { total: number; open: number; oldestAge: number | null }
}

export interface TrendResponse {
  metricId: string
  origin: DataOrigin
  caption: string | null
  points: TrendPoint[]
}

export interface RiskApi {
  getOverview(query?: OverviewQuery): Promise<OverviewResponse>
  listMetrics(query?: MetricListQuery): Promise<MetricListResponse>
  getMetric(metricId: string): Promise<MetricDetailResponse>
  getTrend(metricId: string): Promise<TrendResponse>
  listInvestigations(): Promise<{ items: InvestigationSummary[] }>
  getInvestigation(metricId: string): Promise<Investigation | DqInvestigation>
  getOrgContribution(metricId: string): Promise<OrgContribution>
  getDeskBreakdown(controlId: string, date?: string): Promise<DeskBreakdown>
  listExceptions(query?: ExceptionQuery): Promise<ExceptionPage>
  getControlNotes(controlId: string): Promise<ControlNote>
}
