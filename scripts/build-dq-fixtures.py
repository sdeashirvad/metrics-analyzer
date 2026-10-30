"""Read SMARTS_DQ_mock_data.xlsx and write split JSON fixtures. Does not modify the workbook."""

import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XLSX = next(
    (path for path in (ROOT / "SMARTS_DQ_mock_data.xlsx", ROOT.parent / "SMARTS_DQ_mock_data.xlsx") if path.exists()),
    ROOT / "SMARTS_DQ_mock_data.xlsx",
)
OUT = ROOT / "frontend" / "src" / "backend" / "data" / "dq"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
STORIES = {
    "DQ-001": "From 14 Oct. LEI nulls after onboarding migration; Equity Derivatives and Prime Services are the hotspots.",
    "DQ-010": "From 16 Oct. UTI mismatch after TR vendor schema change and duplicate UTI hotfix; Rates and Credit are the hotspots.",
    "DQ-015": "22-23 Oct. Scheduler failure caused late T+1 submissions on all desks; partial recovery 26-27 Oct.",
    "DQ-020": "From 19 Oct. Commodities booking migration not mapped to risk feed; Commodities and Securitised are the hotspots.",
    "DQ-025": "From 8 Oct. Gradual drift: vendor ISIN feed delayed; Equities Cash and Treasury are the hotspots.",
}


def col_idx(ref: str) -> int:
    col = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            break
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n - 1


def iso(serial: str) -> str:
    return (datetime(1899, 12, 30) + timedelta(days=int(float(serial)))).date().isoformat()


def rows_of(z: zipfile.ZipFile, target: str) -> list[list[str]]:
    path = target[1:] if target.startswith("/") else target
    if not path.startswith("xl/"):
        path = "xl/" + path
    root = ET.fromstring(z.read(path))
    out = []
    for row in root.iter(NS + "row"):
        cells = {}
        for cell in row.findall("m:c", ns):
            ref = cell.attrib.get("r", "")
            if cell.attrib.get("t") == "inlineStr":
                val = "".join(node.text or "" for node in cell.iter(NS + "t"))
            else:
                node = cell.find("m:v", ns)
                val = node.text if node is not None and node.text else ""
            if ref:
                cells[col_idx(ref)] = val
        if cells:
            last = max(cells)
            out.append([cells.get(i, "") for i in range(last + 1)])
    return out


def rag(value: str) -> str:
    return {"Green": "green", "Amber": "amber", "Red": "red"}[value]


def num(value: str) -> float:
    return round(float(value), 4)


def expect(pass_rate: float, green: float, amber: float) -> str:
    if pass_rate + 1e-9 >= green:
        return "green"
    if pass_rate + 1e-9 >= amber:
        return "amber"
    return "red"


def main() -> None:
    z = zipfile.ZipFile(XLSX)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheets = {}
    for sheet in wb.find("m:sheets", ns):
        name = sheet.attrib["name"]
        target = rid[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
        sheets[name] = rows_of(z, target)

    defs_raw = sheets["dq_control_definitions"]
    dh = {name: i for i, name in enumerate(defs_raw[0])}
    definitions = []
    thresholds = {}
    for row in defs_raw[1:]:
        control_id = row[dh["control_id"]]
        green = num(row[dh["green_threshold"]])
        amber = num(row[dh["amber_threshold"]])
        thresholds[control_id] = (green, amber)
        definitions.append(
            {
                "id": control_id,
                "name": row[dh["control_name"]],
                "dimension": row[dh["dq_dimension"]],
                "frequency": row[dh["frequency"]],
                "green": green,
                "amber": amber,
                "severity": row[dh["severity"]],
                "regulation": row[dh["regulation"]],
                "report": row[dh["regulatory_report"]],
                "cde": row[dh["critical_data_element"]],
                "sourceSystem": row[dh["source_system"]],
                "checkLogic": row[dh["check_logic"]],
                "principle": row[dh["bcbs239_principle"]],
                "owner": row[dh["owner_role"]],
                "sheet": "dq_control_definitions",
            }
        )

    results = []
    mismatches = 0
    for row in sheets["dq_results"][1:]:
        header = {name: i for i, name in enumerate(sheets["dq_results"][0])}
        control_id = row[header["control_id"]]
        pass_rate = num(row[header["pass_rate_pct"]])
        status = rag(row[header["rag_status"]])
        if status != expect(pass_rate, *thresholds[control_id]):
            mismatches += 1
        results.append(
            {
                "id": row[header["result_id"]],
                "date": iso(row[header["metric_date"]]),
                "controlId": control_id,
                "frequency": row[header["frequency"]],
                "total": int(float(row[header["total_records"]])),
                "failed": int(float(row[header["failed_records"]])),
                "passRate": pass_rate,
                "status": status,
                "sheet": "dq_results",
            }
        )

    desks = []
    for row in sheets["dq_results_by_desk"][1:]:
        header = {name: i for i, name in enumerate(sheets["dq_results_by_desk"][0])}
        desks.append(
            {
                "date": iso(row[header["metric_date"]]),
                "controlId": row[header["control_id"]],
                "deskId": row[header["desk_id"]],
                "total": int(float(row[header["total_records"]])),
                "failed": int(float(row[header["failed_records"]])),
                "passRate": num(row[header["pass_rate_pct"]]),
                "status": rag(row[header["rag_status"]]),
                "sheet": "dq_results_by_desk",
            }
        )

    exceptions = []
    for row in sheets["dq_exceptions"][1:]:
        header = {name: i for i, name in enumerate(sheets["dq_exceptions"][0])}
        exceptions.append(
            {
                "id": row[header["exception_id"]],
                "date": iso(row[header["exception_date"]]),
                "controlId": row[header["control_id"]],
                "deskId": row[header["desk_id"]],
                "tradeId": row[header["trade_id"]],
                "field": row[header["field_name"]],
                "value": row[header["offending_value"]],
                "reason": row[header["failure_reason"]],
                "severity": row[header["severity"]],
                "status": row[header["status"]],
                "ageingDays": int(float(row[header["ageing_days"]])),
                "team": row[header["assigned_team"]],
                "sheet": "dq_exceptions",
            }
        )

    hierarchy = []
    for row in sheets["desk_hierarchy"][1:]:
        header = {name: i for i, name in enumerate(sheets["desk_hierarchy"][0])}
        hierarchy.append(
            {
                "id": row[header["desk_id"]],
                "name": row[header["desk_name"]],
                "line": row[header["business_line"]],
                "region": row[header["primary_region"]],
                "volumeShare": num(row[header["volume_share"]]),
                "sheet": "desk_hierarchy",
            }
        )

    events = []
    for row in sheets["change_incident_events"][1:]:
        header = {name: i for i, name in enumerate(sheets["change_incident_events"][0])}
        events.append(
            {
                "id": row[header["event_id"]],
                "date": row[header["event_date"]],
                "type": row[header["event_type"]],
                "deskIds": row[header["desk_ids"]],
                "description": row[header["description"]],
                "controlId": row[header["related_control_id"]],
                "sheet": "change_incident_events",
            }
        )

    commentary = []
    for row in sheets["analyst_commentary"][1:]:
        header = {name: i for i, name in enumerate(sheets["analyst_commentary"][0])}
        commentary.append(
            {
                "date": iso(row[header["commentary_date"]]),
                "controlId": row[header["control_id"]],
                "ragAtTime": rag(row[header["rag_at_time"]]),
                "text": row[header["analyst_commentary"]],
                "cause": row[header["root_cause_category"]],
                "path": row[header["path_to_green"]],
                "author": row[header["author_role"]],
                "sheet": "analyst_commentary",
            }
        )

    by_control = defaultdict(list)
    for row in results:
        by_control[row["controlId"]].append(row)
    latest_rows = []
    counts = Counter()
    dimension_counts = defaultdict(Counter)
    for definition in definitions:
        series = sorted(by_control[definition["id"]], key=lambda item: item["date"])
        latest = series[-1]
        first_red = next((item["date"] for item in series if item["status"] == "red"), None)
        last_red = next((item["date"] for item in reversed(series) if item["status"] == "red"), None)
        counts[latest["status"]] += 1
        dimension_counts[definition["dimension"]][latest["status"]] += 1
        latest_rows.append(
            {
                "id": definition["id"],
                "name": definition["name"],
                "dimension": definition["dimension"],
                "frequency": definition["frequency"],
                "green": definition["green"],
                "amber": definition["amber"],
                "owner": definition["owner"],
                "severity": definition["severity"],
                "status": latest["status"],
                "passRate": latest["passRate"],
                "failed": latest["failed"],
                "total": latest["total"],
                "asOf": latest["date"],
                "firstRed": first_red,
                "lastRed": last_red,
                "points": len(series),
            }
        )

    as_of = max(row["asOf"] for row in latest_rows)
    desk_names = {item["id"]: item["name"] for item in hierarchy}
    names = {item["id"]: item["name"] for item in definitions}
    hotspot_failed = Counter()
    hotspot_total = Counter()
    for row in desks:
        if row["date"] != as_of:
            continue
        hotspot_failed[row["deskId"]] += row["failed"]
        hotspot_total[row["deskId"]] += row["total"]
    hotspots = []
    for desk_id, failed in hotspot_failed.most_common():
        total = hotspot_total[desk_id]
        hotspots.append(
            {
                "deskId": desk_id,
                "deskName": desk_names[desk_id],
                "failed": failed,
                "total": total,
                "passRate": round((1 - failed / total) * 100, 4) if total else None,
                "date": as_of,
                "basis": "Sum of failed records on this date across the eight controls that have a desk split.",
            }
        )

    exception_status = Counter(row["status"] for row in exceptions)
    desk_controls = {row["controlId"] for row in desks}
    summary = {
        "asOf": as_of,
        "dateFrom": min(row["date"] for row in results),
        "dateTo": max(row["date"] for row in results),
        "controls": len(definitions),
        "withResults": len(latest_rows),
        "latest": {"red": counts["red"], "amber": counts["amber"], "green": counts["green"]},
        "byDimension": [
            {
                "name": name,
                "red": dimension_counts[name]["red"],
                "amber": dimension_counts[name]["amber"],
                "green": dimension_counts[name]["green"],
            }
            for name, _count in sorted(dimension_counts.items(), key=lambda item: (-item[1]["red"] - item[1]["amber"], item[0]))
        ],
        "openExceptions": exception_status["Open"],
        "exceptionStatus": dict(exception_status),
        "deskControls": sorted({row["controlId"] for row in desks}),
        "hotspots": hotspots,
        "stories": [
            {
                "id": story_id,
                "name": names[story_id],
                "readme": text,
                "status": next(row["status"] for row in latest_rows if row["id"] == story_id),
                "asOf": next(row["asOf"] for row in latest_rows if row["id"] == story_id),
                "passRate": next(row["passRate"] for row in latest_rows if row["id"] == story_id),
                "failed": next(row["failed"] for row in latest_rows if row["id"] == story_id),
                "total": next(row["total"] for row in latest_rows if row["id"] == story_id),
                "firstRed": next(row["firstRed"] for row in latest_rows if row["id"] == story_id),
                "recent": recent_points(by_control[story_id]),
            }
            for story_id, text in STORIES.items()
        ],
        "coverage": {
            "deskControls": len(desk_controls),
            "controlDatesWithoutDesk": sum(1 for row in results if row["controlId"] not in desk_controls),
            "controlsWithoutNarrative": len(definitions) - len(STORIES),
        },
        "latestByControl": latest_rows,
        "provenance": "Workbook SMARTS_DQ_mock_data.xlsx. Pass rates rounded to 4 decimal places to remove binary float dust. Supplied RAG is unchanged.",
        "ragMismatchesAfterRounding": mismatches,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write("definitions.json", definitions)
    write("results.json", results)
    write("results-by-desk.json", desks)
    write("exceptions.json", exceptions)
    write("hierarchy.json", hierarchy)
    write("events.json", events)
    write("commentary.json", commentary)
    write("summary.json", summary)
    print(
        json.dumps(
            {
                "definitions": len(definitions),
                "results": len(results),
                "desks": len(desks),
                "exceptions": len(exceptions),
                "hierarchy": len(hierarchy),
                "events": len(events),
                "commentary": len(commentary),
                "mismatches": mismatches,
                "latest": summary["latest"],
                "open": summary["openExceptions"],
            }
        )
    )


RECENT = 20


def recent_points(series: list[dict]) -> list[dict]:
    ordered = sorted(series, key=lambda item: item["date"])[-RECENT:]
    return [{"date": row["date"], "passRate": row["passRate"], "status": row["status"]} for row in ordered]


def write(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
