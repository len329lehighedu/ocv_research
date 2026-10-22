#!/usr/bin/env python3
"""Rebuild audited binary country-month outcomes from the request-level CSV.

The primary outcome counts only requests explicitly labelled Reactive. A
request with a missing campaign-type label counts toward the all-request
outcome but not the reactive outcome. Multiple requests in one country-month
still produce one event-month.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


FIRST_MONTH = "2014-07"
LAST_MONTH = "2019-12"


def build(requests: pd.DataFrame) -> pd.DataFrame:
    required = {"country", "request_id", "request_date", "campaign_type"}
    missing = required - set(requests.columns)
    if missing:
        raise ValueError(f"Missing request columns: {sorted(missing)}")
    countries = sorted(requests.country.dropna().unique())
    if len(countries) != 25 or not all(countries):
        raise ValueError("Expected exactly 25 named countries")

    dated = requests.copy()
    dated["request_date_parsed"] = pd.to_datetime(
        dated.request_date, format="%m/%d/%Y", errors="coerce"
    )
    undated = dated.loc[dated.request_date_parsed.isna()]
    if not undated.request_date.isin(["n/a", "", "NA"]).all():
        raise ValueError("Unparseable non-placeholder request date")
    dated = dated.loc[dated.request_date_parsed.notna()].copy()
    dated["yearmonth"] = dated.request_date_parsed.dt.to_period("M").astype(str)
    dated = dated.loc[dated.yearmonth.between(FIRST_MONTH, LAST_MONTH)].copy()
    if not dated.campaign_type.isin(["Reactive", "Preventive", ""]).all():
        raise ValueError("Unexpected campaign-type label in estimation period")
    if dated.request_id.duplicated().any():
        raise ValueError("Duplicate request IDs in estimation period")

    months = pd.period_range(FIRST_MONTH, LAST_MONTH, freq="M").astype(str)
    panel = pd.MultiIndex.from_product(
        [countries, months], names=["country", "yearmonth"]
    ).to_frame(index=False)
    dated["is_reactive"] = dated.campaign_type.eq("Reactive").astype(int)
    grouped = dated.groupby(["country", "yearmonth"], as_index=False).agg(
        n_requests_this_month=("request_id", "size"),
        reactive_request=("is_reactive", "max"),
    )
    panel = panel.merge(grouped, on=["country", "yearmonth"], how="left", validate="one_to_one")
    panel["n_requests_this_month"] = panel.n_requests_this_month.fillna(0).astype(int)
    panel["reactive_request"] = panel.reactive_request.fillna(0).astype(int)
    panel["request_this_month"] = panel.n_requests_this_month.gt(0).astype(int)
    panel = panel[["country", "yearmonth", "reactive_request", "request_this_month"]]
    if len(panel) != 1650 or panel.reactive_request.sum() != 58 or panel.request_this_month.sum() != 73:
        raise ValueError("Outcome panel does not reconcile to 1,650 rows and 58/73 event-months")
    return panel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    panel = build(pd.read_csv(args.requests, keep_default_na=False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    print(f"Saved {args.output}: {len(panel)} rows, 25 countries")
    print(f"Reactive event-months: {int(panel.reactive_request.sum())}")
    print(f"All-request event-months: {int(panel.request_this_month.sum())}")


if __name__ == "__main__":
    main()
