"""Deterministic narratives from stored facts. These are not Cortex results."""

from __future__ import annotations

from app.dq.mapping import NOT_SUPPLIED, established_lines

DETERMINISTIC_DISCLAIMER = (
    "Deterministic summary of stored Data Quality facts. Not a Snowflake Cortex analysis."
)


def deterministic_summary(control: dict) -> dict:
    if control.get("snapshotUnavailable"):
        text = f"{control['name']} ({control['id']}) has no stored snapshot. Pass rate and RAG were not invented."
        movement = "No stored result is available."
        position = "Thresholds were not applied because no snapshot is stored."
    else:
        text = (
            f"{control['name']} ({control['id']}) pass rate is {control['passRate']}% "
            f"on {control['asOf']} ({control['failed']} failed of {control['total']}). "
            f"The stored RAG is {control['status']}."
        )
        movement = (
            f"The first stored red date is {control['firstRed']}."
            if control.get("firstRed")
            else "The stored series has no red row."
        )
        position = f"Green is {control['green']}% and amber is {control['amber']}%."
    return {
        "controlId": control["id"],
        "text": text,
        "movement": movement,
        "thresholdPosition": position,
        "implications": "This restates stored facts. It does not add a cause.",
        "disclaimer": DETERMINISTIC_DISCLAIMER,
        "source": "deterministic",
        "cached": False,
        "generatedAt": None,
    }


def deterministic_investigation(control: dict, desks: dict, notes: dict) -> dict:
    established = established_lines(control, desks, notes)
    hypotheses: list[str] = []
    steps: list[str] = []
    if control.get("plantedStory"):
        hypotheses.append(f"Planted-story context: {control['plantedStory']}")
    for note in notes.get("commentary") or []:
        if note.get("text"):
            hypotheses.append(note["text"])
        if note.get("path"):
            steps.append(note["path"])
    return {
        "kind": "data_quality",
        "metricId": control["id"],
        "name": control["name"],
        "dimension": control["dimension"],
        "readme": control.get("plantedStory") or "",
        "summary": established[0],
        "whatChanged": established[1] if len(established) > 1 else established[0],
        "whyItMatters": "The stored reading is shown against the stored thresholds. No cause was inferred.",
        "hypotheses": hypotheses,
        "validationSteps": steps,
        "established": established,
        "hypothesis": hypotheses,
        "notSupplied": [NOT_SUPPLIED],
        "discrepancy": None,
        "disclaimer": DETERMINISTIC_DISCLAIMER,
        "desks": desks,
        "notes": notes,
        "exceptions": {
            "total": control.get("exceptionCount") or 0,
            "open": control.get("openExceptions") or 0,
            "oldestAge": control.get("oldestOpenAge"),
        },
        "source": "deterministic",
        "stale": False,
        "cached": False,
        "generatedAt": None,
    }
