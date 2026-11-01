import { NavLink, Outlet, ScrollRestoration } from 'react-router-dom'
import { EnvironmentBar } from './EnvironmentBar'

export function AppShell() {
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
          <div>
            <div className="brand-name">Metrics Analyzer</div>
            <div className="brand-sub">Metric Intelligence Platform</div>
          </div>
        </div>
        <nav className="side-nav" aria-label="Primary">
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/overview">Triage</NavLink>
          <NavLink to="/metrics">Metric register</NavLink>
          <NavLink to="/architecture">Architecture</NavLink>
        </nav>
        <nav className="side-utility" aria-label="Reference">
          <NavLink to="/glossary">Glossary &amp; conventions</NavLink>
        </nav>
        <div className="sidebar-foot">
          <div>Policy Control Office</div>
          <div>Data Quality from Snowflake</div>
        </div>
      </aside>
      <div className="main-col">
        <EnvironmentBar />
        <main id="content" className="content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <ScrollRestoration />
    </div>
  )
}
