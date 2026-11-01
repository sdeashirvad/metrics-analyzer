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
  /** Nodes doing the work in this step. Defaults to `nodes`. */
  active?: string[]
  /** Upstream nodes blocked until a child in this step finishes. */
  waiting?: string[]
  /** A new journey clears the completed path. Steps with the same id share one path. */
  journey?: string
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
  /** The UI that asked. Stays visible for the whole journey unless it is the active step. */
  requester: string[]
}

const POC_W = 1200
const POC_H = 468
const NW = 200
const NH = 76

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
    12,
    52,
    'A person using Metrics Analyzer to see portfolio health, open a control, or read an investigation.',
    ['Dashboard, Triage, register, and investigation links'],
    ['A request for a metric, a control, or an investigation'],
    ['Uses the screens in this application', 'Does not connect to SMARTS'],
  ),
  pocNode(
    'frontend',
    'React + Vite UI',
    'Experience',
    'implemented',
    258,
    52,
    'The Metrics Analyzer interface, hosted on Cloudflare Pages. It calls the API over HTTPS and renders the typed responses.',
    ['Stakeholder navigation', 'API responses and investigation status'],
    ['Dashboard, Triage, register, metric detail, and investigation views'],
    ['Does not query Snowflake or Cortex from the browser', 'Labels Technology Risk as illustrative and Data Quality as live'],
  ),
  pocNode(
    'gateway',
    'Public HTTPS',
    'Application',
    'implemented',
    504,
    52,
    'Public HTTPS on the Oracle Cloud VM. The reverse proxy forwards API calls to the application.',
    ['Browser requests to the public API address'],
    ['Requests on the private application port'],
    ['The browser talks only to this HTTPS address', 'The application port is not opened publicly'],
  ),
  pocNode(
    'api',
    'FastAPI backend',
    'Application',
    'implemented',
    750,
    52,
    'The API on the VM. It serves Data Quality from Snowflake, Technology Risk from illustrative scenario data, and investigation jobs.',
    ['Authorized reads and investigation requests'],
    ['Portfolio, control, and investigation responses'],
    ['One application process', 'A missing reading is not reported as healthy'],
  ),
  pocNode(
    'tr',
    'Technology Risk data',
    'Data',
    'implemented',
    996,
    52,
    'Illustrative scenario data, served by the API. Not live Snowflake telemetry. SMARTS is not connected.',
    ['The authored Technology Risk scenario'],
    ['Readings, trends, and seeded investigations'],
    ['Kept separate from Data Quality', 'Organization contribution exists only where the scenario supplied it'],
  ),
  pocNode(
    'snowflake',
    'Snowflake',
    'Data Quality',
    'implemented',
    258,
    228,
    'The live Data Quality store: control results, desk rows, exceptions, events, and commentary from the supplied workbook.',
    ['Stored Data Quality records'],
    ['The facts an investigation is allowed to cite'],
    ['Read by the API, not by the browser', 'SMARTS is not the source of these rows'],
  ),
  pocNode(
    'jobs',
    'Investigation jobs',
    'Investigation',
    'implemented',
    504,
    228,
    'A new investigation is accepted and runs asynchronously. The screen polls until it completes or fails.',
    ['An investigation request'],
    ['A running, completed, or failed status'],
    ['Two investigations can run at once', 'Leaving the page does not cancel the run'],
  ),
  pocNode(
    'agent',
    'Cortex Agent',
    'Investigation',
    'implemented',
    750,
    228,
    'The published Snowflake Cortex Agent drafts the investigation narrative from the facts the API retrieved.',
    ['The facts for one control'],
    ['A draft narrative'],
    ['Used for Data Quality investigations and summaries', 'Not used for Technology Risk'],
  ),
  pocNode(
    'validate',
    'Result check',
    'Investigation',
    'implemented',
    996,
    228,
    'The narrative is accepted only when its control, dates, counts, and status match the retrieved facts.',
    ['The draft narrative and the retrieved facts'],
    ['An accepted narrative, or a rejected run'],
    ['A rejected run does not replace a completed investigation', 'The screen says when a run did not finish'],
  ),
  pocNode(
    'ledger',
    'Result cache',
    'Investigation',
    'implemented',
    750,
    360,
    'A completed investigation is stored in Snowflake. Opening that control again returns the saved result.',
    ['An accepted investigation'],
    ['The cached investigation the UI shows'],
    ['A saved result is labelled Cached', 'Run again starts a new investigation and keeps the saved one until the new one finishes'],
  ),
]

const pocEdges: ArchEdge[] = [
  edge('p1', 'user', 'frontend', 'opens', 'control', 'implemented', 'right', 'left'),
  edge('p2', 'frontend', 'gateway', 'HTTPS', 'control', 'implemented', 'right', 'left'),
  edge('p3', 'gateway', 'api', 'routes', 'control', 'implemented', 'right', 'left'),
  edge('p4', 'api', 'tr', 'scenario', 'data', 'implemented', 'right', 'left'),
  edge('p5', 'api', 'snowflake', 'reads', 'data', 'implemented', 'bottom', 'top'),
  edge('p6', 'api', 'jobs', 'start', 'async', 'implemented', 'bottom', 'top'),
  edge('p7', 'jobs', 'agent', 'draft', 'async', 'implemented', 'right', 'left'),
  edge('p8', 'agent', 'validate', 'check', 'control', 'implemented', 'right', 'left'),
  edge('p9', 'validate', 'ledger', 'store', 'data', 'implemented', 'bottom', 'top'),
  edge('p10', 'ledger', 'frontend', 'poll', 'control', 'implemented', 'left', 'left', 'west'),
]

export const pocGraph: ArchGraph = {
  id: 'poc',
  title: 'POC Design',
  lede: 'The UI on Cloudflare Pages calls the API on the Oracle Cloud VM. Data Quality is read from Snowflake. A Cortex Agent drafts investigations, the API checks them, and completed results are cached. Technology Risk is illustrative. SMARTS is not connected.',
  walkthrough: 'Trace a Data Quality investigation',
  width: POC_W,
  height: POC_H,
  bands: [
    { label: 'What you use', x: 8, y: 12, w: 1184, h: 176, tone: 'implemented' },
    { label: 'Data Quality investigation', x: 8, y: 200, w: 1184, h: 256, tone: 'implemented' },
  ],
  nodes: pocNodes,
  edges: pocEdges,
  initialNodeId: 'frontend',
  requester: ['user', 'frontend'],
  steps: [
    {
      badge: 'Data Quality',
      title: 'Open an investigation',
      caption: 'A stakeholder opens a Data Quality control from the dashboard, triage, or register.',
      nodes: ['user', 'frontend'],
      journey: 'data-quality',
    },
    {
      badge: 'Data Quality',
      title: 'Call the API over HTTPS',
      caption: 'The page on Cloudflare Pages calls the public API. The reverse proxy on the VM forwards it to the backend.',
      nodes: ['frontend', 'gateway', 'api'],
      journey: 'data-quality',
    },
    {
      badge: 'Data Quality',
      title: 'Read the Snowflake facts',
      caption: 'The API reads the control result, history, desks, exceptions, and notes from Snowflake.',
      nodes: ['api', 'snowflake'],
      journey: 'data-quality',
    },
    {
      badge: 'Data Quality',
      title: 'Accept the job',
      caption: 'A new investigation is accepted and runs in the background. The page keeps showing that it is working.',
      nodes: ['api', 'jobs'],
      journey: 'data-quality',
    },
    {
      badge: 'Data Quality',
      title: 'Draft the findings',
      caption: 'The Cortex Agent writes the narrative from the facts that were retrieved.',
      nodes: ['jobs', 'agent'],
      active: ['agent'],
      waiting: ['jobs'],
      journey: 'data-quality',
    },
    {
      badge: 'Data Quality',
      title: 'Check the narrative',
      caption: 'Cited controls, dates, counts, and status have to match the retrieved facts. A rejected run does not replace a saved investigation.',
      nodes: ['agent', 'validate'],
      waiting: ['jobs'],
      journey: 'data-quality',
    },
    {
      badge: 'Data Quality',
      title: 'Save the result',
      caption: 'An accepted investigation is stored so the next open can retrieve it.',
      nodes: ['validate', 'ledger'],
      waiting: ['jobs'],
      journey: 'data-quality',
    },
    {
      badge: 'Data Quality',
      title: 'Show the result',
      caption: 'The page polls until the run finishes, then renders the saved investigation. A later open retrieves that result.',
      nodes: ['ledger', 'frontend', 'api'],
      active: ['frontend', 'user'],
      journey: 'data-quality',
    },
    {
      badge: 'Technology Risk',
      title: 'Illustrative scenario',
      caption: 'Technology Risk readings and investigations come from illustrative scenario data served by the API. They are not live Snowflake telemetry, and SMARTS is not connected.',
      nodes: ['frontend', 'api', 'tr'],
      active: ['api', 'tr'],
      journey: 'technology-risk',
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
  proposedNode('client', 'Metrics Analyzer UI', 'API', 0, 4, 'The React application on Cloudflare Pages. It calls the backend over HTTPS and polls investigation status.', ['Stakeholder actions', 'API responses and job status'], ['Dashboard, register, and investigation screens'], ['Running in this POC', 'Does not query Snowflake or Cortex from the browser'], 'implemented'),
  proposedNode('api-auth', 'Auth boundary', 'API', 1, 4, 'Request authentication, authorization, and validation before any data or model call.', ['Frontend requests'], ['Authorized, validated calls'], ['Proposed. No live identity provider is wired', 'Data boundaries apply here']),
  proposedNode('api-sync', 'Sync metric API', 'API', 2, 4, 'Ordinary overview and metric queries. This path is synchronous and is what the dashboard uses today.', ['Read requests'], ['Portfolio, metric, and trend responses'], ['Dashboard reads do not start an investigation', 'Running in this POC'], 'implemented'),
  proposedNode('job-submit', 'Job submission', 'Async investigations', 0, 5, 'Accepts a long investigation and returns a run id. The UI polls that run until it completes or fails.', ['An investigation request'], ['Run id and initial status'], ['Separate from a dashboard read', 'Running in this POC'], 'implemented'),
  proposedNode('job-queue', 'Queue', 'Async investigations', 1, 5, 'Holds investigation work off the request path so a slow analysis cannot block the UI.', ['Submitted jobs'], ['Work items for a bounded pool'], ['Proposed. No separate queue product is deployed']),
  proposedNode('job-workers', 'Workers', 'Async investigations', 2, 5, 'The API runs analysis with a concurrency limit of two, a timeout, and a check that cited figures were retrieved.', ['Accepted jobs'], ['A checked narrative, or a failed run'], ['Running in this POC', 'A failed check does not replace a saved investigation'], 'implemented'),
  proposedNode('job-dead', 'Dead letter', 'Async investigations', 3, 5, 'Holds jobs that still fail after retries so they can be seen and replayed without silent success.', ['Exhausted failures'], ['A visible failed job'], ['Failure stays failed', 'Proposed. The POC records a failed run, without a separate replay queue']),
  proposedNode('job-result', 'Persisted result', 'Async investigations', 4, 5, 'Stores the completed investigation in Snowflake. A later request returns that cached result.', ['Completed findings'], ['A result the UI can poll and reopen'], ['Running in this POC', 'The browser does not wait on the worker'], 'implemented'),
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
  lede: 'A fuller production shape. Boxes marked implemented are running in this POC. The rest are proposals and are not deployed.',
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
  requester: ['client'],
  steps: [
    {
      badge: 'Synchronous read',
      title: 'Dashboard request',
      caption: 'An ordinary portfolio or metric query is authenticated and answered on the request path. It is not placed on the investigation queue.',
      nodes: ['client', 'api-auth', 'api-sync'],
      journey: 'sync-read',
    },
    {
      badge: 'Synchronous read',
      title: 'Governed metric read',
      caption: 'The API reads curated data through the semantic model. The browser does not query Snowflake.',
      nodes: ['api-sync', 'sf-semantic', 'sf-curated'],
      active: ['sf-semantic', 'sf-curated'],
      waiting: ['api-sync'],
      journey: 'sync-read',
    },
    {
      badge: 'Asynchronous investigation',
      title: 'Submit a job',
      caption: 'A multi-step investigation returns a run id. This POC runs two investigations at a time. A separate queue product is still a proposal.',
      nodes: ['client', 'job-submit', 'job-queue'],
      journey: 'investigation',
    },
    {
      badge: 'Asynchronous investigation',
      title: 'Analyst and Agents',
      caption: 'Workers call Agents. Agents call Analyst and evidence tools through the tool interface. The two Cortex capabilities stay distinct.',
      nodes: ['job-workers', 'ai-tools', 'ai-agents', 'ai-analyst'],
      active: ['ai-tools', 'ai-agents', 'ai-analyst'],
      waiting: ['job-workers'],
      journey: 'investigation',
    },
    {
      badge: 'Asynchronous investigation',
      title: 'Result or failure',
      caption: 'A finished result is stored for the UI to poll. Retries that still fail land on the dead-letter path and stay failed.',
      nodes: ['job-workers', 'job-result', 'job-dead', 'client'],
      active: ['job-result', 'job-dead', 'client'],
      journey: 'investigation',
    },
    {
      badge: 'Proposed controls',
      title: 'Checks, audit, and fallback',
      caption: 'The POC checks that a narrative cites retrieved figures. Formal evaluations, access review, audit, and telemetry remain proposals. A gap is reported rather than shown as healthy.',
      nodes: ['safe-checks', 'safe-ground', 'safe-eval', 'safe-access', 'safe-fallback', 'ops-audit', 'ops-observe'],
      journey: 'safeguards',
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
