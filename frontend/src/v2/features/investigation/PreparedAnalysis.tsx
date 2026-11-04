import type { ReactNode } from 'react'
import type { AgentAnalysisRef } from '../../api/types'
import { Markdown } from '../../components/markdown'
export interface PreparedView {
  text: string
  generatedAt: string
  dataAsOf: string | null
  limitation: string | null
  datasetVersion: string
  definitionsVersion: string
  agent: string | null
}

/** Prepared narrative text for a read-only view. Returns null when nothing usable was prepared. */
export function preparedText(analysis: AgentAnalysisRef): PreparedView | null {
  const prepared = analysis.precomputed
  const content = prepared?.content
  if (analysis.status !== 'FALLBACK_STATIC' || !prepared || prepared.stale || !content || content.kind !== 'analysis') return null
  const text = content.text.trim()
  if (!text) return null
  return {
    text,
    generatedAt: prepared.generatedAt,
    dataAsOf: prepared.dataAsOf ?? prepared.month ?? null,
    datasetVersion: prepared.datasetVersion,
    definitionsVersion: prepared.definitionsVersion,
    agent: prepared.agentSpecVersion ? 'Analysis Agent' : null,
    // The raw list of untied figures is not useful to a reader, so the note says what that means.
    limitation:
      prepared.sourceFactValidation === 'PARTIAL'
        ? 'Headline figures match the portfolio data. Other figures come from the Agent’s own queries and were not independently checked.'
        : null,
  }
}

const SECTION = /^\s*(?:\*\*\s*\d+\.|#{2,6}\s)/

/**
 * Split an analysis into the main finding and the supporting detail.
 * The finding is the title-less text before the second numbered or headed section.
 */
export function splitAnalysis(text: string): { finding: string; detail: string } {
  const lines = text.split('\n')
  const body = lines[0]?.startsWith('# ') ? lines.slice(1) : lines
  const starts: number[] = []
  body.forEach((line, index) => {
    if (SECTION.test(line)) starts.push(index)
  })
  if (starts.length < 2) return { finding: body.join('\n').trim(), detail: '' }
  const cut = starts[1]
  return { finding: body.slice(0, cut).join('\n').trim(), detail: body.slice(cut).join('\n').trim() }
}

function shortDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

/**
 * Read-only. No composer, selector, follow-up, history or polling.
 * Conversation with the Agent happens only in the Agent workspace.
 */
export function PreparedAnalysis({
  analysis,
  emptyText,
  title = 'AI Investigation',
}: {
  analysis: AgentAnalysisRef
  /** Shown instead of the note when none was prepared for this scope. Omit to render nothing. */
  emptyText?: ReactNode
  title?: string
}) {
  const prepared = preparedText(analysis)
  if (!prepared) {
    if (!emptyText) return null
    return (
      <section className="card prepared-analysis" aria-labelledby="ai-investigation-title">
        <div className="card-head">
          <h2 id="ai-investigation-title">{title}</h2>
        </div>
        <p className="fine">{emptyText}</p>
      </section>
    )
  }
  const { finding, detail } = splitAnalysis(prepared.text)
  return (
    <section className="card prepared-analysis" aria-labelledby="ai-investigation-title">
      <div className="card-head">
        <h2 id="ai-investigation-title">{title}</h2>
        <span className="chip prepared-badge">Prepared · Agent-generated</span>
      </div>
      <p className="asof">
        {prepared.dataAsOf ? `Data as of ${shortDate(prepared.dataAsOf)} · ` : ''}Generated {shortDate(prepared.generatedAt)}
        {prepared.agent ? ` · ${prepared.agent}` : ''} · dataset {prepared.datasetVersion} · definitions {prepared.definitionsVersion}.
        Hypotheses are not established.
      </p>
      <Markdown text={finding} />
      {detail && (
        <details className="prepared-detail">
          <summary>Evidence, contributors and limitations</summary>
          <Markdown text={detail} />
        </details>
      )}
      {prepared.limitation && <p className="fine">{prepared.limitation}</p>}
    </section>
  )
}
