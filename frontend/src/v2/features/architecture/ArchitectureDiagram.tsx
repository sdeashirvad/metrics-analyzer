import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import type { EdgeRole, JourneyRole } from './journey'
import type { ArchEdge, ArchGraph, ArchNode, Side } from './model'
import { statusShort } from './model'

interface Point {
  x: number
  y: number
}

interface ArchitectureDiagramProps {
  graph: ArchGraph
  selectedId: string
  roles: Map<string, JourneyRole>
  edgeRoles: Map<string, EdgeRole>
  stepping: boolean
  stepNumber: number
  onSelect: (id: string) => void
  onHold?: (held: boolean) => void
}

const LABEL_PX = 12

function useScale(graphWidth: number) {
  const ref = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  useEffect(() => {
    const node = ref.current
    if (!node) return
    const measure = () => {
      const width = node.getBoundingClientRect().width
      if (width > 0) setScale(width / graphWidth)
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [graphWidth])
  return [ref, scale] as const
}

function nodeClass(node: ArchNode, selectedId: string, role: JourneyRole | undefined, extra = '') {
  return ['arch-node', extra, `is-${node.status}`, node.id === selectedId ? 'is-selected' : '', role ? `is-role-${role}` : '']
    .filter(Boolean)
    .join(' ')
}

function StepMark({ role, stepNumber }: { role: JourneyRole | undefined; stepNumber: number }) {
  if (role === 'active') {
    return (
      <span className="arch-step-badge" aria-hidden="true">
        {stepNumber}
      </span>
    )
  }
  if (role === 'done') {
    return (
      <span className="arch-step-badge is-done" aria-hidden="true">
        ✓
      </span>
    )
  }
  return null
}

export function ArchitectureDiagram({ graph, selectedId, roles, edgeRoles, stepping, stepNumber, onSelect, onHold }: ArchitectureDiagramProps) {
  const [sceneRef, scale] = useScale(graph.width)
  const labelSize = LABEL_PX / scale
  const byId = new Map(graph.nodes.map((node) => [node.id, node]))
  const laneSlot = new Map<string, number>()
  const laneCount = { east: 0, west: 0 }
  for (const item of graph.edges) {
    if (!item.lane) continue
    laneSlot.set(item.id, laneCount[item.lane])
    laneCount[item.lane] += 1
  }

  return (
    <div
      ref={sceneRef}
      id={`arch-scene-${graph.id}`}
      className={`arch-scene${stepping ? ' is-stepping' : ''}`}
      style={{ aspectRatio: `${graph.width} / ${graph.height}`, '--arch-label': `${labelSize}px`, '--arch-halo': `${4 / scale}px` } as CSSProperties}
      onPointerEnter={() => onHold?.(true)}
      onPointerLeave={() => onHold?.(false)}
    >
      <svg
        className="arch-svg"
        viewBox={`0 0 ${graph.width} ${graph.height}`}
        aria-hidden="true"
      >
        <defs>
          <marker id={`${graph.id}-arrow`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M 0 1.2 L 8 5 L 0 8.8 z" className="arch-arrow" />
          </marker>
        </defs>
        {graph.bands.map((band) => (
          <g key={band.label}>
            <rect x={band.x} y={band.y} width={band.w} height={band.h} rx="10" className={`arch-band band-${band.tone}`} />
            <text x={band.x + 12} y={band.y + 6 + labelSize} className="arch-band-label">
              {band.label}
            </text>
          </g>
        ))}
        {graph.edges.map((item) => {
          const points = routeEdge(item, byId, graph.width, laneSlot.get(item.id) ?? 0)
          if (points.length < 2) return null
          const edgeRole = edgeRoles.get(item.id)
          const labelAt = longestMidpoint(points)
          return (
            <g key={item.id} className={edgeRole ? `arch-edge-group is-edge-${edgeRole}` : 'arch-edge-group'}>
              <path
                d={toPath(points)}
                className={`arch-edge edge-${item.kind} edge-${item.status}`}
                markerEnd={`url(#${graph.id}-arrow)`}
              />
              <text x={labelAt.x} y={labelAt.y - 6} textAnchor="middle" className="arch-edge-label">
                {item.label}
              </text>
            </g>
          )
        })}
      </svg>
      {graph.nodes.map((node) => (
        <button
          key={node.id}
          type="button"
          className={nodeClass(node, selectedId, roles.get(node.id))}
          style={nodeStyle(node, graph.width, graph.height)}
          aria-pressed={node.id === selectedId}
          onClick={() => onSelect(node.id)}
        >
          <StepMark role={roles.get(node.id)} stepNumber={stepNumber} />
          <span>{node.label}</span>
          <small>{statusShort(node.status)}</small>
        </button>
      ))}
    </div>
  )
}

export function ArchitectureList({
  graph,
  selectedId,
  roles,
  edgeRoles,
  stepping,
  stepNumber,
  onSelect,
  detail,
}: Omit<ArchitectureDiagramProps, 'onHold'> & { detail: ReactNode }) {
  const layers: string[] = []
  for (const node of graph.nodes) {
    if (!layers.includes(node.layer)) layers.push(node.layer)
  }
  const selectedLayer = graph.nodes.find((node) => node.id === selectedId)?.layer
  return (
    <div className={`arch-layers${stepping ? ' is-stepping' : ''}`} id={`arch-list-${graph.id}`}>
      {layers.map((layer) => (
        <section key={layer}>
          <h3>{layer}</h3>
          <div className="arch-layer-nodes">
            {graph.nodes
              .filter((node) => node.layer === layer)
              .map((node, index, layerNodes) => {
                const next = layerNodes[index + 1]
                const link = next ? graph.edges.find((edge) => edge.from === node.id && edge.to === next.id) : undefined
                const edgeRole = link ? edgeRoles.get(link.id) : undefined
                return (
                  <div key={node.id} className="arch-flow-item">
                    <button
                      type="button"
                      className={nodeClass(node, selectedId, roles.get(node.id), 'arch-node-flow')}
                      aria-pressed={node.id === selectedId}
                      onClick={() => onSelect(node.id)}
                    >
                      <StepMark role={roles.get(node.id)} stepNumber={stepNumber} />
                      <span>{node.label}</span>
                      <small>{statusShort(node.status)}</small>
                    </button>
                    {link && (
                      <div className={`arch-flow-link edge-${link.kind}${edgeRole ? ` is-edge-${edgeRole}` : ''}`}>
                        <span className="arch-flow-stem" aria-hidden="true" />
                        <span>{link.label}</span>
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
          {layer === selectedLayer && detail ? <div className="arch-inline-detail">{detail}</div> : null}
        </section>
      ))}
    </div>
  )
}

function nodeStyle(node: ArchNode, width: number, height: number) {
  return {
    left: `${(node.x / width) * 100}%`,
    top: `${(node.y / height) * 100}%`,
    width: `${(node.w / width) * 100}%`,
    height: `${(node.h / height) * 100}%`,
  }
}

function sidePoint(node: ArchNode, side: Side): Point {
  if (side === 'left') return { x: node.x, y: node.y + node.h / 2 }
  if (side === 'right') return { x: node.x + node.w, y: node.y + node.h / 2 }
  if (side === 'top') return { x: node.x + node.w / 2, y: node.y }
  return { x: node.x + node.w / 2, y: node.y + node.h }
}

function routeEdge(item: ArchEdge, nodes: Map<string, ArchNode>, width: number, slot: number): Point[] {
  const from = nodes.get(item.from)
  const to = nodes.get(item.to)
  if (!from || !to) return []
  if (item.lane) {
    const goingUp = to.y < from.y
    const start = sidePoint(from, goingUp ? 'top' : 'bottom')
    const end = sidePoint(to, goingUp ? 'bottom' : 'top')
    const exit = { x: start.x, y: goingUp ? from.y - 14 : from.y + from.h + 14 }
    const entry = { x: end.x, y: goingUp ? to.y + to.h + 14 : to.y - 14 }
    const laneX = item.lane === 'east' ? width - 8 - slot * 14 : 6 + slot * 14
    return [start, exit, { x: laneX, y: exit.y }, { x: laneX, y: entry.y }, entry, end]
  }
  const start = sidePoint(from, item.fromSide)
  const end = sidePoint(to, item.toSide)
  if (Math.abs(start.y - end.y) < 10) {
    if (Math.abs(end.x - start.x) > from.w) {
      const y = Math.max(from.y, to.y) + from.h + 12
      const left = sidePoint(from, 'bottom')
      const right = sidePoint(to, 'bottom')
      return [left, { x: left.x, y }, { x: right.x, y }, right]
    }
    return [start, end]
  }
  if (Math.abs(start.x - end.x) < 10) return [start, end]
  if (item.fromSide === 'top' || item.fromSide === 'bottom') {
    const midY = (start.y + end.y) / 2
    return [start, { x: start.x, y: midY }, { x: end.x, y: midY }, end]
  }
  const midX = (start.x + end.x) / 2
  return [start, { x: midX, y: start.y }, { x: midX, y: end.y }, end]
}

function toPath(points: Point[]): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
}

function longestMidpoint(points: Point[]): Point {
  let best = 0
  let bestLength = -1
  for (let index = 0; index < points.length - 1; index += 1) {
    const length = Math.hypot(points[index + 1].x - points[index].x, points[index + 1].y - points[index].y)
    if (length > bestLength) {
      best = index
      bestLength = length
    }
  }
  return {
    x: (points[best].x + points[best + 1].x) / 2,
    y: (points[best].y + points[best + 1].y) / 2,
  }
}
