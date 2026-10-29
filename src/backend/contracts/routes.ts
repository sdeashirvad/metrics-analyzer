/**
 * Future HTTP map for controllens_backend.
 * The UI depends on RiskApi, not on these strings.
 * Swap src/backend/services/index.ts to an HTTP client that calls these routes.
 */
export const apiRoutes = {
  overview: 'GET /api/v1/overview',
  metrics: 'GET /api/v1/metrics',
  metric: 'GET /api/v1/metrics/:metricId',
  trend: 'GET /api/v1/metrics/:metricId/trend',
  investigations: 'GET /api/v1/investigations',
  investigation: 'GET /api/v1/investigations/:metricId',
  orgContribution: 'GET /api/v1/metrics/:metricId/org-contribution',
} as const
