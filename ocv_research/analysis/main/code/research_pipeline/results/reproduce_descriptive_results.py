#!/usr/bin/env python3
"""Recalculate manuscript Section 3.1 source-data and timing summaries.

Prints unrounded values so manuscript rounding and denominator choices remain
auditable. The 2013-2019 outbreak-source summary and the country-month
predictor both assign the separately coded Zanzibar record to Tanzania.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def summarize(outbreaks: pd.DataFrame, requests: pd.DataFrame, deliveries: pd.DataFrame) -> None:
    starts = pd.to_datetime(outbreaks.start_date, errors="raise")
    source = outbreaks.loc[starts.dt.year.between(2013, 2019)].copy()
    country_codes = source.country.replace({"TZA_zanzibar": "TZA"})
    print("OUTBREAK SOURCE, starts in 2013-2019")
    print(f"recorded outbreak rows: {len(source)}")
    print(f"countries with recorded outbreaks: {country_codes.nunique()}")
    for name in (
        "total_suspected_cases", "total_confirmed_cases", "total_deaths",
        "duration", "threshold", "attack_rate", "cfr", "mean_R0",
        "population_density",
    ):
        values = pd.to_numeric(source[name], errors="coerce")
        print(f"mean {name}: {values.mean():.9f} (nonmissing n={values.notna().sum()})")
    print(f"rural share: {source.rural_urban.str.contains('Rural', na=False).mean():.9f}")

    req = requests.copy()
    req["date"] = pd.to_datetime(req.request_date, format="%m/%d/%Y", errors="coerce")
    req = req.loc[req.date.notna()].copy()
    req["requested"] = pd.to_numeric(req.doses_requested, errors="coerce")
    req["approved"] = pd.to_numeric(req.doses_approved, errors="coerce")
    dashboard = req.loc[req.request_id.ne("n/a")]
    print("\nREQUEST SOURCE, all available request dates")
    print(f"all request records including external: {len(req)}")
    print(f"dashboard request IDs: {dashboard.request_id.nunique()}")
    print(f"dashboard requests with positive approval: {dashboard.approved.gt(0).sum()}")
    print(f"campaign labels: {req.campaign_type.value_counts(dropna=False).to_dict()}")
    print(f"doses requested, millions, all records: {req.requested.sum()/1e6:.9f}")
    print(f"doses approved, millions, all records: {req.approved.sum()/1e6:.9f}")
    print(f"doses approved, millions, dashboard only: {dashboard.approved.sum()/1e6:.9f}")
    print(f"mean request-to-decision days: {pd.to_numeric(req.decision_days, errors='coerce').mean():.9f}")

    rounds = deliveries.copy()
    rounds["round"] = pd.to_numeric(rounds.round_number, errors="coerce")
    rounds["days"] = pd.to_numeric(rounds.days_since_decision, errors="coerce")
    rounds["doses"] = pd.to_numeric(rounds.doses_delivered, errors="coerce")
    rounds = rounds.loc[rounds["round"].notna()].copy()
    valid = rounds.loc[rounds.days.notna()]
    first = valid.loc[valid["round"].eq(1)]
    last = valid.sort_values("round").groupby("request_id").tail(1)
    print("\nDELIVERY SOURCE")
    print(f"delivery rounds: {len(rounds)}")
    print(f"delivery rounds / dashboard-approved requests: {len(rounds)/dashboard.approved.gt(0).sum():.9f}")
    print(f"doses delivered, millions: {rounds.doses.sum()/1e6:.9f}")
    print(f"first-delivery delay: mean={first.days.mean():.9f}, n={len(first)}")
    print(f"last-delivery delay: mean={last.days.mean():.9f}, n={len(last)}")
    print(f"all-round delay: mean={valid.days.mean():.9f}, n={len(valid)}")

    cancelled = req.loc[req.note.eq("CANCELLED VIA ICG"), "requested"].sum()
    no_decision = req.loc[req.decision_date.isin(["n/a", ""]), "requested"].sum()
    partial_shortfall = (req.requested - req.approved).clip(lower=0).sum()
    reconstructed = req.approved.sum() + cancelled + no_decision + partial_shortfall
    print("\nFIGURE 2 COMPONENTS, millions, unrounded")
    print(f"approved (all records): {req.approved.sum()/1e6:.9f}")
    print(f"cancelled: {cancelled/1e6:.9f}")
    print(f"no logged decision: {no_decision/1e6:.9f}")
    print(f"partial-approval shortfall: {partial_shortfall/1e6:.9f}")
    print(f"sum of components: {reconstructed/1e6:.9f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbreaks", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--deliveries", type=Path, required=True)
    args = parser.parse_args()
    summarize(
        pd.read_csv(args.outbreaks),
        pd.read_csv(args.requests, keep_default_na=False),
        pd.read_csv(args.deliveries, keep_default_na=False),
    )


if __name__ == "__main__":
    main()
