import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { getStatus } from '../api/portfolio'
import { formatMonth } from '../format'
import { useAnyStale, useApiQuery } from '../hooks/useApiQuery'
import { useScopeFilters } from '../hooks/useScopeFilters'

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? 'active' : undefined
}

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      {children}
    </svg>
  )
}

export function V2Shell() {
  const status = useApiQuery('status', 'portfolio', getStatus)
  const { filters } = useScopeFilters()
  const updating = useAnyStale()
  const data = status.data
  const latestLabel = data ? formatMonth(data.latestMonth) : ''
  const selectedLabel = filters.month ? formatMonth(filters.month) : null
  const period = selectedLabel || latestLabel
  const prepared = status.meta?.source === 'packaged'
  const statusText = data
    ? `Demo dataset · ${period}${prepared ? ' · prepared copy, live data is catching up' : ''}`
    : status.status === 'error'
      ? 'Status unavailable'
      : 'Loading status…'

  return (
    <div className="app">
      <a className="skip" href="#content">
        Skip to content
      </a>
      <aside className="sidebar">
        <div className="brand">
          <span className="mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="brand-copy">
            <span className="brand-name">Metrics Analyzer</span>
            <span className="brand-sub">Application compliance intelligence</span>
          </span>
        </div>
        <nav className="side-nav" aria-label="Primary">
          <NavLink to="/" end className={navClass}>
            <Icon>
              <rect x="3" y="3" width="8" height="8" rx="1.5" />
              <rect x="13" y="3" width="8" height="5" rx="1.5" />
              <rect x="13" y="10" width="8" height="11" rx="1.5" />
              <rect x="3" y="13" width="8" height="8" rx="1.5" />
            </Icon>
            Dashboard
          </NavLink>
          <NavLink to="/register" className={navClass}>
            <Icon>
              <rect x="4" y="3" width="16" height="18" rx="2" />
              <path d="M8 8h8M8 12h8M8 16h5" />
            </Icon>
            Metric register
          </NavLink>
          <NavLink to="/agent" className={navClass}>
            <Icon>
              <path d="M12 3l1.6 5.2L19 10l-5.4 1.8L12 17l-1.6-5.2L5 10l5.4-1.8L12 3z" />
            </Icon>
            Agent
            <span className="chip accent">New</span>
          </NavLink>
          <NavLink to="/architecture" className={navClass}>
            <Icon>
              <path d="M12 3l8 4-8 4-8-4 8-4z" />
              <path d="M4 12l8 4 8-4" />
              <path d="M4 17l8 4 8-4" />
            </Icon>
            Architecture
          </NavLink>
        </nav>
        <div>
          <p className="nav-label">Utility</p>
          <nav className="side-nav" aria-label="Utility">
            <NavLink to="/definitions" className={navClass}>
              <Icon>
                <path d="M5 4h11a3 3 0 013 3v13H8a3 3 0 00-3 3V4z" />
                <path d="M8 4v16" />
              </Icon>
              Definitions &amp; conventions
            </NavLink>
          </nav>
        </div>
        <div className="side-foot">
          <span>Policy Control Office</span>
          <span>Prepared demo dataset</span>
          <a href="/legacy">Earlier release</a>
        </div>
      </aside>
      <div className="main-col">
        <div className="env-bar" aria-live="polite">
          <span className="env-dot" />
          <span className="grow">{statusText}</span>
          {updating && (
            <span className="env-updating" role="status">
              <span className="env-updating-dot" aria-hidden="true" />
              Showing the previous selection while the new one loads
            </span>
          )}
          {status.status === 'error' && (
            <button type="button" className="btn btn-quiet btn-sm" onClick={status.retry}>
              Retry
            </button>
          )}
        </div>
        <main id="content" className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
