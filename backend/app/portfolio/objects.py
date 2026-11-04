"""Qualified Snowflake names. Role and credentials stay in the existing Settings."""

from __future__ import annotations

APPLICATION_MONTH = "METRICS_ANALYZER.MOCK_DATA.V_APPLICATION_MONTH_STATUS"
APPLICATION_COMPLIANCE = "METRICS_ANALYZER.MOCK_DATA.APPLICATION_COMPLIANCE"
SNAPSHOT = "METRICS_ANALYZER.MOCK_DATA.APP_PORTFOLIO_MONTHLY_SNAPSHOT"

# Organisation contribution is aggregated from APPLICATION_MONTH.
# V_ORGANIZATION_MONTHLY_SUMMARY is not queried: the contract computes the same
# figures from the application-month view, and that summary view is not required.
