import { Navigate, Route, createBrowserRouter, createRoutesFromElements } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { NotFoundPage } from './components/NotFoundPage'
import { ArchitecturePage } from './features/architecture/ArchitecturePage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { InvestigationPage } from './features/investigation/InvestigationPage'
import { MetricDetailPage } from './features/metric/MetricDetailPage'
import { GlossaryPage } from './features/glossary/GlossaryPage'
import { OverviewPage } from './features/overview/OverviewPage'
import { RegisterPage } from './features/register/RegisterPage'

export const router = createBrowserRouter(
  createRoutesFromElements(
    <Route element={<AppShell />}>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="dashboard" element={<DashboardPage />} />
      <Route path="overview" element={<OverviewPage />} />
      <Route path="metrics" element={<RegisterPage />} />
      <Route path="architecture" element={<ArchitecturePage />} />
      <Route path="glossary" element={<GlossaryPage />} />
      <Route path="metrics/:metricId" element={<MetricDetailPage />} />
      <Route path="investigations/:metricId" element={<InvestigationPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Route>,
  ),
)
