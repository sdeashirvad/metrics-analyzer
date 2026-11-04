/**
 * Frozen V2 API types. Contract version 2.0.0.
 * Field names follow resources/metrics_analyzer_v2/API_CONTRACT.md.
 * Shapes only: no fetch and no client behavior.
 */

export const CONTRACT_VERSION = '2.0.0' as const

export type Month = string
export type DefinitionId = `PD-${string}`
export type OrgTree = 'BUSINESS_ORG' | 'BU'
export type DenominatorScope = 'INCLUDES_PENDING' | 'EXCLUDES_PENDING' | 'MIXED' | 'UNDETERMINED'
export type AgentKey = 'analysis' | 'data'
export type AgentAvailability = 'available' | 'busy' | 'unavailable'

export const API_ERROR_CODES = [
  'VALIDATION_FAILED',
  'UNKNOWN_MONTH',
  'UNKNOWN_FILTER_VALUE',
  'UNSUPPORTED_SORT',
  'CONTEXT_TOO_LARGE',
  'MESSAGE_TOO_LONG',
  'CONTEXT_INVALID',
  'METRIC_NOT_FOUND',
  'APPLICATION_NOT_FOUND',
  'CONVERSATION_NOT_FOUND',
  'RUN_NOT_FOUND',
  'RUN_IN_PROGRESS',
  'RUN_NOT_RETRYABLE',
  'CONTEXT_STALE',
  'IDEMPOTENCY_KEY_REUSED',
  'AGENT_BUSY',
  'RATE_LIMITED',
  'AGENT_BUDGET_EXHAUSTED',
  'UPSTREAM_ERROR',
  'DATA_SOURCE_UNAVAILABLE',
  'AGENT_UNAVAILABLE',
  'THREAD_UNAVAILABLE',
  'FALLBACK_UNSUPPORTED',
  'UPSTREAM_TIMEOUT',
] as const

export type ApiErrorCode = (typeof API_ERROR_CODES)[number]

/** HTTP status for each code in contract 3.2. `code` on the wire stays a string. */
export const API_ERROR_HTTP_STATUS: Record<ApiErrorCode, number> = {
  VALIDATION_FAILED: 400,
  UNKNOWN_MONTH: 400,
  UNKNOWN_FILTER_VALUE: 400,
  UNSUPPORTED_SORT: 400,
  CONTEXT_TOO_LARGE: 400,
  MESSAGE_TOO_LONG: 400,
  CONTEXT_INVALID: 400,
  METRIC_NOT_FOUND: 404,
  APPLICATION_NOT_FOUND: 404,
  CONVERSATION_NOT_FOUND: 404,
  RUN_NOT_FOUND: 404,
  RUN_IN_PROGRESS: 409,
  RUN_NOT_RETRYABLE: 409,
  CONTEXT_STALE: 409,
  IDEMPOTENCY_KEY_REUSED: 409,
  AGENT_BUSY: 429,
  RATE_LIMITED: 429,
  AGENT_BUDGET_EXHAUSTED: 429,
  UPSTREAM_ERROR: 502,
  DATA_SOURCE_UNAVAILABLE: 503,
  AGENT_UNAVAILABLE: 503,
  THREAD_UNAVAILABLE: 503,
  FALLBACK_UNSUPPORTED: 503,
  UPSTREAM_TIMEOUT: 504,
}

export interface FieldError {
  field: string
  code: string
  message: string
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    retryable: boolean
    requestId: string
    retryAfterMs?: number
    fieldErrors?: FieldError[]
    details?: Record<string, unknown>
  }
}

export interface ApiWarning {
  code: string
  message: string
}

export interface Lineage {
  field: string
  class: 'observation' | 'derived' | 'hypothesis'
  status: 'source' | 'documented_rule' | 'provisional' | 'assumption' | 'not_available'
  definitionIds: string[]
  source: {
    objects: string[]
    columns: string[]
    grain: 'application_month' | 'metric_row' | 'application' | 'metric_month'
  }
}

export interface DatasetMeta {
  version: string
  rowCount: number
  promotedAt: string | null
}

export interface EnvelopeMeta {
  contractVersion: typeof CONTRACT_VERSION
  definitionsVersion: string
  requestId: string
  generatedAt: string
  asOf: string | null
  dataset: DatasetMeta
  source: 'snowflake' | 'packaged'
  cache: { hit: boolean; ageSeconds: number; ttlSeconds: number }
  warnings: ApiWarning[]
  lineage?: Lineage[]
}

export interface Envelope<T> {
  data: T
  meta: EnvelopeMeta
}

export interface Count {
  value: number
  prior: number | null
  delta: number | null
}

export interface RateValue {
  numerator: number
  denominator: number
  rate: number | null
  priorRate: number | null
  deltaPp: number | null
  definitionId: 'PD-01'
}

export interface Share {
  value: number | null
  prior: number | null
  deltaPp: number | null
  definitionId: 'PD-08'
}

export interface OrgRef {
  tree: OrgTree
  level1: string
  level2: string | null
}

export interface Page {
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export interface ActiveFilters {
  month: Month
  orgTree: OrgTree
  l1: string[]
  l2: string[]
  legalEntity: string[]
  tier: number[]
  risk: string[]
  lifecycle: string[]
  ma: 'Y' | 'N' | null
}

/** Query form of the shared scope filters (contract 3.5). Omitted fields use server defaults. */
export interface ScopeFilters {
  month?: Month
  orgTree?: OrgTree
  l1?: string[]
  l2?: string[]
  legalEntity?: string[]
  tier?: number[]
  risk?: string[]
  lifecycle?: string[]
  ma?: 'Y' | 'N'
}

export interface PortfolioStatus {
  latestMonth: Month
  months: number
  dataset: { version: string; rowCount: number; promotedAt: string | null }
  source: 'snowflake' | 'packaged'
  definitionsVersion: string
  agents: { analysis: AgentAvailability; data: AgentAvailability }
}

export interface FilterMonth {
  month: Month
  applicationsReporting: number
  metricRows: number
  isLatest: boolean
}

export interface OrgLevelValue {
  value: string
  applications: number
}

export interface OrgLevelChild {
  value: string
  parent: string
}

export interface OrgTreeFilters {
  level1Label: string
  level2Label: string
  level1: OrgLevelValue[]
  level2: OrgLevelChild[]
}

export interface PortfolioFilters {
  defaultMonth: Month
  months: FilterMonth[]
  orgTrees: { BUSINESS_ORG: OrgTreeFilters; BU: OrgTreeFilters }
  legalEntities: Array<{ code: string; name: string }>
  tiers: number[]
  risks: string[]
  lifecycles: string[]
  maOptions: Array<'Y' | 'N'>
  vocab: {
    complianceStatus: string[]
    testStatus: string[]
    testResult: string[]
    complianceReason: string[]
    movement: string[]
  }
  metrics: Array<{
    metricId: string
    rows: number
    firstMonth: Month
    lastMonth: Month
    denominatorScope: DenominatorScope
  }>
}

export type RagStatus = 'green' | 'amber' | 'red' | 'unclassified'

export interface DefinitionRecord {
  id: DefinitionId
  name: string
  definition: string
  status: string
  basis: string
  appliesTo: string[]
  caveats: string[]
}

export interface DefinitionsData {
  definitions: DefinitionRecord[]
  conventions: Array<{ id: string; text: string }>
  classification?: {
    provisional: boolean
    rate: { definitionId: string; direction: string; unit: string; greenBelow: number; amberBelow: number; note: string }
    applicationGreen: { complianceStatus: string; testStatus: string; testResult: string; note: string }
  }
}

export interface OverviewMovement {
  newlyNonCompliant: number
  resolved: number
  persistentNonCompliant: number
  noPriorMonth: number
  notNonCompliantBothMonths: number
}

export interface PortfolioOverview {
  month: Month
  previousMonth: Month | null
  applicationsReporting: Count
  nonCompliant: { applications: Count; share: Share }
  testing: { withoutCompletedTest: Count; withFailedTest: Count }
  openFindings: Count
  metricRows: Count
  movement: OverviewMovement | null
  freshness: { datasetVersion: string; snapshotGeneratedAt: string | null; sourceRowCount: number }
}

export interface TrendPoint {
  month: Month
  applicationsReporting: number
  nonCompliantApplications: number
  nonCompliantShare: number | null
  withoutCompletedTest: number
  withFailedTest: number
  newlyNonCompliant: number | null
  resolved: number | null
  persistentNonCompliant: number | null
  metricRows: number
  openFindings: number
}

export interface PortfolioTrends {
  points: TrendPoint[]
  note: { code: 'POPULATION_GROWS'; text: string }
}

export type MetricRowStatus = 'Compliant' | 'Non_Compliant' | 'Pending' | 'Not_Applicable'
export type ApplicationStatusPrecedence = 'NON_COMPLIANT' | 'PENDING' | 'COMPLIANT' | 'NOT_APPLICABLE'

export interface ComplianceDistribution {
  month: Month
  metricRows: {
    total: number
    byStatus: Array<{ status: MetricRowStatus; rows: number; share: number }>
  }
  applications: {
    nonCompliant: number
    notNonCompliant: number
    total: number
    statusPrecedence?: Array<{
      status: ApplicationStatusPrecedence
      applications: number
      definitionId: 'PD-09'
    }>
  }
  topReasons: Array<{ reason: string; rows: number; nonCompliantRows: number }>
}

export type TestStatus = 'Test_Complete' | 'No_Test' | 'Test_Pending' | 'Exempt'

export interface TestingDistribution {
  month: Month
  byTestStatus: Array<{
    testStatus: TestStatus
    metricRows: number
    share: number
    distinctApplications: number
  }> | null
  completedTestResults: { pass: number; fail: number; notRecorded: number } | null
  applications: { withoutCompletedTest: number; withFailedTest: number; reporting: number }
  series?: Array<{
    month: Month
    applicationsReporting: number
    withoutCompletedTest: number
    withFailedTest: number
  }>
}

export type DistributionDimension = 'risk' | 'tier' | 'lifecycle' | 'rto' | 'legalEntity'

export interface AttributeDistribution {
  month: Month
  dimension: DistributionDimension
  items: Array<{
    key: string
    label: string
    applicationsReporting: number
    nonCompliantApplications: number
    nonCompliantShare: number | null
    share: number
  }>
  definitionIds: ['PD-08', 'PD-11']
}

export interface OrgContributionItem {
  key: string
  label: string
  org: OrgRef
  applicationsReporting: number
  nonCompliantApplications: number
  nonCompliantShare: number | null
  contributionShare: number | null
  newlyNonCompliant: number | null
  resolved: number | null
  withoutCompletedTest: number
  withFailedTest: number
  openFindings: number
}

export interface OrgContribution {
  month: Month
  orgTree: OrgTree
  level: 1 | 2
  parent: string | null
  totals: { applicationsReporting: number; nonCompliantApplications: number }
  items: OrgContributionItem[]
  page: Page
}

export interface DataCoverage {
  month: Month
  applicationsInDataset: number
  applicationsReporting: number
  applicationsNotReporting: number
  observedInAllMonths: { applications: number; share: number }
  observedInOneMonthOnly: { applications: number; share: number }
  metricsInDataset: number
  metricRowsInDataset: number
  applicationMonthsInDataset: number
  months: { first: Month; last: Month; count: number }
  freshness: { datasetVersion: string; promotedAt: string | null; snapshotGeneratedAt: string | null }
}

export type Attention =
  | 'nonCompliant'
  | 'noCompletedTest'
  | 'failedTest'
  | 'newlyNonCompliant'
  | 'resolved'
  | 'persistentNonCompliant'

export type ApplicationMovement =
  | 'NO_PRIOR_MONTH'
  | 'NEWLY_NON_COMPLIANT'
  | 'RESOLVED'
  | 'PERSISTENT_NON_COMPLIANT'
  | 'NOT_NON_COMPLIANT_BOTH_MONTHS'

export interface PortfolioApplication {
  eonId: string
  applicationName: string
  org: OrgRef
  legalEntityCode: string
  tier: number
  risk: string
  lifecycle: string
  isNonCompliant: boolean
  hasNoCompletedTest: boolean
  hasFailedTest: boolean
  movement: ApplicationMovement
  metricsReported: number
  metricRows: number
  nonCompliantRows: number
  openFindings: number | null
  nonCompliantSince: Month | null
}

export interface PortfolioApplications {
  month: Month
  items: PortfolioApplication[]
  summary: { matching: number; byOrgLevel1: Array<{ key: string; count: number }> }
  page: Page
}

export interface ComplianceRowCounts {
  compliant: number
  nonCompliant: number
  pending: number
  notApplicable: number
}

export interface TestRowCounts {
  complete: number
  pending: number
  none: number
  exempt: number
}

export interface MetricMovementCounts {
  newlyNonCompliant: number
  resolved: number
  persistentNonCompliant: number
  noPriorMonth: number
  other: number
}

export interface RegisterMetric {
  metricId: string
  family: null
  denominatorScope: DenominatorScope
  applications: number
  rate: RateValue
  complianceRows: ComplianceRowCounts
  nonCompliantApplications: number
  testRows: TestRowCounts
  movement: MetricMovementCounts | null
  rag: RagStatus
  sparkline: Array<{ month: Month; rate: number | null }>
}

export interface MetricRegister {
  month: Month
  previousMonth: Month | null
  items: RegisterMetric[]
  page: Page
  totals: { metrics: number; metricsWithRowsInMonth: number }
}

export type MetricFlagCode =
  | 'RATE_PROVISIONAL'
  | 'DENOMINATOR_SCOPE_INFERRED'
  | 'FAMILY_NOT_AVAILABLE'
  | 'SMALL_BASE'
  | 'NO_PRIOR_MONTH'

export interface MetricFlag {
  code: MetricFlagCode
  text: string
  definitionId?: DefinitionId
}

export interface MetricPreview {
  metricId: string
  family: null
  month: Month
  previousMonth: Month | null
  rate: RateValue
  movement: MetricMovementCounts | null
  compliance: ComplianceRowCounts
  testing: TestRowCounts & { pass: number; fail: number; resultNotRecorded: number }
  coverage: {
    applications: number
    applicationsReportingInScope: number
    coverageShare: number | null
    firstObserved: Month
    lastObserved: Month
    monthsObserved: number
  }
  activeFilters: ActiveFilters
  definition: {
    summary: string
    denominatorScope: DenominatorScope
    numeratorRule: string
    denominatorRule: string
    definitionIds: DefinitionId[]
  }
  flags: MetricFlag[]
  links: { summary: string; investigation: string }
  rag: RagStatus
}

export interface MetricSummary {
  preview: MetricPreview
  calculation: {
    formula: string
    steps: Array<{ label: string; value: number | null; note?: string }>
    excludedRows: { notApplicable: number; pendingExcluded: number; pendingIncluded: number }
  }
  distributions: {
    byComplianceStatus: Array<{ key: string; rows: number; share: number }>
    byTestStatus: Array<{ key: string; rows: number; share: number }>
    byComplianceReason: Array<{ key: string; rows: number; nonCompliantRows: number }>
  }
  topContributors: { nonCompliantApplications: ApplicationRow[] }
  availableMonths: Month[]
  provisional: Array<{ definitionId: DefinitionId; statement: string }>
}

export interface MetricCompositionPoint {
  month: Month
  continuing: number
  entered: number
  left: number
  continuingRate: number | null
  priorContinuingRate: number | null
}

export type MetricTrendPoint =
  | { month: Month; observed: false }
  | {
      month: Month
      observed: true
      applications: number
      numerator: number
      denominator: number
      rate: number | null
      nonCompliantApplications: number
      complianceRows: ComplianceRowCounts
      testRows: TestRowCounts
    }

export interface MetricTrend {
  metricId: string
  points: MetricTrendPoint[]
  composition: MetricCompositionPoint[]
}

export type MetricBreakdownDimension =
  | 'org'
  | 'legalEntity'
  | 'tier'
  | 'risk'
  | 'lifecycle'
  | 'complianceReason'
  | 'testStatus'

export interface MetricBreakdown {
  metricId: string
  month: Month
  dimension: MetricBreakdownDimension
  orgTree?: OrgTree
  level?: 1 | 2
  items: Array<{
    key: string
    label: string
    applications: number
    nonCompliantApplications: number
    rate: RateValue
    shareOfMetricNonCompliant: number | null
  }>
  page: Page
}

export type MetricMovement =
  | 'NO_PRIOR_MONTH'
  | 'NEWLY_NON_COMPLIANT'
  | 'RESOLVED'
  | 'PERSISTENT_NON_COMPLIANT'
  | 'OTHER'

export interface ApplicationRow {
  eonId: string
  applicationName: string
  org: OrgRef
  legalEntityCode: string
  complianceStatus: string
  complianceReason: string
  testStatus: string
  testResult: string | null
  isNumerator: boolean
  isDenominator: boolean
  rfb: number | null
  openFindings: number | null
  metricMovement: MetricMovement
}

export interface MetricApplications {
  metricId: string
  month: Month
  items: ApplicationRow[]
  page: Page
}

export interface AttributeChange {
  field: string
  from: string
  to: string
  month: Month
}

export interface ApplicationOwners {
  business: string
  it: string
}

export interface PeerComparison {
  definitionId: 'PD-17'
  applications: number
  nonCompliantApplications: number
  nonCompliantShare: number | null
  basis: { l1: string; lifecycle: string }
}

export interface ApplicationMetricRow {
  metricId: string
  complianceStatus: string
  complianceReason: string
  testStatus: string
  testResult: string | null
  isNumerator: boolean
  isDenominator: boolean
  rfb: number | null
  metricMovement: string
}

export interface ApplicationDetail {
  eonId: string
  applicationName: string
  month: Month
  observed: boolean
  lastObservedMonth: Month | null
  attributes: {
    tier: number
    risk: string
    lifecycle: string
    rto: string
    legalEntityCode: string
    legalEntityName: string
    isMergersAcquisitionsAsset: boolean
    org: {
      businessOrg: OrgRef & { superDepartment: string; department: string | null; busOrgLgNm: string }
      bu: OrgRef & { buSuperDepartment: string; buDepartment: string | null }
    }
    owners: ApplicationOwners | null
  }
  changedAttributes: AttributeChange[]
  status: {
    isNonCompliant: boolean
    hasNoCompletedTest: boolean
    hasFailedTest: boolean
    movement: string
    metricsReported: number
    metricRows: number
    nonCompliantRows: number
    openFindings: number | null
    statusPrecedence: string
  }
  metrics: ApplicationMetricRow[]
  peers: PeerComparison
}

export type ApplicationHistoryMonth =
  | { month: Month; observed: false }
  | {
      month: Month
      observed: true
      isNonCompliant: boolean
      hasNoCompletedTest: boolean
      hasFailedTest: boolean
      movement: string
      metricsReported: number
      metricRows: number
      openFindings: number | null
    }

export interface ApplicationHistory {
  eonId: string
  window: { first: Month; last: Month }
  months: ApplicationHistoryMonth[]
  metricTimeline: Array<{
    metricId: string
    months: Array<{
      month: Month
      observed: boolean
      complianceStatus?: string
      testStatus?: string
      testResult?: string | null
    }>
  }>
  attributeChanges: AttributeChange[]
  note: string
}

export interface ContentWarning {
  code: string
  message: string
}

export interface QueryResult {
  index: number
  toolUseId: string
  toolName: string | null
  sql: string | null
  queryId: string | null
  status: 'success' | 'empty' | 'error'
  error: { message: string } | null
  columns: Array<{ name: string; type: string; nullable: boolean | null; scale: number | null }>
  rows: Array<Array<string | null>>
  rowCount: number | null
  rowsReturned: number
  truncated: boolean
  truncation: {
    reason: 'RESULT_SET_LIMIT' | 'RESPONSE_CAP' | 'AGENT_ROW_LIMIT' | null
    limit: number | null
    note: string | null
  }
  exportable: boolean
}

export interface UserContent {
  kind: 'user'
  text: string
  contextHash: string | null
}

export interface DataExplorerContent {
  kind: 'dataset'
  interpretedIntent: string | null
  assumptions: string[]
  agentText: string
  noQueryExecuted: boolean
  queries: QueryResult[]
  primaryQueryIndex: number | null
  warnings: ContentWarning[]
}

export interface AnalysisContent {
  kind: 'analysis'
  text: string
  evidence: QueryResult[]
  toolActivity: Array<{
    toolUseId: string
    toolType: string
    toolName: string | null
    status: 'RESULT' | 'ERROR' | 'NO_RESULT'
  }>
  suggestedFollowUps: string[]
  notices: Array<{ code: 'AGENT_GENERATED'; text: string }>
  warnings: ContentWarning[]
}

export interface Message {
  messageId: string
  conversationId: string
  role: 'user' | 'assistant'
  agentKey: AgentKey
  runId: string | null
  createdAt: string
  content: UserContent | AnalysisContent | DataExplorerContent
}

export interface PrecomputedAnalysis {
  source: 'precomputed'
  target: { kind: 'metric'; metricId: string } | { kind: 'application'; eonId: string }
  month: Month
  generatedAt: string
  datasetVersion: string
  definitionsVersion: string
  agentSpecVersion: string | null
  stale: boolean
  staleReason: 'DATASET_CHANGED' | 'DEFINITIONS_CHANGED' | null
  label: string
  content: AnalysisContent
  sourceFactValidation?: 'PASS' | 'FAIL' | 'PARTIAL'
  sourceFactLimitation?: string | null
  displayName?: string | null
  dataAsOf?: string | null
  sourceSnapshot?: { version?: string; generatedAt?: string; sourceRowCount?: number } | null
  rag?: 'red' | 'amber' | 'green' | 'unclassified' | null
}

export interface AgentAnalysisRef {
  status: 'NOT_RUN' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'FALLBACK_STATIC'
  source: 'live' | 'precomputed' | null
  precomputed: PrecomputedAnalysis | null
  conversationId: string | null
  runId: string | null
  messageId: string | null
  generatedAt: string | null
  stale: boolean
  label: 'Agent-generated. Hypotheses are not established.'
}

export interface PortfolioFlag {
  code: string
  text: string
  definitionId?: DefinitionId
}

export interface MetricInvestigation {
  metricId: string
  month: Month
  previousMonth: Month | null
  observations: {
    rate: RateValue
    compliance: ComplianceRowCounts
    testing: TestRowCounts & { pass: number; fail: number; resultNotRecorded: number }
    applications: number
    rag: RagStatus
  }
  derived: {
    rateChange: { deltaPp: number | null; definitionId: 'PD-16' }
    composition: {
      continuing: number
      entered: number
      left: number
      continuingRate: number | null
      priorContinuingRate: number | null
      definitionId: 'PD-15'
    }
    movement: MetricMovementCounts | null
    largestContributors: Array<{
      dimension: 'org' | 'legalEntity'
      key: string
      nonCompliantApplications: number
      applications: number
      changeInNonCompliantVsPrior: number | null
    }>
  }
  sourceRows: { applicationsUrl: string; breakdownsUrl: string; trendUrl: string }
  agentAnalysis: AgentAnalysisRef
  flags: PortfolioFlag[]
}

export interface ApplicationInvestigation {
  application: ApplicationDetail
  history: ApplicationHistory
  derived: {
    nonCompliantRun: { months: number; since: Month | null } | null
    peers: PeerComparison
    definitionIds: DefinitionId[]
  }
  agentAnalysis: AgentAnalysisRef
  flags: PortfolioFlag[]
}

/** JSON claims inside a conversation handle (contract 3.8). `conversationId` itself is opaque. */
export interface ConversationHandlePayload {
  threadId: number
  agentKey: AgentKey
  createdAt: string
}

/** JSON claims inside a run token (contract 3.8 and 5.5.3). `runId` itself is opaque. */
export interface RunHandlePayload {
  threadId: number
  agentKey: AgentKey
  userMessageId: string
  snowflakeRunId: string
  submittedAt: string
}

export interface AgentMetadata {
  agentKey: AgentKey
  displayName: string
  description: string
  responseKind: 'analysis' | 'dataset'
  status: AgentAvailability
  capabilities: { showsSql: boolean; returnsDataset: boolean; charts: false; followUps: boolean }
  limits: { maxMessageChars: 2000; maxContextChars: 12000; overdueAfterMs: 180000; failAfterMs: 600000 }
}

export interface AgentsList {
  agents: AgentMetadata[]
}

export type EntrySurface =
  | 'general'
  | 'dashboard'
  | 'register_preview'
  | 'metric_summary'
  | 'metric_investigation'
  | 'application_investigation'

export interface ContextRequest {
  entrySurface: EntrySurface
  scope: {
    month?: Month
    metricId?: string
    eonId?: string
    filters?: Partial<ActiveFilters>
  }
  items?: { include?: string[]; exclude?: string[] }
}

export type ContextItemKind =
  | 'ground_rules'
  | 'scope'
  | 'definition'
  | 'kpis'
  | 'trend'
  | 'breakdown'
  | 'applications'
  | 'filters'
  | 'attributes'
  | 'history'
  | 'peers'
  | 'owners'
  | 'coverage'

export interface ContextItem {
  key: string
  label: string
  kind: ContextItemKind
  required: boolean
  included: boolean
  defaultIncluded: boolean
  sensitive: boolean
  summary: string
  lines: string[]
  approxChars: number
  definitionIds: DefinitionId[]
}

export interface ContextPreview {
  contextHash: string
  definitionsVersion: string
  entrySurface: EntrySurface
  scope: {
    month: Month
    monthSource: 'selected' | 'latest_available'
    metricId: string | null
    eonId: string | null
    filters: ActiveFilters
  }
  chips: string[]
  items: ContextItem[]
  rendered: { text: string; chars: number; approxTokens: number }
  warnings: ApiWarning[]
}

export interface Conversation {
  conversationId: string
  threadId: number
  agentKey: AgentKey
  title: string
  entrySurface: EntrySurface
  scope: { month: Month; metricId: string | null; eonId: string | null }
  chips: string[]
  contextHash: string
  messageCount: number
  createdAt: string
  updatedAt: string
}

export interface CreateConversationRequest {
  agentKey: AgentKey
  message: string
  context: ContextRequest
  contextHash: string
  clientRequestId: string
}

export interface SendMessageRequest {
  message: string
  clientRequestId: string
}

export type RunStatus = 'RUNNING' | 'COMPLETED' | 'FAILED'
export type RunEventType = 'submitted' | 'running' | 'overdue' | 'completed' | 'failed'

export interface Run {
  runId: string
  conversationId: string
  agentKey: AgentKey
  status: RunStatus
  overdue: boolean
  attempt: number
  retryOf: string | null
  submittedAt: string
  finishedAt: string | null
  elapsedMs: number
  pollAfterMs: number | null
  events: Array<{ at: string; type: RunEventType; detail?: string }>
  error: { code: string; message: string; retryable: boolean } | null
  message: Message | null
}

export interface CreateConversationResult {
  conversation: Conversation
  userMessage: Message
  run: Run
}

export interface SendMessageResult {
  userMessage: Message
  run: Run
}

export interface ConversationDetail {
  conversation: Conversation
  messages: Message[]
  activeRun: Run | null
}

/** GET conversation context. Contract 5.4 specifies readable lines and chips only. */
export interface ConversationContextSummary {
  chips: string[]
  lines: string[]
}

export interface RetryRunResult {
  run: Run
}

export interface SavedConversation {
  conversationId: string
  threadId: number
  agentKey: AgentKey
  title: string
  createdAt: string
  lastActivityAt: string
  contextSummary?: { chips: string[]; entrySurface: string }
  lastRunId?: string
}
