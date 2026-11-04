import type { ArchGraph } from './model'

export type JourneyRole = 'requester' | 'waiting' | 'active' | 'done'
export type EdgeRole = 'active' | 'done'

export interface JourneyView {
  roles: Map<string, JourneyRole>
  edges: Map<string, EdgeRole>
  stepping: boolean
}

const EMPTY: JourneyView = { roles: new Map(), edges: new Map(), stepping: false }

/** Cumulative path for the walkthrough. A new `journey` id clears what counts as completed. */
export function journeyState(graph: ArchGraph, stepIndex: number): JourneyView {
  const current = graph.steps[stepIndex]
  if (!current) return EMPTY
  const journey = current.journey ?? 'main'
  let start = stepIndex
  while (start > 0 && (graph.steps[start - 1].journey ?? 'main') === journey) start -= 1

  const roles = new Map<string, JourneyRole>()
  const edges = new Map<string, EdgeRole>()
  for (let index = start; index < stepIndex; index += 1) {
    for (const id of graph.steps[index].nodes) roles.set(id, 'done')
    markEdges(graph, graph.steps[index].nodes, 'done', edges)
  }

  const active = new Set(current.active ?? current.nodes)
  const waiting = new Set(current.waiting ?? [])
  for (const id of waiting) roles.set(id, 'waiting')
  for (const id of active) {
    if (roles.get(id) !== 'waiting') roles.set(id, 'active')
  }
  for (const id of graph.requester) {
    const role = roles.get(id)
    if (role !== 'active' && role !== 'waiting') roles.set(id, 'requester')
  }
  markEdges(graph, current.nodes, 'active', edges)
  return { roles, edges, stepping: true }
}

function markEdges(graph: ArchGraph, nodes: string[], role: EdgeRole, edges: Map<string, EdgeRole>) {
  const present = new Set(nodes)
  for (const edge of graph.edges) {
    if (!present.has(edge.from) || !present.has(edge.to)) continue
    if (role === 'done' && edges.get(edge.id) === 'active') continue
    edges.set(edge.id, role)
  }
}
