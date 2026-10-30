"""Assert workbook fixtures match SMARTS_DQ_mock_data.xlsx. Read-only."""

import importlib.util
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "src" / "backend" / "data" / "dq"
spec = importlib.util.spec_from_file_location("dqbuild", ROOT / "scripts" / "build-dq-fixtures.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main() -> None:
    definitions = load("definitions.json")
    results = load("results.json")
    desks = load("results-by-desk.json")
    exceptions = load("exceptions.json")
    hierarchy = load("hierarchy.json")
    events = load("events.json")
    commentary = load("commentary.json")
    summary = load("summary.json")
    assert len(definitions) == 36
    assert len(results) == 1722
    assert len(desks) == 4536
    assert len(exceptions) == 1560
    assert len(hierarchy) == 9
    assert len(events) == 12
    assert len(commentary) == 12
    assert summary["ragMismatchesAfterRounding"] == 0
    assert summary["controls"] == 36
    assert abs(sum(item["volumeShare"] for item in hierarchy) - 1) < 1e-6

    portfolio = {(row["controlId"], row["date"]): row for row in results}
    grouped = defaultdict(lambda: {"failed": 0, "total": 0})
    for row in desks:
        key = (row["controlId"], row["date"])
        grouped[key]["failed"] += row["failed"]
        grouped[key]["total"] += row["total"]
    for key, sums in grouped.items():
        source = portfolio[key]
        assert sums["failed"] == source["failed"], key
        assert sums["total"] == source["total"], key
    assert len(set(row["controlId"] for row in desks)) == 8

    by_control = defaultdict(list)
    for row in results:
        by_control[row["controlId"]].append(row)
    for story in summary["stories"]:
        tail = sorted(by_control[story["id"]], key=lambda item: item["date"])[-20:]
        expected = [{"date": row["date"], "passRate": row["passRate"], "status": row["status"]} for row in tail]
        assert story["recent"] == expected, story["id"]
    for row in summary["latestByControl"]:
        reds = sorted(item["date"] for item in by_control[row["id"]] if item["status"] == "red")
        assert row["firstRed"] == (reds[0] if reds else None), row["id"]
        assert row["lastRed"] == (reds[-1] if reds else None), row["id"]
    coverage = summary["coverage"]
    assert coverage["deskControls"] == 8
    assert coverage["controlDatesWithoutDesk"] == 1218
    assert coverage["controlsWithoutNarrative"] == 31
    assert summary["latest"] == {"red": 5, "amber": 2, "green": 29}
    assert summary["openExceptions"] == 722

    with mod.zipfile.ZipFile(mod.XLSX) as book:
        sheets = {}
        root = mod.ET.fromstring(book.read("xl/workbook.xml"))
        rels = mod.ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        for sheet in root.findall("m:sheets/m:sheet", mod.ns):
            sheets[sheet.attrib["name"]] = mod.rows_of(book, targets[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]])
    assert len(sheets["dq_control_definitions"]) - 1 == 36
    assert len(sheets["dq_results"]) - 1 == 1722
    assert len(sheets["dq_results_by_desk"]) - 1 == 4536
    assert len(sheets["dq_exceptions"]) - 1 == 1560
    assert len(sheets["desk_hierarchy"]) - 1 == 9
    assert len(sheets["change_incident_events"]) - 1 == 12
    assert len(sheets["analyst_commentary"]) - 1 == 12
    print("reconcile ok", {"results": 1722, "desks": 4536, "deskControls": 8, "stories": len(summary["stories"])})


if __name__ == "__main__":
    main()
