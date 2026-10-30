import { useCallback, useEffect, useRef, useState } from 'react'
import { PageHeader } from '../../components/ui/PageHeader'
import { ProvenanceChip } from '../../components/ui/ProvenanceChip'
import { TabPanel, Tabs } from '../../components/ui/Tabs'
import { useUrlState } from '../../hooks/useUrlState'
import { ArchitectureDiagram, ArchitectureList } from './ArchitectureDiagram'
import { DetailPanel } from './DetailPanel'
import { kindLabel, pocGraph, proposedGraph, statusLabel, type ArchGraph } from './model'
import { Walkthrough } from './Walkthrough'

type TabId = ArchGraph['id']

function compactDiagram() {
  const scene = document.querySelector<HTMLElement>('.arch-scene')
  return !scene || getComputedStyle(scene).display === 'none'
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
  const traced = step >= 0 ? graph.steps[step].nodes : []
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
    const targets = [...scope.querySelectorAll<HTMLElement>('.is-traced')]
    if (!targets.length) return
    const rects = (narrow ? targets.slice(0, 1) : targets).map((node) => node.getBoundingClientRect())
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

  return (
    <div className="page page-wide architecture">
      <PageHeader
        title={graph.title}
        subtitle={graph.lede}
        chips={
          <>
            <ProvenanceChip kind={tab === 'poc' ? 'synthetic' : 'proposed'} label={tab === 'poc' ? 'Running in this demo · mocked data' : undefined} />
            <span className="fine">Target architecture is not a live integration. Snowflake, Cortex, and SMARTS are not connected. Solid nodes are what this prototype runs.</span>
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
        <ul className="arch-legend" aria-label="Legend">
          <li><i className="arch-key is-implemented" /> {statusLabel('implemented')}</li>
          <li><i className="arch-key is-upcoming" /> {statusLabel('upcoming')}</li>
          <li><i className="arch-key is-proposed" /> {statusLabel('proposed')}</li>
          <li><i className="arch-key edge-data" /> {kindLabel('data')}</li>
          <li><i className="arch-key edge-control" /> {kindLabel('control')}</li>
          <li><i className="arch-key edge-async" /> {kindLabel('async')}</li>
          <li><i className="arch-key is-traced-key" /> Highlighted by the walkthrough</li>
        </ul>
        <div className="arch-layout">
          <div className="arch-main">
            <ArchitectureDiagram
              graph={graph}
              selectedId={selected[tab]}
              traced={traced}
              stepNumber={step + 1}
              onSelect={select}
              onHold={setHeld}
            />
            <ArchitectureList graph={graph} selectedId={selected[tab]} traced={traced} stepNumber={step + 1} onSelect={select} detail={<DetailPanel node={selectedNode} />} />
            <Walkthrough key={tab} title={graph.walkthrough} steps={graph.steps} step={step} onStep={onStep} held={held} />
          </div>
          <div className="arch-side">
            <DetailPanel node={selectedNode} />
          </div>
        </div>
      </TabPanel>
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {current ? `Step ${step + 1}: ${current.title}` : ''}
      </p>
    </div>
  )
}
