#!/usr/bin/env python3
"""Read-only audit of recorded outbreak opportunity in the frozen panel.

This is descriptive. It does not fit a model, alter an outcome, or interpret
Zheng records as a complete census of cholera episodes. Each source row is a
record, and each inclusive calendar-month overlap is one record-month.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.main.code.research_pipeline.data.build_active_outbreak_panel import COUNTRY_NAMES


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/source/zheng_outbreak_records.csv"
PANEL = ROOT / "analysis/main/outputs/analysis_data/active_outbreak_panel.csv"
OUTCOMES = ROOT / "analysis/main/outputs/analysis_data/request_outcomes.csv"
START = pd.Period("2014-07", freq="M")
END = pd.Period("2019-12", freq="M")
HISTORY_START = START - 12


def audit() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = pd.read_csv(PANEL)
    outcomes = pd.read_csv(OUTCOMES)
    records = pd.read_csv(SOURCE)
    if len(records) != 999:
        raise AssertionError("Unexpected Zheng source-row count")
    if len(panel) != 1650 or panel.country.nunique() != 25:
        raise AssertionError("Frozen panel must contain 25 x 66 rows")
    if len(outcomes) != len(panel) or outcomes.duplicated(["country", "yearmonth"]).any():
        raise AssertionError("Outcome panel size/key error")
    if int(panel.reactive_request.sum()) != 58:
        raise AssertionError("Reactive event-month total changed")
    required_panel = [
        "active_outbreaks_this_month", "active_outbreak_months_prior_12m",
        "log1p_active_outbreak_months_12m",
        "log1p_active_outbreak_months_12m_between",
        "log1p_active_outbreak_months_12m_within",
    ]
    if panel[required_panel].isna().any().any():
        raise AssertionError("Missing frozen-panel predictor values")
    p = panel.merge(outcomes, on=["country", "yearmonth"], validate="one_to_one", suffixes=("", "_source"))
    for col in ("reactive_request", "request_this_month"):
        if not p[col].equals(p[f"{col}_source"]):
            raise AssertionError(f"Frozen panel disagrees with outcomes: {col}")
    countries = set(panel.country)
    expected = {str(x) for x in pd.period_range(START, END, freq="M")}
    for country, group in panel.groupby("country"):
        if len(group) != 66 or set(group.yearmonth) != expected:
            raise AssertionError(f"Incomplete months: {country}")

    records["start_date"] = pd.to_datetime(records.start_date, errors="raise")
    records["end_date"] = pd.to_datetime(records.end_date, errors="raise")
    if records[["start_date", "end_date"]].isna().any().any():
        raise AssertionError("Missing source dates")
    if records.end_date.lt(records.start_date).any():
        raise AssertionError("End precedes start")
    if int(records.country.eq("TZA_zanzibar").sum()) != 1:
        raise AssertionError("Unexpected Zanzibar records")
    records["country_name"] = records.country.map(COUNTRY_NAMES)
    if records.country_name.isna().any():
        raise AssertionError("Unmapped source country code")

    # Expand source rows independently of the pipeline's shift/rolling code.
    active: dict[tuple[str, pd.Period], int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    panel_intersections: dict[str, int] = defaultdict(int)
    history_intersections: dict[str, int] = defaultdict(int)
    for row in records.itertuples(index=False):
        c = row.country_name
        if c not in countries:
            continue
        source_counts[c] += 1
        first, last = row.start_date.to_period("M"), row.end_date.to_period("M")
        if first <= END and last >= START:
            panel_intersections[c] += 1
        if first <= END and last >= HISTORY_START:
            history_intersections[c] += 1
        for month in pd.period_range(max(first, HISTORY_START), min(last, END), freq="M") if first <= END and last >= HISTORY_START else []:
            active[(c, month)] += 1

    rebuilt = []
    for row in panel.itertuples(index=False):
        month = pd.Period(row.yearmonth, freq="M")
        current = active[(row.country, month)]
        prior12 = sum(active[(row.country, month - lag)] for lag in range(1, 13))
        if current != row.active_outbreaks_this_month or prior12 != row.active_outbreak_months_prior_12m:
            raise AssertionError(f"Monthly active count mismatch: {row.country} {month}")
        if not np.isclose(np.log1p(prior12), row.log1p_active_outbreak_months_12m, atol=1e-10):
            raise AssertionError(f"Log predictor mismatch: {row.country} {month}")
        rebuilt.append((row.country, row.yearmonth, current, prior12))
    rebuilt = pd.DataFrame(rebuilt, columns=["country", "yearmonth", "current", "prior12"])
    for country, group in panel.groupby("country"):
        b = group.log1p_active_outbreak_months_12m.mean()
        if not np.allclose(group.log1p_active_outbreak_months_12m_between, b, atol=1e-10):
            raise AssertionError(f"Between mean mismatch: {country}")
        if not np.allclose(group.log1p_active_outbreak_months_12m_within,
                           group.log1p_active_outbreak_months_12m - b, atol=1e-10):
            raise AssertionError(f"Within deviation mismatch: {country}")

    p["prior12_positive"] = p.active_outbreak_months_prior_12m.gt(0)
    p["current_positive"] = p.active_outbreaks_this_month.gt(0)
    rows = []
    for country, g in p.groupby("country", sort=True):
        request = g.reactive_request.eq(1)
        rows.append({
            "country": country,
            "source_records_all_years": source_counts[country],
            "records_intersecting_panel": panel_intersections[country],
            "records_intersecting_predictor_history": history_intersections[country],
            "active_record_months_panel": int(g.active_outbreaks_this_month.sum()),
            "months_current_active": int(g.current_positive.sum()),
            "months_prior12_positive": int(g.prior12_positive.sum()),
            "mean_log1p_prior12": round(g.log1p_active_outbreak_months_12m.mean(), 4),
            "reactive_request_months": int(request.sum()),
            "reactive_with_prior12_zero": int((request & ~g.prior12_positive).sum()),
            "reactive_with_current_zero": int((request & ~g.current_positive).sum()),
            "reactive_with_both_zero": int((request & ~g.current_positive & ~g.prior12_positive).sum()),
        })
    country = pd.DataFrame(rows)
    if country.source_records_all_years.sum() != 994:
        raise AssertionError("Unexpected number of source rows in 25 countries")
    cross = p.groupby(["prior12_positive", "current_positive"], dropna=False).agg(
        country_months=("reactive_request", "size"),
        reactive_request_months=("reactive_request", "sum"),
        countries=("country", "nunique"),
    ).reset_index()
    events_zero = p.loc[p.reactive_request.eq(1) & ~p.prior12_positive,
                        ["country", "yearmonth", "active_outbreaks_this_month"]]
    return country, cross, events_zero


if __name__ == "__main__":
    country, cross, events_zero = audit()
    print("COUNTRY AUDIT")
    print(country.to_string(index=False))
    print("\nPRIOR 12M × CURRENT-MONTH RECORDING")
    print(cross.to_string(index=False))
    print("\nREACTIVE REQUESTS WITH ZERO PRIOR-12M RECORDS")
    print(events_zero.to_string(index=False))
