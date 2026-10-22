#!/usr/bin/env python3
"""Rebuild the manuscript's request classification and dose reconciliation.

Writes row-level data for Supplement Tables S1–S3 from the preserved request
CSV. A missing numeric approval is not interpreted as zero doses delivered.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


CATEGORY_ORDER = (
    "Requested and approved quantities equal",
    "Partially approved",
    "Approved quantity exceeds requested quantity",
    "Approved quantity recorded; requested quantity missing",
    "Marked not approved",
    "Marked cancelled",
    "No decision date or approved quantity logged",
)
DETAIL_LABELS = {
    CATEGORY_ORDER[1]: "Partial approval",
    CATEGORY_ORDER[2]: "Approved excess",
    CATEGORY_ORDER[3]: "Missing requested dose",
    CATEGORY_ORDER[4]: "Not approved",
    CATEGORY_ORDER[5]: "Cancelled",
    CATEGORY_ORDER[6]: "No logged decision",
}


def classify(source: pd.DataFrame) -> pd.DataFrame:
    requests = source.copy()
    requests["parsed_date"] = pd.to_datetime(
        requests.request_date, format="%m/%d/%Y", errors="coerce"
    )
    requests = requests.loc[requests.parsed_date.notna()].copy()
    if len(requests) != 88:
        raise ValueError("Expected 88 dated request records")
    requests["requested"] = pd.to_numeric(requests.doses_requested, errors="coerce")
    requests["approved"] = pd.to_numeric(requests.doses_approved, errors="coerce")

    categories = []
    for row in requests.itertuples(index=False):
        if pd.notna(row.approved):
            if pd.isna(row.requested):
                category = CATEGORY_ORDER[3]
            elif row.approved == row.requested:
                category = CATEGORY_ORDER[0]
            elif row.approved < row.requested:
                category = CATEGORY_ORDER[1]
            else:
                category = CATEGORY_ORDER[2]
        elif row.doses_approved == "NOT APPROVED":
            category = CATEGORY_ORDER[4]
        elif row.doses_approved == "CANCELLED":
            category = CATEGORY_ORDER[5]
        elif row.doses_approved == "n/a" and row.decision_date == "n/a":
            category = CATEGORY_ORDER[6]
        else:
            raise ValueError(f"Unclassified request: {row.country}, {row.request_id}")
        categories.append(category)
    requests["category"] = pd.Categorical(
        categories, categories=CATEGORY_ORDER, ordered=True
    )
    return requests


def make_tables(requests: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s1 = requests.groupby("category", observed=True).agg(
        requests=("country", "size"),
        requested_doses=("requested", "sum"),
        numeric_approved_doses=("approved", "sum"),
    ).reset_index()
    for category in (CATEGORY_ORDER[4], CATEGORY_ORDER[5], CATEGORY_ORDER[6]):
        s1.loc[s1.category.eq(category), "numeric_approved_doses"] = pd.NA
    s1.loc[s1.category.eq(CATEGORY_ORDER[3]), "requested_doses"] = pd.NA
    s1["requested_doses"] = s1.requested_doses.astype("Int64")
    s1["numeric_approved_doses"] = s1.numeric_approved_doses.astype("Int64")
    if s1.requests.tolist() != [48, 12, 1, 1, 13, 2, 11]:
        raise ValueError("Supplement S1 category counts changed")
    s1["category"] = s1.category.astype(str)
    s1 = pd.concat([
        s1,
        pd.DataFrame([{
            "category": "Total",
            "requests": len(requests),
            "requested_doses": int(requests.requested.sum()),
            "numeric_approved_doses": int(requests.approved.sum()),
        }]),
    ], ignore_index=True)

    total_requested = int(requests.requested.sum())
    total_approved = int(requests.approved.sum())
    not_approved = int(requests.loc[requests.category.eq(CATEGORY_ORDER[4]), "requested"].sum())
    cancelled = int(requests.loc[requests.category.eq(CATEGORY_ORDER[5]), "requested"].sum())
    no_decision = int(requests.loc[requests.category.eq(CATEGORY_ORDER[6]), "requested"].sum())
    partial = requests.loc[requests.category.eq(CATEGORY_ORDER[1])]
    shortfall = int((partial.requested - partial.approved).sum())
    excess = int((requests.loc[requests.category.eq(CATEGORY_ORDER[2]), "approved"]
                  - requests.loc[requests.category.eq(CATEGORY_ORDER[2]), "requested"]).sum())
    missing_request = int(requests.loc[requests.category.eq(CATEGORY_ORDER[3]), "approved"].sum())
    steps = [
        ("Requested doses", total_requested),
        ("Requests marked not approved", -not_approved),
        ("Cancelled requests", -cancelled),
        ("Requests with no logged decision", -no_decision),
        ("Unapproved portion of partially approved requests", -shortfall),
        ("Tanzania: approved quantity above requested quantity", excess),
        ("Malawi: approved quantity with requested quantity missing", missing_request),
    ]
    running = 0
    rows = []
    for label, change in steps:
        running += change
        rows.append({"step": label, "change_doses": change, "running_total": running})
    s2 = pd.DataFrame(rows)
    if (total_requested, total_approved, running) != (89088648, 53998292, 53998292):
        raise ValueError("Supplement S2 total does not reconcile")

    detail = requests.loc[~requests.category.eq(CATEGORY_ORDER[0])].copy()
    detail["category"] = detail.category.map(DETAIL_LABELS).astype(str)
    detail["request_id_display"] = detail.request_id.where(
        detail.request_id.ne("n/a"), "External record, 24 Jan 2014"
    )
    detail["requested_doses"] = detail.requested.astype("Int64")
    detail["numeric_approved_doses"] = detail.approved.astype("Int64")
    detail = detail[["category", "country", "request_id_display",
                     "requested_doses", "numeric_approved_doses"]]
    detail = detail.sort_values(["category", "country", "request_id_display"])
    if len(detail) != 40:
        raise ValueError("Supplement S3 should list 40 non-equal request records")
    return s1, s2, detail


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    source = pd.read_csv(args.requests, keep_default_na=False)
    s1, s2, s3 = make_tables(classify(source))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in (
        ("supplement_s1_request_classification.csv", s1),
        ("supplement_s2_dose_reconciliation.csv", s2),
        ("supplement_s3_nonstandard_requests.csv", s3),
    ):
        frame.to_csv(args.output_dir / name, index=False)
        print(f"Saved {name}: {len(frame)} rows")


if __name__ == "__main__":
    main()
