"""Lineage entries for fields the UI chips. Omitted when an endpoint publishes definitions inline."""

from __future__ import annotations

AM = "V_APPLICATION_MONTH_STATUS"
AC = "APPLICATION_COMPLIANCE"


def entry(field: str, kind: str, status: str, definition_ids: list[str], objects: list[str], columns: list[str], grain: str) -> dict:
    return {
        "field": field,
        "class": kind,
        "status": status,
        "definitionIds": definition_ids,
        "source": {"objects": objects, "columns": columns, "grain": grain},
    }


def overview() -> list[dict]:
    return [
        entry("applicationsReporting", "observation", "source", [], [AM], ["EON_ID", "REPORTING_MONTHEND_DATE"], "application_month"),
        entry("nonCompliant.applications", "derived", "provisional", ["PD-03"], [AM], ["IS_NON_COMPLIANT_APP"], "application_month"),
        entry("nonCompliant.share", "derived", "provisional", ["PD-08"], [AM], ["IS_NON_COMPLIANT_APP"], "application_month"),
        entry("testing.withoutCompletedTest", "derived", "documented_rule", ["PD-04"], [AM], ["HAS_NO_COMPLETED_TEST"], "application_month"),
        entry("testing.withFailedTest", "derived", "documented_rule", ["PD-05"], [AM], ["HAS_FAILED_TEST"], "application_month"),
        entry("openFindings", "derived", "documented_rule", ["PD-07"], [AM], ["OPEN_FINDINGS"], "application_month"),
        entry("metricRows", "observation", "source", [], [AM], ["METRIC_ROWS"], "application_month"),
        entry("movement", "derived", "provisional", ["PD-06"], [AM], ["MOVEMENT_STATUS"], "application_month"),
    ]


def rate() -> list[dict]:
    return [
        entry("rate", "derived", "provisional", ["PD-01", "PD-16"], [AC], ["IS_NUMERATOR", "IS_DENOMINATOR"], "metric_month"),
        entry("family", "derived", "not_available", ["PD-13"], [], [], "metric"),
        entry("denominatorScope", "derived", "assumption", ["PD-02", "PD-19"], [AC], ["COMPLIANCE_STATUS", "IS_DENOMINATOR"], "metric"),
        entry("movement", "derived", "provisional", ["PD-14"], [AC], ["COMPLIANCE_STATUS"], "metric_row"),
    ]
