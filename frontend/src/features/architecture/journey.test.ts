import { describe, expect, it } from 'vitest'
import { journeyState } from './journey'
import { pocGraph, proposedGraph } from './model'

describe('journeyState', () => {
  it('draws nothing before the walkthrough starts', () => {
    const view = journeyState(pocGraph, -1)
    expect(view.stepping).toBe(false)
    expect(view.roles.size).toBe(0)
    expect(view.edges.size).toBe(0)
  })

  it('marks the opening request active', () => {
    const view = journeyState(pocGraph, 0)
    expect(view.roles.get('user')).toBe('active')
    expect(view.roles.get('frontend')).toBe('active')
    expect(view.edges.get('p1')).toBe('active')
    expect(view.edges.has('p2')).toBe(false)
  })

  it('keeps the requester visible and the earlier path completed', () => {
    const view = journeyState(pocGraph, 2)
    expect(view.roles.get('api')).toBe('active')
    expect(view.roles.get('snowflake')).toBe('active')
    expect(view.roles.get('user')).toBe('requester')
    expect(view.roles.get('frontend')).toBe('requester')
    expect(view.roles.get('gateway')).toBe('done')
    expect(view.edges.get('p5')).toBe('active')
    expect(view.edges.get('p1')).toBe('done')
    expect(view.edges.get('p3')).toBe('done')
  })

  it('shows the job as waiting while the agent is drafting', () => {
    const view = journeyState(pocGraph, 4)
    expect(view.roles.get('agent')).toBe('active')
    expect(view.roles.get('jobs')).toBe('waiting')
    expect(view.roles.get('snowflake')).toBe('done')
    expect(view.roles.get('user')).toBe('requester')
    expect(view.edges.get('p7')).toBe('active')
  })

  it('returns the result to the requester and leaves the cache on the completed path', () => {
    const view = journeyState(pocGraph, 7)
    expect(view.roles.get('frontend')).toBe('active')
    expect(view.roles.get('user')).toBe('active')
    expect(view.roles.get('ledger')).toBe('done')
    expect(view.roles.get('api')).toBe('done')
    expect(view.edges.get('p10')).toBe('active')
  })

  it('starts a new journey without the previous completed path', () => {
    const view = journeyState(pocGraph, 8)
    expect(view.roles.get('api')).toBe('active')
    expect(view.roles.get('tr')).toBe('active')
    expect(view.roles.get('frontend')).toBe('requester')
    expect(view.roles.get('user')).toBe('requester')
    expect(view.roles.has('snowflake')).toBe(false)
    expect(view.roles.has('jobs')).toBe(false)
    expect(view.edges.get('p4')).toBe('active')
    expect(view.edges.has('p5')).toBe(false)
  })

  it('keeps the proposed API waiting while the read is in Snowflake', () => {
    const view = journeyState(proposedGraph, 1)
    expect(view.roles.get('api-sync')).toBe('waiting')
    expect(view.roles.get('sf-semantic')).toBe('active')
    expect(view.roles.get('sf-curated')).toBe('active')
    expect(view.roles.get('client')).toBe('requester')
    expect(view.roles.get('api-auth')).toBe('done')
  })

  it('treats the safeguard step as its own journey', () => {
    const view = journeyState(proposedGraph, 5)
    expect(view.roles.get('safe-checks')).toBe('active')
    expect(view.roles.get('client')).toBe('requester')
    expect(view.roles.has('job-workers')).toBe(false)
    expect(view.edges.has('s23')).toBe(false)
  })
})
