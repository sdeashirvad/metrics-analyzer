import { Route, Routes } from 'react-router-dom'
import { AgentHome, ConversationPage, NewConversationPage } from './features/agent/AgentPages'
import { ArchitecturePage } from './features/architecture/ArchitecturePage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { DefinitionsPage } from './features/definitions/DefinitionsPage'
import { ApplicationInvestigationPage } from './features/investigation/ApplicationInvestigationPage'
import { MetricInvestigationPage } from './features/investigation/MetricInvestigationPage'
import { MetricSummaryPage } from './features/metric/MetricSummaryPage'
import { NotFoundPage } from './features/NotFoundPage'
import { RegisterPage } from './features/register/RegisterPage'
import { V2Shell } from './shell/V2Shell'

export function V2Routes() {
  return (
    <Routes>
      <Route element={<V2Shell />}>
        <Route index element={<DashboardPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="register/:metricId" element={<MetricSummaryPage />} />
        <Route path="investigate/metrics/:metricId" element={<MetricInvestigationPage />} />
        <Route path="investigate/applications/:eonId" element={<ApplicationInvestigationPage />} />
        <Route path="agent" element={<AgentHome />} />
        <Route path="agent/:agentKey" element={<NewConversationPage />} />
        <Route path="agent/:agentKey/:conversationId" element={<ConversationPage />} />
        <Route path="architecture" element={<ArchitecturePage />} />
        <Route path="definitions" element={<DefinitionsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
