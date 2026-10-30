export type ArchStatus = 'implemented' | 'upcoming' | 'proposed'
export type FlowKind = 'data' | 'control' | 'async'
export type Side = 'left' | 'right' | 'top' | 'bottom'

export interface ArchNode {
  id: string
  label: string
  layer: string
  status: ArchStatus
  x: number
  y: number
  w: number
  h: number
  purpose: string
  inputs: string[]
  outputs: string[]
  responsibilities: string[]
}

export interface ArchEdge {
  id: string
  from: string
  to: string
  label: string
  kind: FlowKind
  status: ArchStatus
  fromSide: Side
  toSide: Side
  lane?: 'east' | 'west'
}

export interface ArchBand {
  label: string
  x: number
  y: number
  w: number
  h: number
  tone: ArchStatus
}

export interface ArchStep {
  badge: string
  title: string
  caption: string
  nodes: string[]
}

export interface ArchGraph {
  id: 'poc' | 'proposed'
  title: string
  lede: string
  walkthrough: string
  width: number
  height: number
  bands: ArchBand[]
  nodes: ArchNode[]
  edges: ArchEdge[]
  steps: ArchStep[]
  initialNodeId: string
}

const POC_W = 1040
const POC_H = 520
const NW = 168
const NH = 64

function pocNode(
  id: string,
  label: string,
  layer: string,
  status: ArchStatus,
  x: number,
  y: number,
  purpose: string,
  inputs: string[],
  outputs: string[],
  responsibilities: string[],
): ArchNode {
  return { id, label, layer, status, x, y, w: NW, h: NH, purpose, inputs, outputs, responsibilities }
}

const pocNodes: ArchNode[] = [
  pocNode(
    'user',
    'Risk stakeholder',
    'Experience',
    'implemented',
    16,
    42,
    'A person using Metrics Analyzer to see portfolio health, open a metric, or start from a seeded investigation.',
    ['Dashboard, Triage, register, and investigation links'],
    ['A request for a metric or an investigation'],
    ['Opens the screens that exist today', 'Does not connect to SMARTS or Cortex'],
  ),
  pocNode(
    'frontend',
    'React + Vite UI',
    'Experience',
    'implemented',
    220,
    42,
    'The Metrics Analyzer interface. Screens call the in-app API object and render its typed responses.',
    ['Stakeholder navigation', 'RiskApi responses'],
    ['Dashboard, Triage, register, metric detail, and investigation views'],
    ['Keeps the mock boundary: screens do not import fixtures', 'Labels illustrative readings and simulated analysis'],
  ),
  pocNode(
    'contract',
    'Mock API contract',
    'Application',
    'implemented',
    424,
    42,
    'Typed request and response models in the frontend service boundary. A future HTTP map is documented and unused.',
    ['Triage, metric, trend, and investigation calls'],
    ['The same shapes a later backend would return'],
    ['UI depends on RiskApi, not on route strings', 'Swapping the mock later should not require a screen rewrite'],
  ),
  pocNode(
    'services',
    'Mock services',
    'Application',
    'implemented',
    628,
    42,
    'Deterministic Promise-based functions. They wait briefly, then answer from local fixtures and the shared status rules.',
    ['Contract calls'],
    ['Portfolio counts, metric lists, trends, and seeded investigations'],
    ['No network call', 'Does not invent a reading when none was supplied'],
  ),
  pocNode(
    'fixtures',
    'Illustrative fixtures',
    'Data',
    'implemented',
    832,
    42,
    'Local definitions, thresholds, readings, trends, four seeded investigations, and organization contribution where it was supplied.',
    ['Authored demo records'],
    ['Records the services read'],
    ['Marks scenario facts separately from synthetic readings', 'Organization contribution exists only for M001 and M003'],
  ),
  pocNode(
    'rules',
    'Threshold rules',
    'Application',
    'implemented',
    628,
    132,
    'Shared status evaluation. Higher-is-better and lower-is-better thresholds produce green, amber, red, or not evaluated.',
    ['A reading, direction, and green and amber thresholds'],
    ['A status the screens and portfolio counts both use'],
    ['A null reading is insufficient data, not healthy', 'Boundaries are provisional pending validation'],
  ),
  pocNode(
    'smarts',
    'SMARTS',
    'Upcoming sources',
    'upcoming',
    16,
    286,
    'Intended source of metric results, control definitions, and threshold metadata. Not connected.',
    ['Operational metric and control records'],
    ['Extracts a later pipeline would land'],
    ['Upcoming — not connected', 'The demo banner remains accurate'],
  ),
  pocNode(
    'snowflake',
    'Snowflake tables',
    'Upcoming sources',
    'upcoming',
    220,
    286,
    'Intended governed store for metric history. Not connected, and this POC does not query it.',
    ['Landed metric and context extracts'],
    ['Curated tables a semantic model would describe'],
    ['Upcoming — not connected', 'Missing joins would stay missing'],
  ),
  pocNode(
    'semantic',
    'Semantic models',
    'Upcoming sources',
    'upcoming',
    424,
    286,
    'Intended description of metric meaning, dimensions, and approved measures. Not connected.',
    ['Curated metric datasets'],
    ['A governed surface for analytical questions'],
    ['Upcoming — not connected', 'Would not replace the provisional definitions until they are validated'],
  ),
  pocNode(
    'analyst',
    'Cortex Analyst',
    'Upcoming intelligence',
    'upcoming',
    628,
    286,
    'Intended metric-aware analysis against semantic models. Nothing on this screen calls Cortex.',
    ['Governed semantic queries'],
    ['Structured comparisons and summaries'],
    ['Upcoming — not connected', 'Distinct from Cortex Agents'],
  ),
  pocNode(
    'agents',
    'Cortex Agents',
    'Upcoming intelligence',
    'upcoming',
    832,
    286,
    'Intended orchestration of a multi-step investigation through approved tools. Not connected.',
    ['Analyst results and approved evidence tools'],
    ['Findings with evidence and stated uncertainty'],
    ['Upcoming — not connected', 'Would not declare a proven root cause from a missing join'],
  ),
  pocNode(
    'ops',
    'Operational sources',
    'Upcoming sources',
    'upcoming',
    16,
    392,
    'Change, incident, and organizational records. Whether they can be joined to metrics is still a verification item.',
    ['Change, incident, and organization data, where it exists'],
    ['Context an investigation could cite'],
    ['Upcoming — not connected', 'Join feasibility is not established'],
  ),
  pocNode(
    'evidence',
    'Evidence results',
    'Upcoming intelligence',
    'upcoming',
    628,
    392,
    'Intended investigation payload: findings tied to definitions, readings, and cited evidence. The current summaries are deterministic mocks.',
    ['Agent findings and source citations'],
    ['A response the backend would store and return'],
    ['Upcoming — not connected', 'Today’s on-screen summary says it is not a Cortex response'],
  ),
  pocNode(
    'backend',
    'Backend API',
    'Upcoming application',
    'upcoming',
    220,
    392,
    'A future service in the separate backend repository would implement the contracts this UI already uses. That repository is not connected.',
    ['Authenticated frontend requests', 'Evidence-backed investigation results'],
    ['The HTTP responses documented as a future map'],
    ['Upcoming — not connected', 'The browser would still not call Snowflake or Cortex directly'],
  ),
]

const pocEdges: ArchEdge[] = [
  edge('p1', 'user', 'frontend', 'opens', 'control', 'implemented', 'right', 'left'),
  edge('p2', 'frontend', 'contract', 'calls', 'control', 'implemented', 'right', 'left'),
  edge('p3', 'contract', 'services', 'runs', 'control', 'implemented', 'right', 'left'),
  edge('p4', 'services', 'fixtures', 'reads', 'data', 'implemented', 'right', 'left'),
  edge('p5', 'services', 'rules', 'status', 'control', 'implemented', 'bottom', 'top'),
  edge('p6', 'smarts', 'snowflake', 'extract', 'data', 'upcoming', 'right', 'left'),
  edge('p7', 'snowflake', 'semantic', 'curate', 'data', 'upcoming', 'right', 'left'),
  edge('p8', 'semantic', 'analyst', 'model', 'data', 'upcoming', 'right', 'left'),
  edge('p9', 'analyst', 'agents', 'tools', 'control', 'upcoming', 'right', 'left'),
  edge('p10', 'ops', 'snowflake', 'context', 'data', 'upcoming', 'right', 'left'),
  edge('p11', 'agents', 'evidence', 'findings', 'data', 'upcoming', 'bottom', 'top'),
  edge('p12', 'evidence', 'backend', 'return', 'data', 'upcoming', 'left', 'right'),
  edge('p13', 'backend', 'frontend', 'later', 'control', 'upcoming', 'left', 'left', 'west'),
]

export const pocGraph: ArchGraph = {
  id: 'poc',
  title: 'POC Design',
  lede: 'What this prototype actually runs, and the integrations that are drawn only as upcoming.',
  walkthrough: 'Trace a metric investigation',
  width: POC_W,
  height: POC_H,
  bands: [
    { label: 'Implemented in this POC', x: 8, y: 12, w: 1024, h: 210, tone: 'implemented' },
    { label: 'Upcoming — not connected', x: 8, y: 240, w: 1024, h: 264, tone: 'upcoming' },
  ],
  nodes: pocNodes,
  edges: pocEdges,
  initialNodeId: 'frontend',
  steps: [
    {
      badge: "Today's mock path",
      title: 'Open an investigation',
      caption: 'A stakeholder opens Dashboard, the register, a metric, or an investigation. This path runs in the browser.',
      nodes: ['user', 'frontend'],
    },
    {
      badge: "Today's mock path",
      title: 'Call the mock contract',
      caption: 'The screen calls the typed API. It does not import fixture files and it does not use the network.',
      nodes: ['frontend', 'contract'],
    },
    {
      badge: "Today's mock path",
      title: 'Read illustrative fixtures',
      caption: 'Services resolve from local definitions, readings, trends, investigations, and organization data where it was supplied.',
      nodes: ['contract', 'services', 'fixtures'],
    },
    {
      badge: "Today's mock path",
      title: 'Evaluate the threshold',
      caption: 'Shared rules return green, amber, red, or not evaluated. A missing reading is not treated as healthy.',
      nodes: ['services', 'rules'],
    },
    {
      badge: "Today's mock path",
      title: 'Render the summary',
      caption: 'The screen shows that deterministic result. It is not a Snowflake Cortex response.',
      nodes: ['frontend', 'services'],
    },
    {
      badge: 'Future path — not connected',
      title: 'Metric result',
      caption: 'SMARTS results would land in Snowflake. That path is not connected.',
      nodes: ['smarts', 'snowflake'],
    },
    {
      badge: 'Future path — not connected',
      title: 'Metric-aware summary',
      caption: 'Cortex Analyst would query a semantic model. It is not connected, and it is not the same component as an agent.',
      nodes: ['semantic', 'analyst'],
    },
    {
      badge: 'Future path — not connected',
      title: 'Signals, cause, and hotspot',
      caption: 'Agents would use approved tools and operational context where a join exists. Organization contribution is not available for every metric.',
      nodes: ['ops', 'agents', 'analyst'],
    },
    {
      badge: 'Future path — not connected',
      title: 'Return the investigation',
      caption: 'Evidence-grounded results would come back through the backend API to these screens. None of that is live.',
      nodes: ['evidence', 'backend', 'frontend'],
    },
  ],
}

const PW = 1080
const ROW = 118
const MARGIN = 32
const GAP = 34
const PH = 62
const PNODE_W = (PW - MARGIN * 2 - GAP * 4) / 5

function slot(col: number, row: number) {
  return {
    x: MARGIN + col * (PNODE_W + GAP),
    y: 10 + row * ROW + 30,
    w: PNODE_W,
    h: PH,
  }
}

function band(row: number, label: string): ArchBand {
  return { label, x: 8, y: 10 + row * ROW, w: PW - 16, h: ROW - 8, tone: 'proposed' }
}

function proposedNode(
  id: string,
  label: string,
  layer: string,
  col: number,
  row: number,
  purpose: string,
  inputs: string[],
  outputs: string[],
  responsibilities: string[],
  status: ArchStatus = 'proposed',
): ArchNode {
  return { id, label, layer, status, ...slot(col, row), purpose, inputs, outputs, responsibilities }
}

const proposedNodes: ArchNode[] = [
  proposedNode('src-smarts', 'SMARTS metrics', 'Sources', 0, 0, 'Metric results, control definitions, and threshold metadata from SMARTS.', ['SMARTS metric and control records'], ['Extracts for validation'], ['Source system, not the warehouse', 'Not connected in this POC']),
  proposedNode('src-dq', 'Data Quality sets', 'Sources', 1, 0, 'Data Quality controls and other metric categories found in the client workbook, once a later pass maps them.', ['Workbook and operational DQ extracts'], ['Candidate metric definitions and results'], ['Kept distinct from the ten technology metrics loaded today', 'Not ingested yet']),
  proposedNode('src-org', 'Organization', 'Sources', 2, 0, 'Organizational hierarchy and metric-by-organization breakdowns, if the source holds them.', ['Org hierarchy and breakdowns'], ['Dimensions for hotspot analysis'], ['Availability is a verification item, not an assumption']),
  proposedNode('src-events', 'Change and incidents', 'Sources', 3, 0, 'Change and incident records that might explain a breach.', ['Change and incident feeds'], ['Events eligible for a reliable join'], ['A failed or unknown join stays absent']),
  proposedNode('src-notes', 'Analyst commentary', 'Sources', 4, 0, 'Analyst notes and other evidence, where a source actually provides them.', ['Commentary and evidence records'], ['Citations an investigation may use'], ['Not invented when the source is empty']),
  proposedNode('ing-validate', 'Schema validation', 'Ingestion', 0, 1, 'Checks that landed records match the expected fields before they are stored for analysis.', ['Source extracts'], ['Accepted or rejected batches'], ['Rejects malformed records instead of guessing']),
  proposedNode('ing-quality', 'Quality checks', 'Ingestion', 1, 1, 'Data-quality checks on incoming metrics: completeness, duplicates, and impossible values.', ['Validated batches'], ['Quarantine or pass decisions'], ['Does not turn a failed check into a green metric']),
  proposedNode('ing-norm', 'Normalization', 'Ingestion', 2, 1, 'Maps source fields onto shared metric, organization, and event shapes.', ['Validated records'], ['Normalized records'], ['Preserves source identifiers for traceability']),
  proposedNode('ing-fresh', 'Freshness and versions', 'Ingestion', 3, 1, 'Records as-of time and versions definitions and thresholds before analytical use.', ['Normalized definitions and readings'], ['Versioned, freshness-stamped records'], ['A new threshold does not rewrite history']),
  proposedNode('sf-landing', 'Landing datasets', 'Snowflake', 0, 2, 'Raw or landing tables in Snowflake. Analytical consumers do not read this layer directly.', ['Ingestion output'], ['Landed source-shaped tables'], ['Separate from curated metrics']),
  proposedNode('sf-curated', 'Curated metrics', 'Snowflake', 1, 2, 'Validated metric readings, history, and the threshold version that applied at the time.', ['Landed records that passed checks'], ['Curated fact and threshold history'], ['The surface behind trustworthy comparisons']),
  proposedNode('sf-org', 'Org and related events', 'Snowflake', 2, 2, 'Organization contributions and change or incident rows only where a reliable join exists.', ['Normalized org and event records'], ['Dimensions and linked events, or an explicit gap'], ['Missing joins are stored as unavailable, not filled in']),
  proposedNode('sf-semantic', 'Semantic models', 'Snowflake', 3, 2, 'Defines metric meaning, dimensions, and approved measures so questions use one vocabulary.', ['Curated metrics and approved dimensions'], ['A governed model for Analyst'], ['Consistent definitions improve comparable answers']),
  proposedNode('ai-analyst', 'Cortex Analyst', 'Intelligence', 1, 3, 'Answers metric-aware questions by querying the semantic model. It does not orchestrate an investigation.', ['Approved measures and dimensions'], ['Structured results and comparisons'], ['Grounded in the model, not in free-form invention', 'Not interchangeable with Agents']),
  proposedNode('ai-tools', 'Tool interface', 'Intelligence', 2, 3, 'The explicit boundary Agents use to call Analyst and evidence retrieval. Tools are approved, not open-ended.', ['Agent tool requests'], ['Analyst results and retrieved evidence'], ['Keeps model calls inside known contracts']),
  proposedNode('ai-agents', 'Cortex Agents', 'Intelligence', 3, 3, 'Orchestrates a multi-step investigation: context, evidence, findings, and uncertainty.', ['A job brief and approved tools'], ['Structured findings with citations and gaps'], ['Does not treat missing evidence as a healthy result', 'Separate from Analyst']),
  proposedNode('client', 'Metrics Analyzer UI', 'API', 0, 4, 'The current React application. In this design it calls the backend only. It exists today; the API below does not.', ['Stakeholder actions', 'API responses and job status'], ['Dashboard, register, and investigation screens'], ['Already implemented as a mock-backed UI', 'Would not call Snowflake or Cortex from the browser'], 'implemented'),
  proposedNode('api-auth', 'Auth boundary', 'API', 1, 4, 'Request authentication, authorization, and validation before any data or model call.', ['Frontend requests'], ['Authorized, validated calls'], ['Proposed. No live identity provider is wired', 'Data boundaries apply here']),
  proposedNode('api-sync', 'Sync metric API', 'API', 2, 4, 'Ordinary overview and metric queries. This path is synchronous on purpose.', ['Authorized read requests'], ['Portfolio, metric, and trend responses'], ['Dashboard reads do not enter the investigation queue', 'Proposed, matching the contracts the UI already uses']),
  proposedNode('job-submit', 'Job submission', 'Async investigations', 0, 5, 'Accepts a long investigation and returns a job id. Status starts as accepted, then moves as the job runs.', ['An investigation request'], ['Job id and initial status'], ['Separate from a dashboard read', 'Proposed']),
  proposedNode('job-queue', 'Queue', 'Async investigations', 1, 5, 'Holds investigation work off the request path so a slow analysis cannot block the UI.', ['Submitted jobs'], ['Work items for a bounded pool'], ['Proposed. No queue product or depth target is chosen']),
  proposedNode('job-workers', 'Workers', 'Async investigations', 2, 5, 'A pool that runs analysis with limited concurrency, timeouts, and idempotent retries.', ['Queued jobs'], ['Tool calls, or a dead-letter record'], ['Concurrency limits are a design requirement, not a chosen count', 'Retries are safe only when the job is idempotent']),
  proposedNode('job-dead', 'Dead letter', 'Async investigations', 3, 5, 'Holds jobs that still fail after retries so they can be seen and replayed without silent success.', ['Exhausted failures'], ['A visible failed job'], ['Failure stays failed', 'Proposed']),
  proposedNode('job-result', 'Persisted result', 'Async investigations', 4, 5, 'Stores the investigation the UI can poll for. The browser does not wait on the worker.', ['Completed findings'], ['A result keyed by job id'], ['Status transitions remain queryable', 'Proposed']),
  proposedNode('ops-store', 'Job-state store', 'Records', 1, 6, 'Operational state for jobs. Which database holds it is a design decision, not a selection made here.', ['Job status and payloads'], ['Current state for the API'], ['Not the Snowflake analytical store', 'Proposed']),
  proposedNode('ops-audit', 'Audit and provenance', 'Records', 2, 6, 'Records who asked, which definition and prompt versions were used, and which evidence was cited.', ['Requests, versions, and citations'], ['An audit trail'], ['Separate from analytical tables', 'Proposed']),
  proposedNode('ops-observe', 'Observability', 'Records', 3, 6, 'Logs, metrics, traces, queue depth, worker use, latency, errors, and usage or cost telemetry.', ['Runtime signals'], ['Alerts and diagnostic history'], ['Proposed. No vendor or quota is specified']),
  proposedNode('safe-checks', 'Threshold checks', 'Safeguards', 0, 7, 'Repeatable checks that status rules and threshold versions match the approved definitions.', ['Curated metrics and rules'], ['Pass or fail of a correctness check'], ['Proposed. The POC rules are provisional']),
  proposedNode('safe-ground', 'Groundedness', 'Safeguards', 1, 7, 'Checks that a finding cites available evidence and does not fill a gap with a confident claim.', ['Findings and citations'], ['Accept, revise, or reject'], ['Proposed']),
  proposedNode('safe-eval', 'Regression evals', 'Safeguards', 2, 7, 'Versioned prompts, model settings, and repeatable cases, including the seeded investigations.', ['Named test cases and config versions'], ['A regression result'], ['Proposed. Not a running eval harness']),
  proposedNode('safe-access', 'Access and review', 'Safeguards', 3, 7, 'Data boundaries and human review before an important conclusion is treated as approved.', ['Role and dataset policy', 'Findings flagged for review'], ['Allow, deny, or hold'], ['Proposed. No approval workflow is live']),
  proposedNode('safe-fallback', 'Fallback', 'Safeguards', 4, 7, 'When data or a model call is unavailable, the API says so. It does not report the metric as healthy.', ['Timeouts, empty joins, and model errors'], ['A degraded response with the gap named'], ['Proposed', 'Matches the current rule that missing data is not green']),
]

const proposedEdges: ArchEdge[] = [
  edge('s1', 'src-smarts', 'ing-validate', 'extract', 'data', 'proposed', 'bottom', 'top'),
  edge('s2', 'src-dq', 'ing-quality', 'extract', 'data', 'proposed', 'bottom', 'top'),
  edge('s3', 'src-org', 'ing-norm', 'extract', 'data', 'proposed', 'bottom', 'top'),
  edge('s4', 'src-events', 'ing-norm', 'events', 'data', 'proposed', 'bottom', 'top'),
  edge('s5', 'src-notes', 'ing-fresh', 'notes', 'data', 'proposed', 'bottom', 'top'),
  edge('s6', 'ing-validate', 'sf-landing', 'land', 'data', 'proposed', 'bottom', 'top'),
  edge('s7', 'ing-quality', 'sf-curated', 'pass', 'data', 'proposed', 'bottom', 'top'),
  edge('s8', 'ing-norm', 'sf-org', 'shape', 'data', 'proposed', 'bottom', 'top'),
  edge('s9', 'ing-fresh', 'sf-curated', 'versions', 'data', 'proposed', 'bottom', 'top'),
  edge('s10', 'sf-landing', 'sf-curated', 'curate', 'data', 'proposed', 'right', 'left'),
  edge('s11', 'sf-curated', 'sf-org', 'history', 'data', 'proposed', 'right', 'left'),
  edge('s12', 'sf-org', 'sf-semantic', 'joins', 'data', 'proposed', 'right', 'left'),
  edge('s13', 'sf-semantic', 'ai-analyst', 'query', 'data', 'proposed', 'bottom', 'top'),
  edge('s14', 'ai-analyst', 'ai-tools', 'results', 'control', 'proposed', 'right', 'left'),
  edge('s15', 'ai-tools', 'ai-agents', 'tools', 'control', 'proposed', 'right', 'left'),
  edge('s16', 'client', 'api-auth', 'request', 'control', 'proposed', 'right', 'left'),
  edge('s17', 'api-auth', 'api-sync', 'allow', 'control', 'proposed', 'right', 'left'),
  edge('s18', 'api-sync', 'sf-semantic', 'sync read', 'control', 'proposed', 'right', 'right', 'east'),
  edge('s19', 'client', 'job-submit', 'investigate', 'async', 'proposed', 'bottom', 'top'),
  edge('s20', 'job-submit', 'job-queue', 'enqueue', 'async', 'proposed', 'right', 'left'),
  edge('s21', 'job-queue', 'job-workers', 'work', 'async', 'proposed', 'right', 'left'),
  edge('s22', 'job-workers', 'ai-tools', 'call', 'control', 'proposed', 'right', 'right', 'east'),
  edge('s23', 'job-workers', 'job-result', 'store', 'async', 'proposed', 'right', 'left'),
  edge('s24', 'job-workers', 'job-dead', 'fail', 'async', 'proposed', 'right', 'left'),
  edge('s25', 'job-result', 'client', 'poll', 'control', 'proposed', 'top', 'bottom'),
  edge('s26', 'job-result', 'ops-store', 'state', 'data', 'proposed', 'bottom', 'top'),
  edge('s27', 'job-result', 'ops-audit', 'cite', 'data', 'proposed', 'bottom', 'top'),
  edge('s28', 'job-queue', 'ops-observe', 'depth', 'control', 'proposed', 'bottom', 'top'),
  edge('s29', 'safe-checks', 'safe-ground', 'checks', 'control', 'proposed', 'right', 'left'),
  edge('s30', 'safe-ground', 'safe-eval', 'cases', 'control', 'proposed', 'right', 'left'),
  edge('s31', 'safe-eval', 'safe-access', 'review', 'control', 'proposed', 'right', 'left'),
  edge('s32', 'safe-access', 'safe-fallback', 'gap', 'control', 'proposed', 'right', 'left'),
  edge('s33', 'job-workers', 'safe-checks', 'verify', 'control', 'proposed', 'left', 'left', 'west'),
]

export const proposedGraph: ArchGraph = {
  id: 'proposed',
  title: 'Proposed Design',
  lede: 'A production shape. Every box except the current UI is a proposal. Nothing in this diagram is deployed.',
  walkthrough: 'Trace a production request',
  width: PW,
  height: 10 + 8 * ROW,
  bands: [
    band(0, 'Sources'),
    band(1, 'Ingestion'),
    band(2, 'Snowflake'),
    band(3, 'Cortex Analyst and Agents'),
    band(4, 'Backend API — synchronous reads'),
    band(5, 'Asynchronous investigations'),
    band(6, 'Job state, audit, and observability'),
    band(7, 'Evaluations and safeguards'),
  ],
  nodes: proposedNodes,
  edges: proposedEdges,
  initialNodeId: 'api-sync',
  steps: [
    {
      badge: 'Synchronous read',
      title: 'Dashboard request',
      caption: 'An ordinary portfolio or metric query is authenticated and answered on the request path. It is not placed on the investigation queue.',
      nodes: ['client', 'api-auth', 'api-sync'],
    },
    {
      badge: 'Synchronous read',
      title: 'Governed metric read',
      caption: 'The API reads curated data through the semantic model. The browser does not query Snowflake.',
      nodes: ['api-sync', 'sf-semantic', 'sf-curated'],
    },
    {
      badge: 'Asynchronous investigation',
      title: 'Submit a job',
      caption: 'A multi-step investigation returns a job id. Worker count, queue product, and latency are not decided here.',
      nodes: ['client', 'job-submit', 'job-queue'],
    },
    {
      badge: 'Asynchronous investigation',
      title: 'Analyst and Agents',
      caption: 'Workers call Agents. Agents call Analyst and evidence tools through the tool interface. The two Cortex capabilities stay distinct.',
      nodes: ['job-workers', 'ai-tools', 'ai-agents', 'ai-analyst'],
    },
    {
      badge: 'Asynchronous investigation',
      title: 'Result or failure',
      caption: 'A finished result is stored for the UI to poll. Retries that still fail land on the dead-letter path and stay failed.',
      nodes: ['job-workers', 'job-result', 'job-dead', 'client'],
    },
    {
      badge: 'Proposed controls',
      title: 'Checks, audit, and fallback',
      caption: 'Correctness, groundedness, regression cases, access review, audit, and telemetry are planned. They are not running. A gap is reported rather than shown as healthy.',
      nodes: ['safe-checks', 'safe-ground', 'safe-eval', 'safe-access', 'safe-fallback', 'ops-audit', 'ops-observe'],
    },
  ],
}

function edge(
  id: string,
  from: string,
  to: string,
  label: string,
  kind: FlowKind,
  status: ArchStatus,
  fromSide: Side,
  toSide: Side,
  lane?: 'east' | 'west',
): ArchEdge {
  return { id, from, to, label, kind, status, fromSide, toSide, lane }
}

export function statusLabel(status: ArchStatus): string {
  if (status === 'implemented') return 'Implemented'
  if (status === 'upcoming') return 'Upcoming — not connected'
  return 'Proposed'
}

export function statusShort(status: ArchStatus): string {
  if (status === 'implemented') return 'In this POC'
  if (status === 'upcoming') return 'Not connected'
  return 'Proposed'
}

export function kindLabel(kind: FlowKind): string {
  if (kind === 'data') return 'Data flow'
  if (kind === 'async') return 'Asynchronous work'
  return 'Control flow'
}
