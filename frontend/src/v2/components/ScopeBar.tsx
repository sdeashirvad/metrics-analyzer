import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { getFilters } from '../api/portfolio'
import type { ScopeFilters } from '../api/types'
import { formatMonth } from '../format'
import { useApiQuery } from '../hooks/useApiQuery'
import { useScopeFilters } from '../hooks/useScopeFilters'
import { MenuSelect } from './MenuSelect'
import { legalEntityLabel, useLegalEntityNames } from './scopeLabels'

export function ScopeBar({ search, extra }: { mode?: 'full' | 'compact'; search?: ReactNode; extra?: ReactNode }) {
  const { filters, replaceScope } = useScopeFilters()
  const catalog = useApiQuery('filters', 'catalog', getFilters)
  const names = useLegalEntityNames()
  const [more, setMore] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const treeKey = filters.orgTree ?? 'BUSINESS_ORG'
  const tree = catalog.data?.orgTrees[treeKey]
  const l2 = tree?.level2.filter((child) => !filters.l1?.length || filters.l1.includes(child.parent)) ?? []

  const advancedCount =
    (filters.l1?.length ?? 0) +
    (filters.l2?.length ?? 0) +
    (filters.legalEntity?.length ?? 0) +
    (filters.tier?.length ?? 0) +
    (filters.risk?.length ?? 0) +
    (filters.lifecycle?.length ?? 0) +
    (filters.ma ? 1 : 0)

  function patch(next: ScopeFilters) {
    replaceScope(next)
  }

  useEffect(() => {
    if (!more) return
    const button = buttonRef.current
    const panel = panelRef.current
    if (!button || !panel) return
    const place = () => {
      const rect = button.getBoundingClientRect()
      const width = Math.min(560, window.innerWidth - 24)
      const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))
      panel.style.top = `${Math.min(rect.bottom + 8, window.innerHeight - 16)}px`
      panel.style.left = `${left}px`
      panel.style.width = `${width}px`
      panel.style.maxHeight = `${Math.max(220, window.innerHeight - rect.bottom - 24)}px`
    }
    place()
    const close = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (panel.contains(target) || button.contains(target)) return
      setMore(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMore(false)
    }
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', onKey)
    }
  }, [more])

  const months = catalog.data?.months.map((item) => ({ value: item.month, label: formatMonth(item.month) })) ?? []
  const chips = [
    ...(filters.l1 ?? []).map((value) => ({ key: `l1-${value}`, label: value, clear: () => patch({ ...filters, l1: filters.l1?.filter((item) => item !== value), l2: undefined }) })),
    ...(filters.l2 ?? []).map((value) => ({ key: `l2-${value}`, label: value, clear: () => patch({ ...filters, l2: filters.l2?.filter((item) => item !== value) }) })),
    ...(filters.legalEntity ?? []).map((value) => ({ key: `le-${value}`, label: legalEntityLabel(value, names), clear: () => patch({ ...filters, legalEntity: filters.legalEntity?.filter((item) => item !== value) }) })),
    ...(filters.tier ?? []).map((value) => ({ key: `tier-${value}`, label: `Tier ${value}`, clear: () => patch({ ...filters, tier: filters.tier?.filter((item) => item !== value) }) })),
    ...(filters.risk ?? []).map((value) => ({ key: `risk-${value}`, label: value, clear: () => patch({ ...filters, risk: filters.risk?.filter((item) => item !== value) }) })),
    ...(filters.lifecycle ?? []).map((value) => ({ key: `life-${value}`, label: value, clear: () => patch({ ...filters, lifecycle: filters.lifecycle?.filter((item) => item !== value) }) })),
    ...(filters.ma ? [{ key: 'ma', label: `M&A ${filters.ma}`, clear: () => patch({ ...filters, ma: undefined }) }] : []),
  ]

  return (
    <div className="toolbar">
      {search}
      <div className="field">
        <span className="field-label">Month</span>
        <MenuSelect label="Month" emptyLabel="Latest" options={months} selected={filters.month ? [filters.month] : []} onChange={(next) => patch({ ...filters, month: next[0] })} />
      </div>
      <div className="seg" role="group" aria-label="Organisation tree">
        <button type="button" className={treeKey === 'BUSINESS_ORG' ? 'on' : ''} onClick={() => patch({ ...filters, orgTree: undefined, l1: undefined, l2: undefined })}>
          Business org
        </button>
        <button type="button" className={treeKey === 'BU' ? 'on' : ''} onClick={() => patch({ ...filters, orgTree: 'BU', l1: undefined, l2: undefined })}>
          Bank group
        </button>
      </div>
      <button
        ref={buttonRef}
        type="button"
        className={`btn btn-sm${more ? ' is-open' : ''}${advancedCount ? ' is-selected' : ''}`}
        aria-expanded={more}
        aria-controls={titleId}
        onClick={() => setMore((value) => !value)}
      >
        {advancedCount ? `More filters · ${advancedCount}` : 'More filters'}
      </button>
      {advancedCount > 0 && (
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => replaceScope({ month: filters.month, orgTree: filters.orgTree })}>
          Clear filters
        </button>
      )}
      {extra}
      {chips.length > 0 && (
        <div className="filter-chips">
          {chips.map((chip) => (
            <button key={chip.key} type="button" className="ctxchip chip-x" onClick={chip.clear} aria-label={`Remove filter ${chip.label}`}>
              {chip.label}
              <span aria-hidden="true"> ×</span>
            </button>
          ))}
        </div>
      )}
      {more &&
        catalog.data &&
        tree &&
        createPortal(
          <div ref={panelRef} id={titleId} className="filter-panel" role="dialog" aria-label="More filters">
            <div className="filter-grid">
              <div className="field">
                <span className="field-label">{tree.level1Label}</span>
                <MenuSelect
                  label={tree.level1Label}
                  multiple
                  options={tree.level1.map((item) => ({ value: item.value, label: item.value }))}
                  selected={filters.l1 ?? []}
                  onChange={(next) => patch({ ...filters, l1: next.length ? next : undefined, l2: undefined })}
                />
              </div>
              <div className="field">
                <span className="field-label">{tree.level2Label}</span>
                <MenuSelect
                  label={tree.level2Label}
                  multiple
                  options={l2.map((item) => ({ value: item.value, label: item.value }))}
                  selected={filters.l2 ?? []}
                  onChange={(next) => patch({ ...filters, l2: next.length ? next : undefined })}
                />
              </div>
              <div className="field">
                <span className="field-label">Legal entity</span>
                <MenuSelect
                  label="Legal entity"
                  multiple
                  options={catalog.data.legalEntities.map((item) => ({ value: item.code, label: item.name, detail: item.code }))}
                  selected={filters.legalEntity ?? []}
                  onChange={(next) => patch({ ...filters, legalEntity: next.length ? next : undefined })}
                />
              </div>
              <div className="field">
                <span className="field-label">Tier</span>
                <MenuSelect
                  label="Tier"
                  multiple
                  options={catalog.data.tiers.map((item) => ({ value: String(item), label: String(item) }))}
                  selected={(filters.tier ?? []).map(String)}
                  onChange={(next) => patch({ ...filters, tier: next.length ? next.map(Number) : undefined })}
                />
              </div>
              <div className="field">
                <span className="field-label">Risk</span>
                <MenuSelect
                  label="Risk"
                  multiple
                  options={catalog.data.risks.map((item) => ({ value: item, label: item }))}
                  selected={filters.risk ?? []}
                  onChange={(next) => patch({ ...filters, risk: next.length ? next : undefined })}
                />
              </div>
              <div className="field">
                <span className="field-label">Lifecycle</span>
                <MenuSelect
                  label="Lifecycle"
                  multiple
                  options={catalog.data.lifecycles.map((item) => ({ value: item, label: item }))}
                  selected={filters.lifecycle ?? []}
                  onChange={(next) => patch({ ...filters, lifecycle: next.length ? next : undefined })}
                />
              </div>
              <div className="field">
                <span className="field-label">M&A</span>
                <MenuSelect
                  label="M&A"
                  emptyLabel="Any"
                  options={catalog.data.maOptions.map((item) => ({ value: item, label: item }))}
                  selected={filters.ma ? [filters.ma] : []}
                  onChange={(next) => patch({ ...filters, ma: next[0] === 'Y' || next[0] === 'N' ? next[0] : undefined })}
                />
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  )
}
