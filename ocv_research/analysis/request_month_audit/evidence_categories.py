"""Map the reviewed audit rows to DD, Q, CW and NE categories.
Manuscript: Methods 2.4; Results 3.1; Table S7 and supplementary references.
Internal source IDs differ from the published reference numbers."""

DATE_AND_DOSE = frozenset({"Z04", "Z18"})
QUANTITY_CANDIDATE = frozenset({"Z06"})
COUNTRY_WINDOW = frozenset({
    "Z01", "Z05", "Z07", "Z08", "Z09", "Z10", "Z14", "Z15", "Z16",
    "Z17", "Z19", "Z20", "Z21", "Z22",
})
NOT_ESTABLISHED = frozenset({"Z02", "Z03", "Z11", "Z12", "Z13"})

CATEGORY_LABELS = {
    "DD": "Date-and-dose correspondence; dashboard ID not independently confirmed",
    "Q": "Quantity-only candidate correspondence; identity not established",
    "CW": "Country/window documentation only; specific request linkage not established",
    "NE": "Preceding-window activity not established; not evidence of absence",
}

REFERENCE_NUMBERS = {
    "S01": "S3", "S02": "S5", "S03": "S6", "S04": "S7", "S05": "S8",
    "S06": "S9", "S07": "S11", "S08": "S13", "S09": "S12", "S10": "S10",
    "S11": "S14", "S13": "S16", "S14": "S17", "S15": "S18", "S16": "S19",
    "S17": "S20", "S18": "S21", "S19": "S22", "S20": "S23", "S21": "S24",
    "S22": "S25", "S23": "S15",
}


def category(audit_id):
    """Return the single reviewed evidence category for an audit row."""
    groups = {"DD": DATE_AND_DOSE, "Q": QUANTITY_CANDIDATE,
              "CW": COUNTRY_WINDOW, "NE": NOT_ESTABLISHED}
    matches = [label for label, ids in groups.items() if audit_id in ids]
    if len(matches) != 1:
        raise ValueError(f"Missing or overlapping revision category: {audit_id}")
    return matches[0]


def source_citations(audit_id, source_ids):
    """Format supplementary reference numbers and retain case-specific caveats."""
    if audit_id == "Z02":
        return "[S4], request record only; audit search log. No qualifying external activity source identified."
    numbers = sorted({REFERENCE_NUMBERS[sid] for sid in source_ids}, key=lambda value: int(value[1:]))
    text = ", ".join(f"[{number}]" for number in numbers)
    if audit_id in {"Z03", "Z12", "Z13"}:
        text += "; context only"
    if audit_id == "Z11":
        text += "; cumulative/weekly reporting does not establish activity in this window"
    return text
