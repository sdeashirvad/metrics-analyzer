"""Provisional definition registry. The only place portfolio formulas are written.

Services call the functions below. They do not restate the formulas.
"""

from __future__ import annotations

DEFINITIONS_VERSION = "pd-1"

NUMERATOR_RULE = "A row is in the numerator when IS_NUMERATOR is 1. The business meaning is unconfirmed."
DENOMINATOR_RULE = (
    "A row is in the denominator when IS_DENOMINATOR is 1. "
    "Pending rows are included or excluded according to the inferred denominator scope."
)

POPULATION_NOTE = {
    "code": "POPULATION_GROWS",
    "text": (
        "The number of applications reporting rises across the months in this dataset. "
        "Read counts together with the non-compliant share."
    ),
}

HISTORY_NOTE = (
    "Months marked not observed mean the application did not report, not that it was compliant."
)

FLAG_TEXT = {
    "RATE_PROVISIONAL": (
        "This rate is provisional. It uses one metric and one month, and it is never compared across metrics.",
        "PD-01",
    ),
    "DENOMINATOR_SCOPE_INFERRED": (
        "Denominator scope is inferred from Pending rows. It is not a stored business label.",
        "PD-02",
    ),
    "FAMILY_NOT_AVAILABLE": (
        "A source metric family is not in the deployed data.",
        "PD-13",
    ),
    "SMALL_BASE": (
        "The denominator is below 20. The rate is shown with its denominator.",
        "PD-01",
    ),
    "NO_PRIOR_MONTH": (
        "This metric has no rows in the previous month.",
        "PD-14",
    ),
    "NO_ROWS_IN_MONTH": (
        "This metric has no rows in the selected month and scope.",
        None,
    ),
}

_ENTRIES = (
    {
        "id": "PD-01",
        "name": "Provisional compliance rate",
        "definition": (
            "SUM(IS_NUMERATOR) / SUM(IS_DENOMINATOR) over metric rows of one METRIC_ID in one month "
            "and scope. null if the denominator is 0. Never averaged or compared across metrics."
        ),
        "grain": "Metric rows (EON_ID x METRIC_ID x month), aggregated to metric x month",
        "scope": "One METRIC_ID, one month, the active filters",
        "limitations": (
            "Numerator and denominator meanings are unconfirmed; denominators differ by variant; "
            "never compared across metrics; an application with several rows counts once per row."
        ),
        "status": "provisional",
        "basis": "Assumptions C03, G02",
    },
    {
        "id": "PD-02",
        "name": "Denominator scope (inferred)",
        "definition": (
            "Per metric over all rows: INCLUDES_PENDING if every Pending row has IS_DENOMINATOR = 1; "
            "EXCLUDES_PENDING if every Pending row has 0; MIXED; UNDETERMINED if the metric has no Pending rows."
        ),
        "grain": "Metric, over all of its rows",
        "scope": "All months and all applications of the metric",
        "limitations": "Inferred from Pending rows only; UNDETERMINED when a metric has none; variant labels are not stored.",
        "status": "assumption",
        "basis": "Variants A/B are generator settings and are not stored.",
    },
    {
        "id": "PD-03",
        "name": "Non-compliant application",
        "definition": "An application-month with at least one Non_Compliant metric row (IS_NON_COMPLIANT_APP).",
        "grain": "Application-month",
        "scope": "One month, the active filters",
        "limitations": "One Non_Compliant row makes the application non-compliant; no severity.",
        "status": "provisional",
        "basis": "View V_APPLICATION_MONTH_STATUS",
    },
    {
        "id": "PD-04",
        "name": "No completed test",
        "definition": "An application-month with no Test_Complete row (HAS_NO_COMPLETED_TEST).",
        "grain": "Application-month",
        "scope": "One month, the active filters",
        "limitations": "Includes applications that have no test rows at all.",
        "status": "documented_rule",
        "basis": "View",
    },
    {
        "id": "PD-05",
        "name": "Failed test",
        "definition": "An application-month with a Test_Complete row whose result is Fail (HAS_FAILED_TEST).",
        "grain": "Application-month",
        "scope": "One month, the active filters",
        "limitations": "Only completed tests with result Fail.",
        "status": "documented_rule",
        "basis": "View",
    },
    {
        "id": "PD-06",
        "name": "Application movement",
        "definition": "MOVEMENT_STATUS compares an application with the immediately preceding calendar month only.",
        "grain": "Application, current month against the previous calendar month",
        "scope": "One month",
        "limitations": "null in the first month; an application absent in the previous month has no comparison.",
        "status": "provisional",
        "basis": "View comment",
    },
    {
        "id": "PD-07",
        "name": "Open findings",
        "definition": "Per application-month MAX(TOTAL_RFB); portfolio total is the sum of those values for one month.",
        "grain": "Application-month, summed across applications",
        "scope": "One month, the active filters",
        "limitations": (
            "Some source rows are null; the business meaning of TOTAL_RFB is not defined; "
            "never summed across metric rows."
        ),
        "status": "documented_rule",
        "basis": "Assumption G04, snapshot comment",
    },
    {
        "id": "PD-08",
        "name": "Non-compliant share",
        "definition": (
            "non-compliant applications / applications reporting, same month and scope. "
            "The denominator includes applications that are not non-compliant and is not a compliance rate."
        ),
        "grain": "Application-month counts",
        "scope": "One month, the active filters",
        "limitations": "Denominator is applications reporting, which changes by month; not a compliance rate.",
        "status": "provisional",
        "basis": "Derived from PD-03",
    },
    {
        "id": "PD-09",
        "name": "Application status precedence",
        "definition": (
            "NON_COMPLIANT if any Non_Compliant row; else PENDING if any Pending; "
            "else COMPLIANT if any Compliant; else NOT_APPLICABLE. Used only for the optional application mix."
        ),
        "grain": "Application-month",
        "scope": "One month",
        "limitations": "Precedence is a design choice, used only for the optional application mix.",
        "status": "provisional",
        "basis": "Design choice",
    },
    {
        "id": "PD-10",
        "name": "Organisation trees",
        "definition": (
            "BUSINESS_ORG (SUPER_DIVISION, DIVISION, SUPER_DEPARTMENT, DEPARTMENT, BUS_ORG_LG_NM) and "
            "BU (BU_SUPER_DIVISION, BU_DIVISION, BU_SUPER_DEPARTMENT, BU_DEPARTMENT) are separate trees. "
            "They are never joined or shown in one hierarchy. Default is BUSINESS_ORG."
        ),
        "grain": "Organisation levels",
        "scope": "One tree at a time",
        "limitations": "BUSINESS_ORG and BU are never combined.",
        "status": "source",
        "basis": "DATA_MODEL.md",
    },
    {
        "id": "PD-11",
        "name": "Risk and tier grouping",
        "definition": (
            "Risk is grouped by the stored ASSET_RISK_RATING_2 code. Tier is the stored number. "
            "Neither has a defined direction, so results are ordered by code and are not ranked as better or worse."
        ),
        "grain": "Risk and tier codes",
        "scope": "One month",
        "limitations": "Codes have no direction or order beyond sorting by key.",
        "status": "documented_rule",
        "basis": "Assumption D03",
    },
    {
        "id": "PD-12",
        "name": "Current roll-up",
        "definition": (
            "Historical trends keep each month's own application-month records. "
            "A current roll-up that spans months uses each application's latest month. A single-month view uses that month."
        ),
        "grain": "Application, latest month",
        "scope": "Across months",
        "limitations": "Used only when a view spans months.",
        "status": "documented_rule",
        "basis": "Assumption G03",
    },
    {
        "id": "PD-13",
        "name": "Source metric family",
        "definition": (
            "Not in the deployed data. The API returns family null and the UI shows not available. "
            "A derived grouping is PD-19; it is not a substitute for a business family."
        ),
        "grain": "Metric",
        "scope": "Not available",
        "limitations": "Source column does not exist.",
        "status": "not_available",
        "basis": "Assumption B03",
    },
    {
        "id": "PD-14",
        "name": "Metric-level movement",
        "definition": (
            "For one metric, per application, comparing its row in the month with its row in the immediately "
            "preceding month: NEWLY_NON_COMPLIANT, RESOLVED, PERSISTENT_NON_COMPLIANT, NO_PRIOR_MONTH, OTHER."
        ),
        "grain": "Metric rows, consecutive months",
        "scope": "One metric, one month and the previous",
        "limitations": "Only applications present in the later month are classified.",
        "status": "provisional",
        "basis": "Metric-level analogue of PD-06",
    },
    {
        "id": "PD-15",
        "name": "Composition effect",
        "definition": (
            "For one metric and two consecutive months: applications in both months, only in the later month, "
            "only in the earlier month, and the rate of the continuing applications in each month. "
            "Describes a change in who reported, not why."
        ),
        "grain": "Metric, two consecutive months",
        "scope": "One metric",
        "limitations": "Describes who reported, not why the rate moved.",
        "status": "provisional",
        "basis": "Derived from PD-01",
    },
    {
        "id": "PD-16",
        "name": "Rate change",
        "definition": "(rate - priorRate) * 100 in percentage points. null if either rate is null. Same metric only.",
        "grain": "Metric, two consecutive months",
        "scope": "One metric",
        "limitations": "Percentage points, same metric only; null if either rate is null.",
        "status": "provisional",
        "basis": "PD-01",
    },
    {
        "id": "PD-17",
        "name": "Peers",
        "definition": (
            "For application investigation: applications in the same month with the same SUPER_DIVISION "
            "and LIFECYCLE_PHASE. Reported as counts and the non-compliant share."
        ),
        "grain": "Application, peers in the same month",
        "scope": "Same SUPER_DIVISION and LIFECYCLE_PHASE",
        "limitations": "Small peer groups are unstable; counts are shown with the shares.",
        "status": "provisional",
        "basis": "Design choice",
    },
    {
        "id": "PD-18",
        "name": "Reporting coverage",
        "definition": (
            "Applications reporting in the month, against the distinct applications seen anywhere in the dataset. "
            "That distinct count is not an authoritative population."
        ),
        "grain": "Month",
        "scope": "The dataset",
        "limitations": "The distinct application count is the applications seen in the dataset, not an authoritative population.",
        "status": "provisional",
        "basis": "Derived",
    },
    {
        "id": "PD-19",
        "name": "Derived metric group (provisional)",
        "definition": (
            "Per metric, the PD-02 classification used as a group: INCLUDES_PENDING, EXCLUDES_PENDING, MIXED, "
            "UNDETERMINED. Shown as the denominator group wherever a family would appear. "
            "Groups by denominator treatment only."
        ),
        "grain": "Metric",
        "scope": "All metrics",
        "limitations": (
            "Groups metrics by denominator treatment only; it is not a business family. "
            "A business-defined grouping needs owner input."
        ),
        "status": "provisional",
        "basis": "Derived from PD-02",
    },
)

_CONVENTIONS = (
    ("G-1", "An EON_ID is one application and a METRIC_ID is one metric. A metric row is one application's observation of one metric at one month-end."),
    ("G-2", "Application counts come from the application-month view, or from distinct applications. They are never a count of metric rows."),
    ("G-3", "Metric-level detail comes from metric rows. For one metric and one month, the number of rows equals the number of applications."),
    ("G-4", "Trends keep each month's own records. A roll-up across months uses each application's latest month. A single-month view uses that month."),
    ("G-5", "Open findings are counted once per application-month. A row-level finding count may be summed only within one metric."),
    ("G-6", "Business organisation and BU are separate trees and are never combined. The default tree is business organisation."),
    ("G-7", "Risk and tier are grouped by the stored code. The codes are ordered by key and are not ranked as better or worse."),
    ("G-8", "An application that is not non-compliant is not called compliant. Compliant, non-compliant, pending and not applicable stay separate."),
    ("G-9", "A month with no observation is not observed. It is not returned as zero or as compliant."),
    ("G-10", "The first month has no prior month. Movement for it is null, not zero."),
)

REGISTRY = {}
for _entry in _ENTRIES:
    item = dict(_entry)
    item["sinceVersion"] = DEFINITIONS_VERSION
    REGISTRY[item["id"]] = item


def get(definition_id: str) -> dict:
    found = REGISTRY.get(definition_id)
    if found is None:
        raise KeyError(definition_id)
    return dict(found)


# Fractional PD-01 rate. 0.45 means 45%. Bands follow the October 2026 register:
# four rates sit under 0.45, the next group ends at 0.565, and the rest start at 0.607.
RATE_GREEN_BELOW = 0.45
RATE_AMBER_BELOW = 0.60
RAG_VALUES = ("green", "amber", "red", "unclassified")
RAG_RANK = {"red": 3, "amber": 2, "green": 1, "unclassified": 0}

APPLICATION_GREEN = {
    "complianceStatus": "Compliant",
    "testStatus": "Test_Complete",
    "testResult": "Pass",
}


def classify_rate(rate: float | None) -> str:
    """PD-01. Higher is worse. Null has no band."""
    if rate is None:
        return "unclassified"
    if rate < RATE_GREEN_BELOW:
        return "green"
    if rate < RATE_AMBER_BELOW:
        return "amber"
    return "red"


def metric_row_is_green(compliance_status: str | None, test_status: str | None, test_result: str | None) -> bool:
    """Provisional application-row target. Pending and Not_Applicable are not green."""
    return (
        compliance_status == APPLICATION_GREEN["complianceStatus"]
        and test_status == APPLICATION_GREEN["testStatus"]
        and test_result == APPLICATION_GREEN["testResult"]
    )


def provisional_rate(numerator: int, denominator: int) -> float | None:
    """PD-01. null when the denominator is 0. Rounded to 6 decimal places."""
    if not denominator:
        return None
    return round(int(numerator) / int(denominator), 6)


def rate_change_pp(rate: float | None, prior_rate: float | None) -> float | None:
    """PD-16. Percentage points, null when either rate is null. Rounded to 4 decimal places."""
    if rate is None or prior_rate is None:
        return None
    return round((rate - prior_rate) * 100, 4)


def share(part: int, whole: int) -> float | None:
    """PD-08. null when the reporting count is 0. Rounded to 6 decimal places."""
    if not whole:
        return None
    return round(int(part) / int(whole), 6)


def classify_denominator(pending_rows: int, pending_in_denominator: int) -> str:
    """PD-02. Groups a metric by denominator treatment only (PD-19 uses the same label)."""
    pending_rows = int(pending_rows or 0)
    pending_in_denominator = int(pending_in_denominator or 0)
    if pending_rows == 0:
        return "UNDETERMINED"
    if pending_in_denominator == pending_rows:
        return "INCLUDES_PENDING"
    if pending_in_denominator == 0:
        return "EXCLUDES_PENDING"
    return "MIXED"


def metric_movement(current_status: str | None, prior_status: str | None) -> str:
    """PD-14 for one application present in the later month."""
    if prior_status is None:
        return "NO_PRIOR_MONTH"
    current_nc = current_status == "Non_Compliant"
    prior_nc = prior_status == "Non_Compliant"
    if current_nc and prior_nc:
        return "PERSISTENT_NON_COMPLIANT"
    if current_nc and not prior_nc:
        return "NEWLY_NON_COMPLIANT"
    if prior_nc and not current_nc:
        return "RESOLVED"
    return "OTHER"


def status_precedence(compliant: int, non_compliant: int, pending: int) -> str:
    """PD-09."""
    if non_compliant:
        return "NON_COMPLIANT"
    if pending:
        return "PENDING"
    if compliant:
        return "COMPLIANT"
    return "NOT_APPLICABLE"


def public_definitions() -> dict:
    definitions = []
    for entry in _ENTRIES:
        definitions.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "definition": entry["definition"],
                "status": entry["status"],
                "basis": entry["basis"],
                "appliesTo": [entry["grain"], entry["scope"]],
                "caveats": [entry["limitations"]],
            }
        )
    return {
        "definitions": definitions,
        "conventions": [{"id": item_id, "text": text} for item_id, text in _CONVENTIONS],
        "classification": {
            "provisional": True,
            "rate": {
                "definitionId": "PD-01",
                "direction": "higher_is_worse",
                "unit": "fraction",
                "greenBelow": RATE_GREEN_BELOW,
                "amberBelow": RATE_AMBER_BELOW,
                "note": (
                    "Provisional, not a client target. A rate of 0.45 is 45%. "
                    "Green is below 0.45, amber is below 0.60, and red is 0.60 or higher. "
                    "A null rate is unclassified."
                ),
            },
            "applicationGreen": {
                **APPLICATION_GREEN,
                "note": (
                    "Provisional. An application is green only when every metric row is Compliant, "
                    "Test_Complete, and Pass. Pending and Not_Applicable stay their own states."
                ),
            },
        },
    }


def flag(code: str) -> dict:
    text, definition_id = FLAG_TEXT[code]
    item = {"code": code, "text": text}
    if definition_id:
        item["definitionId"] = definition_id
    return item
