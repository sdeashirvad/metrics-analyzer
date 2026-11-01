import { useCallback, useEffect, useRef, useState } from 'react'
import { PageHeader } from '../../components/ui/PageHeader'
import { ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { TabPanel, Tabs } from '../../components/ui/Tabs'
import { useUrlState } from '../../hooks/useUrlState'
import { ArchitectureDiagram, ArchitectureList } from './ArchitectureDiagram'
import { DetailPanel } from './DetailPanel'
import { journeyState } from './journey'
import { kindLabel, pocGraph, proposedGraph, statusLabel, type ArchGraph } from './model'
import { Walkthrough } from './Walkthrough'

type TabId = ArchGraph['id']

function useNarrowArchitecture() {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 1180px)').matches)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 1180px)')
    const apply = () => setNarrow(query.matches)
    apply()
    query.addEventListener('change', apply)
    return () => query.removeEventListener('change', apply)
  }, [])
  return narrow
}

function compactDiagram() {
  const scene = document.querySelector<HTMLElement>('.arch-scene')
  return !scene || getComputedStyle(scene).display === 'none'
}

function ArchitectureLegend() {
  return (
    <div className="arch-legend-block">
      <div className="arch-legend-group">
        <span className="arch-legend-label">Component status</span>
        <ul className="arch-legend" aria-label="Component status">
          <li><i className="arch-key is-implemented" /> {statusLabel('implemented')}</li>
          <li><i className="arch-key is-upcoming" /> {statusLabel('upcoming')}</li>
          <li><i className="arch-key is-proposed" /> {statusLabel('proposed')}</li>
        </ul>
      </div>
      <div className="arch-legend-group">
        <span className="arch-legend-label">Connections</span>
        <ul className="arch-legend" aria-label="Connections">
          <li><i className="arch-key edge-data" /> {kindLabel('data')}</li>
          <li><i className="arch-key edge-control" /> {kindLabel('control')}</li>
          <li><i className="arch-key edge-async" /> {kindLabel('async')}</li>
        </ul>
      </div>
      <div className="arch-legend-group">
        <span className="arch-legend-label">Walkthrough</span>
        <ul className="arch-legend" aria-label="Walkthrough">
          <li><i className="arch-key is-role-requester" /> Requester</li>
          <li><i className="arch-key is-role-waiting" /> Waiting on a child process</li>
          <li><i className="arch-key is-role-active" /> Active step</li>
          <li><i className="arch-key is-role-done" /> Completed</li>
        </ul>
      </div>
    </div>
  )
}

function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function ArchitecturePage() {
  const [params, update] = useUrlState()
  const tab: TabId = params.get('tab') === 'proposed' ? 'proposed' : 'poc'
  const [selected, setSelected] = useState({ poc: pocGraph.initialNodeId, proposed: proposedGraph.initialNodeId })
  const [stepIndex, setStepIndex] = useState({ poc: -1, proposed: -1 })
  const [held, setHeld] = useState(false)
  const follow = useRef(false)
  const graph = tab === 'poc' ? pocGraph : proposedGraph
  const step = stepIndex[tab]
  const journey = journeyState(graph, step)
  const selectedNode = graph.nodes.find((node) => node.id === selected[tab]) ?? graph.nodes[0]

  const onStep = useCallback(
    (next: number) => {
      follow.current = true
      setStepIndex((current) => ({ ...current, [tab]: next }))
      const nodes = graph.steps[next]?.nodes
      if (nodes?.[0] && !compactDiagram()) setSelected((current) => ({ ...current, [tab]: nodes[0] }))
    },
    [graph.steps, tab],
  )

  useEffect(() => {
    if (!follow.current) return
    follow.current = false
    if (step < 0) return
    const narrow = compactDiagram()
    const scope = document.getElementById(narrow ? `arch-list-${tab}` : `arch-scene-${tab}`)
    if (!scope) return
    const targets = [...scope.querySelectorAll<HTMLElement>('.is-role-active')]
    if (!targets.length) return
    const rects = targets.map((node) => node.getBoundingClientRect())
    const top = Math.min(...rects.map((rect) => rect.top))
    const bottom = Math.max(...rects.map((rect) => rect.bottom))
    const sidebar = document.querySelector('.sidebar')
    const stickyTop = sidebar && getComputedStyle(sidebar).position === 'sticky' && narrow ? sidebar.getBoundingClientRect().bottom : 0
    const dock = document.querySelector('.arch-dock')
    const dockHeight = dock ? dock.getBoundingClientRect().height + 24 : 0
    const viewTop = stickyTop + 12
    const viewBottom = window.innerHeight - dockHeight
    let delta = 0
    if (top < viewTop) delta = top - viewTop
    else if (bottom > viewBottom) delta = Math.min(bottom - viewBottom, top - viewTop)
    if (Math.abs(delta) < 1) return
    window.scrollBy({ top: delta, behavior: reducedMotion() ? 'auto' : 'smooth' })
  }, [step, tab])

  const select = (id: string) => setSelected((current) => ({ ...current, [tab]: id }))
  const current = step >= 0 ? graph.steps[step] : null
  const waitingOn = (current?.waiting ?? [])
    .map((id) => graph.nodes.find((node) => node.id === id)?.label)
    .filter((label): label is string => Boolean(label))
  const narrow = useNarrowArchitecture()
  const detail = <DetailPanel node={selectedNode} />

  return (
    <div className="page page-wide architecture">
      <PageHeader
        title={graph.title}
        subtitle={graph.lede}
        chips={
          <>
            <ProvenanceChip kind={tab === 'poc' ? 'synthetic' : 'proposed'} label={tab === 'poc' ? 'Technology Risk is illustrative' : undefined} />
          </>
        }
      />
      <Tabs<TabId>
        label="Architecture views"
        idPrefix="arch"
        value={tab}
        onChange={(next) => update({ tab: next === 'poc' ? null : next }, { commit: false })}
        tabs={[
          { id: 'poc', label: 'POC Design' },
          { id: 'proposed', label: 'Proposed Design' },
        ]}
        className="arch-tabs"
      />
      <TabPanel idPrefix="arch" id={tab} className="arch-panel">
        <div className="arch-layout">
          <div className="arch-main">
            <ArchitectureDiagram
              graph={graph}
              selectedId={selected[tab]}
              roles={journey.roles}
              edgeRoles={journey.edges}
              stepping={journey.stepping}
              stepNumber={step + 1}
              onSelect={select}
              onHold={setHeld}
            />
            <ArchitectureList
              graph={graph}
              selectedId={selected[tab]}
              roles={journey.roles}
              edgeRoles={journey.edges}
              stepping={journey.stepping}
              stepNumber={step + 1}
              onSelect={select}
              detail={narrow ? detail : null}
            />
          </div>
          {!narrow && <div className="arch-side">{detail}</div>}
        </div>
        <ArchitectureLegend />
        <Walkthrough key={tab} title={graph.walkthrough} steps={graph.steps} step={step} onStep={onStep} held={held} />
      </TabPanel>
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {current ? `Step ${step + 1}: ${current.title}${waitingOn.length ? `. Waiting on ${waitingOn.join(', ')}` : ''}` : ''}
      </p>
    </div>
  )
}
