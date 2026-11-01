"""Export SMARTS_DQ_mock_data.xlsx to snowflake/seed CSVs.

Reads the workbook. Does not modify it, the SQL scripts, or the README.
Column order is the sheet order consumed by the README COPY statements.
Dates are written as ISO YYYY-MM-DD. Pass rates, thresholds, and volume
share are written at four decimal places, half away from zero, matching
TRY_TO_DECIMAL scale. Record counts and ageing stay integers.
"""

from __future__ import annotations

import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

SEED = Path(__file__).resolve().parent
XLSX = next(
    (
        path
        for path in (
            SEED.parents[2] / "SMARTS_DQ_mock_data.xlsx",
            SEED.parents[1] / "SMARTS_DQ_mock_data.xlsx",
        )
        if path.exists()
    ),
    SEED.parents[2] / "SMARTS_DQ_mock_data.xlsx",
)

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XML_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXCEL_EPOCH = datetime(1899, 12, 30)
SCALE_4 = Decimal("0.0001")

# Workbook header order. These positions are $1..$n in README COPY statements.
SHEETS = {
    "dq_control_definitions.csv": (
        "dq_control_definitions",
        [
            "control_id",
            "control_name",
            "dq_dimension",
            "regulation",
            "regulatory_report",
            "critical_data_element",
            "source_system",
            "frequency",
            "green_threshold",
            "amber_threshold",
            "severity",
            "check_logic",
            "bcbs239_principle",
            "owner_role",
        ],
    ),
    "dq_results.csv": (
        "dq_results",
        [
            "result_id",
            "metric_date",
            "control_id",
            "frequency",
            "total_records",
            "failed_records",
            "pass_rate_pct",
            "rag_status",
        ],
    ),
    "dq_results_by_desk.csv": (
        "dq_results_by_desk",
        [
            "result_id",
            "metric_date",
            "control_id",
            "desk_id",
            "total_records",
            "failed_records",
            "pass_rate_pct",
            "rag_status",
        ],
    ),
    "dq_exceptions.csv": (
        "dq_exceptions",
        [
            "exception_id",
            "exception_date",
            "control_id",
            "desk_id",
            "trade_id",
            "field_name",
            "offending_value",
            "failure_reason",
            "severity",
            "status",
            "ageing_days",
            "assigned_team",
        ],
    ),
    "desk_hierarchy.csv": (
        "desk_hierarchy",
        [
            "desk_id",
            "desk_name",
            "business_line",
            "primary_region",
            "volume_share",
        ],
    ),
    "change_incident_events.csv": (
        "change_incident_events",
        [
            "event_id",
            "event_date",
            "event_type",
            "desk_ids",
            "description",
            "related_control_id",
        ],
    ),
    "analyst_commentary.csv": (
        "analyst_commentary",
        [
            "commentary_date",
            "control_id",
            "rag_at_time",
            "analyst_commentary",
            "root_cause_category",
            "path_to_green",
            "author_role",
        ],
    ),
}

DATE_COLUMNS = {
    "metric_date",
    "exception_date",
    "event_date",
    "commentary_date",
}
SCALE_4_COLUMNS = {
    "green_threshold",
    "amber_threshold",
    "pass_rate_pct",
    "volume_share",
}
INTEGER_COLUMNS = {
    "total_records",
    "failed_records",
    "ageing_days",
}
EXPECTED_ROWS = {
    "dq_control_definitions.csv": 36,
    "dq_results.csv": 1722,
    "dq_results_by_desk.csv": 4536,
    "dq_exceptions.csv": 1560,
    "desk_hierarchy.csv": 9,
    "change_incident_events.csv": 12,
    "analyst_commentary.csv": 12,
    "planted_story.csv": 5,
}
# Staging VARCHAR widths from 03_create_staging_tables.sql. PLANTED_STORY is loaded separately.
MAX_LENGTH = {
    "control_id": 16,
    "control_name": 200,
    "dq_dimension": 32,
    "regulation": 80,
    "regulatory_report": 80,
    "critical_data_element": 80,
    "source_system": 80,
    "frequency": 16,
    "severity": 16,
    "check_logic": 1000,
    "bcbs239_principle": 80,
    "owner_role": 80,
    "desk_id": 16,
    "desk_name": 80,
    "business_line": 40,
    "primary_region": 16,
    "result_id": 16,
    "rag_status": 16,
    "exception_id": 16,
    "trade_id": 32,
    "field_name": 80,
    "offending_value": 200,
    "failure_reason": 500,
    "status": 32,
    "assigned_team": 80,
    "event_id": 16,
    "event_type": 32,
    "desk_ids": 200,
    "description": 2000,
    "related_control_id": 16,
    "rag_at_time": 16,
    "analyst_commentary": 4000,
    "root_cause_category": 80,
    "path_to_green": 500,
    "author_role": 80,
    "planted_story": 256,
}


def col_idx(ref: str) -> int:
    letters = ""
    for char in ref:
        if char.isalpha():
            letters += char
        else:
            break
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
    return number - 1


def sheet_rows(book: zipfile.ZipFile, target: str) -> list[list[str]]:
    path = target[1:] if target.startswith("/") else target
    if not path.startswith("xl/"):
        path = "xl/" + path
    root = ET.fromstring(book.read(path))
    rows: list[list[str]] = []
    for row in root.iter(NS + "row"):
        cells: dict[int, str] = {}
        for cell in row.findall("m:c", XML_NS):
            ref = cell.attrib.get("r", "")
            if cell.attrib.get("t") == "inlineStr":
                value = "".join(node.text or "" for node in cell.iter(NS + "t"))
            else:
                node = cell.find("m:v", XML_NS)
                value = node.text if node is not None and node.text else ""
            if ref:
                cells[col_idx(ref)] = value
        if cells:
            last = max(cells)
            rows.append([cells.get(index, "") for index in range(last + 1)])
    return rows


def load_workbook(path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        relationships = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relationships}
        sheets: dict[str, list[list[str]]] = {}
        for sheet in workbook.find("m:sheets", XML_NS):
            name = sheet.attrib["name"]
            relation = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            sheets[name] = sheet_rows(book, targets[relation])
    return sheets


def to_iso(value: str) -> str:
    text = value.strip()
    if ISO_DATE.fullmatch(text):
        datetime.strptime(text, "%Y-%m-%d")
        return text
    serial = Decimal(text)
    if serial != serial.to_integral_value():
        raise ValueError(f"date is not an integer Excel serial: {value}")
    return (EXCEL_EPOCH + timedelta(days=int(serial))).date().isoformat()


def to_scale_4(value: str) -> str:
    rounded = Decimal(value).quantize(SCALE_4, rounding=ROUND_HALF_UP)
    return format(rounded, "f")


def to_integer(value: str) -> str:
    number = Decimal(value)
    if number != number.to_integral_value():
        raise ValueError(f"expected an integer cell: {value}")
    return str(int(number))


def convert_cell(header: str, value: str) -> str:
    if header in DATE_COLUMNS:
        return to_iso(value)
    if header in SCALE_4_COLUMNS:
        return to_scale_4(value)
    if header in INTEGER_COLUMNS:
        return to_integer(value)
    return value


def planted_stories(readme_rows: list[list[str]]) -> list[list[str]]:
    header_at = next(
        index
        for index, row in enumerate(readme_rows)
        if row[:3] == ["control_id", "period", "planted_story"]
    )
    stories = [["control_id", "planted_story"]]
    for row in readme_rows[header_at + 1 :]:
        if not row or not row[0]:
            break
        stories.append([row[0], row[2]])
    return stories


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows)


def read_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def export() -> None:
    if not XLSX.exists():
        raise SystemExit(f"Workbook not found: {XLSX}")
    sheets = load_workbook(XLSX)
    SEED.mkdir(parents=True, exist_ok=True)
    for filename, (sheet_name, expected_header) in SHEETS.items():
        rows = sheets[sheet_name]
        header = rows[0]
        if header != expected_header:
            raise SystemExit(f"{sheet_name} header {header} does not match COPY order {expected_header}")
        converted = [header]
        for row in rows[1:]:
            padded = row + [""] * (len(header) - len(row))
            converted.append(
                [convert_cell(name, padded[index]) for index, name in enumerate(header)]
            )
        write_csv(SEED / filename, converted)
    stories = planted_stories(sheets["README"])
    if len(stories) != 6:
        raise SystemExit(f"expected 5 planted stories, found {len(stories) - 1}")
    write_csv(SEED / "planted_story.csv", stories)


def duplicates(rows: list[list[str]], indexes: list[int]) -> int:
    seen: set[tuple[str, ...]] = set()
    repeated = 0
    for row in rows:
        key = tuple(row[index] for index in indexes)
        if key in seen:
            repeated += 1
        seen.add(key)
    return repeated


def validate() -> list[str]:
    problems: list[str] = []
    sheets = load_workbook(XLSX)
    loaded: dict[str, list[list[str]]] = {}
    for filename, expected_count in EXPECTED_ROWS.items():
        rows = read_csv(SEED / filename)
        loaded[filename] = rows
        data = rows[1:]
        print(f"{filename}: {len(data)} data rows")
        print(f"  headers: {rows[0]}")
        if len(data) != expected_count:
            problems.append(f"{filename} row count {len(data)} != {expected_count}")
        if filename == "planted_story.csv":
            if rows[0] != ["control_id", "planted_story"]:
                problems.append(f"planted_story headers {rows[0]}")
            continue
        expected_header = SHEETS[filename][1]
        if rows[0] != expected_header:
            problems.append(f"{filename} headers {rows[0]}")
        source = sheets[SHEETS[filename][0]]
        if len(source) - 1 != len(data):
            problems.append(f"{filename} does not match workbook row count")
        for index, name in enumerate(expected_header):
            for row_number, (csv_row, source_row) in enumerate(zip(data, source[1:]), start=2):
                if csv_row[index] == "":
                    problems.append(f"{filename} row {row_number} empty {name}")
                if name in MAX_LENGTH and len(csv_row[index]) > MAX_LENGTH[name]:
                    problems.append(f"{filename} {name} exceeds VARCHAR({MAX_LENGTH[name]})")
                expected = convert_cell(name, source_row[index] if index < len(source_row) else "")
                if csv_row[index] != expected:
                    problems.append(
                        f"{filename} row {row_number} {name} csv={csv_row[index]!r} workbook={expected!r}"
                    )
                    break

    date_columns = {
        "dq_results.csv": "metric_date",
        "dq_results_by_desk.csv": "metric_date",
        "dq_exceptions.csv": "exception_date",
        "change_incident_events.csv": "event_date",
        "analyst_commentary.csv": "commentary_date",
    }
    for filename, column in date_columns.items():
        header = loaded[filename][0]
        position = header.index(column)
        values = [row[position] for row in loaded[filename][1:]]
        bad = [value for value in values if not ISO_DATE.fullmatch(value)]
        if bad:
            problems.append(f"{filename} non-ISO dates: {bad[:3]}")
        print(f"  {column}: {min(values)} .. {max(values)}")

    key_checks = {
        "dq_control_definitions.csv": [["control_id"]],
        "dq_results.csv": [["result_id"], ["control_id", "metric_date"]],
        "dq_results_by_desk.csv": [["result_id"], ["control_id", "metric_date", "desk_id"]],
        "dq_exceptions.csv": [["exception_id"], ["trade_id"]],
        "desk_hierarchy.csv": [["desk_id"]],
        "change_incident_events.csv": [["event_id"]],
        "analyst_commentary.csv": [["commentary_date", "control_id"]],
        "planted_story.csv": [["control_id"]],
    }
    for filename, key_sets in key_checks.items():
        header = loaded[filename][0]
        body = loaded[filename][1:]
        for names in key_sets:
            count = duplicates(body, [header.index(name) for name in names])
            if count:
                problems.append(f"{filename} duplicate {'+'.join(names)}: {count}")

    stories = {row[0]: row[1] for row in loaded["planted_story.csv"][1:]}
    source_stories = {
        row[0]: row[1]
        for row in planted_stories(sheets["README"])[1:]
    }
    if stories != source_stories:
        problems.append(f"planted stories differ from README sheet: {stories}")
    print("planted stories:")
    for control_id, text in stories.items():
        print(f"  {control_id} ({len(text)}): {text}")

    results = loaded["dq_results.csv"]
    result_header = results[0]
    result_index = {name: index for index, name in enumerate(result_header)}
    portfolio: dict[tuple[str, str], tuple[int, int]] = {}
    for row in results[1:]:
        portfolio[(row[result_index["control_id"]], row[result_index["metric_date"]])] = (
            int(row[result_index["failed_records"]]),
            int(row[result_index["total_records"]]),
        )
    desks = loaded["dq_results_by_desk.csv"]
    desk_header = {name: index for index, name in enumerate(desks[0])}
    summed: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for row in desks[1:]:
        key = (row[desk_header["control_id"]], row[desk_header["metric_date"]])
        summed[key][0] += int(row[desk_header["failed_records"]])
        summed[key][1] += int(row[desk_header["total_records"]])
        summed[key][2] += 1
    mismatches = 0
    for key, (failed, total, count) in summed.items():
        parent = portfolio.get(key)
        if parent != (failed, total):
            mismatches += 1
    if mismatches:
        problems.append(f"desk totals differ from portfolio results on {mismatches} dates")
    else:
        print(f"desk totals match portfolio results on {len(summed)} control-dates")

    shares = [Decimal(row[4]) for row in loaded["desk_hierarchy.csv"][1:]]
    share_sum = sum(shares, Decimal("0"))
    print(f"volume share sum: {share_sum}")
    if abs(share_sum - Decimal("1")) > Decimal("0.000001"):
        problems.append(f"volume share sum {share_sum}")

    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print(f"  {problem}")
    else:
        print("validation passed")
    return problems


def main() -> None:
    export()
    problems = validate()
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
