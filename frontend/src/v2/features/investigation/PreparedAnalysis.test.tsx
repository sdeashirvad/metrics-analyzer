import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { AgentAnalysisRef } from '../../api/types'
import { PreparedAnalysis, preparedText, splitAnalysis } from './PreparedAnalysis'

function ref(overrides: Partial<AgentAnalysisRef> = {}, text = '## Summary\nRate is **44%**.'): AgentAnalysisRef {
  return {
    status: 'FALLBACK_STATIC',
    source: 'precomputed',
    conversationId: null,
    runId: null,
    messageId: null,
    generatedAt: null,
    stale: false,
    label: 'Agent-generated. Hypotheses are not established.',
    precomputed: {
      source: 'precomputed',
      target: { kind: 'metric', metricId: 'M1' },
      month: '2026-03-01' as never,
      generatedAt: '2026-03-10T10:00:00Z',
      datasetVersion: 'v1',
      definitionsVersion: 'd1',
      agentSpecVersion: null,
      stale: false,
      staleReason: null,
      label: 'x',
      content: {
        kind: 'analysis',
        text,
        evidence: [],
        toolActivity: [],
        suggestedFollowUps: ['Ask more'],
        notices: [],
        warnings: [{ code: 'MULTIPLE_QUERIES', message: 'More than one query was returned.' } as never],
      },
    },
    ...overrides,
  }
}

describe('PreparedAnalysis', () => {
  it('renders read-only prepared text with as-of and no controls', () => {
    const html = renderToStaticMarkup(<PreparedAnalysis analysis={ref()} />)
    expect(html).toContain('AI Investigation')
    expect(html).toContain('Prepared · Agent-generated')
    expect(html).toContain('Summary')
    expect(html).not.toContain('##')
    expect(html).toContain('dataset v1')
    expect(html).not.toContain('<textarea')
    expect(html).not.toContain('<button')
    expect(html).not.toContain('More than one query')
    expect(html).not.toContain('Ask more')
  })

  it('renders nothing when the analysis is stale, empty or not prepared', () => {
    expect(preparedText(ref({ status: 'NOT_RUN' }))).toBeNull()
    expect(preparedText(ref({}, '   '))).toBeNull()
    const stale = ref()
    stale.precomputed!.stale = true
    expect(preparedText(stale)).toBeNull()
    expect(renderToStaticMarkup(<PreparedAnalysis analysis={ref({ status: 'NOT_RUN' })} />)).toBe('')
  })
})


describe('splitAnalysis', () => {
  it('keeps the title out and puts the first section ahead of the evidence', () => {
    const text = '# Note\n\n**1. Executive finding**\nGreen.\n\n**2. Status**\n- a\n\n**3. Limits**\n- b'
    const { finding, detail } = splitAnalysis(text)
    expect(finding).toContain('Executive finding')
    expect(finding).not.toContain('# Note')
    expect(finding).not.toContain('Status')
    expect(detail.startsWith('**2. Status**')).toBe(true)
    expect(detail).toContain('Limits')
  })

  it('shows everything as the finding when there are no sections', () => {
    expect(splitAnalysis('Just one paragraph.')).toEqual({ finding: 'Just one paragraph.', detail: '' })
  })
})
