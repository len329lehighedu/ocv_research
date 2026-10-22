#!/usr/bin/env python3
"""Build the current country-month panel from Zheng outbreak intervals.

Predictor: the number of *outbreak-months* in the preceding L months. An
outbreak active in three preceding months contributes three, not one. This
uses start/end dates, never the outbreak's eventual total case count.

Requires pandas and numpy. The input outcome panel must contain the audited
reactive_request indicator; this script never reclassifies requests.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


COUNTRY_NAMES = {
    "AGO": "Angola", "BEN": "Benin", "BDI": "Burundi", "CMR": "Cameroon",
    "TCD": "Chad", "COD": "DR Congo", "ETH": "Ethiopia", "GHA": "Ghana",
    "GIN": "Guinea", "CIV": "Ivory Coast", "KEN": "Kenya", "MWI": "Malawi",
    "MOZ": "Mozambique", "NAM": "Namibia", "NER": "Niger", "NGA": "Nigeria",
    "COG": "Republic of the Congo", "SLE": "Sierra Leone", "SOM": "Somalia",
    "SSD": "South Sudan", "SDN": "Sudan", "TZA": "Tanzania",
    "TZA_zanzibar": "Tanzania", "UGA": "Uganda", "ZMB": "Zambia",
    "ZWE": "Zimbabwe", "MLI": "Mali", "GNB": "Guinea-Bissau",
}
WINDOWS = (1, 3, 6, 12)
FIRST_MONTH = pd.Period("2013-07", freq="M")
LAST_MONTH = pd.Period("2019-12", freq="M")


def build(outbreaks: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    required_outcomes = {"country", "yearmonth", "reactive_request", "request_this_month"}
    required_outbreaks = {"country", "start_date", "end_date"}
    for label, frame, required in (
        ("outcomes", outcomes, required_outcomes),
        ("outbreaks", outbreaks, required_outbreaks),
    ):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} missing columns: {sorted(missing)}")
    if outcomes.duplicated(["country", "yearmonth"]).any():
        raise ValueError("Duplicate country-month keys in outcomes")
    if len(outcomes) != 1650 or outcomes.country.nunique() != 25:
        raise ValueError("Expected 25 countries x 66 outcome months")
    if int(outcomes.reactive_request.sum()) != 58:
        raise ValueError("Expected 58 audited reactive event-months")
    if int(outcomes.request_this_month.sum()) != 73:
        raise ValueError("Expected 73 all-request event-months")

    source = outbreaks.copy()
    source["start_date"] = pd.to_datetime(source.start_date, errors="raise")
    source["end_date"] = pd.to_datetime(source.end_date, errors="raise")
    if source[["start_date", "end_date"]].isna().any().any():
        raise ValueError("Missing outbreak start/end date")
    if source.end_date.lt(source.start_date).any():
        raise ValueError("Outbreak end precedes start")
    if int(source.country.eq("TZA_zanzibar").sum()) != 1:
        raise ValueError("Expected one separately coded Zanzibar outbreak record")
    source["country_name"] = source.country.map(COUNTRY_NAMES)
    if source.country_name.isna().any():
        raise ValueError("Unmapped outbreak country code")

    countries = sorted(outcomes.country.unique())
    months = pd.period_range(FIRST_MONTH, LAST_MONTH, freq="M")
    history = pd.MultiIndex.from_product(
        [countries, months], names=["country", "period"]
    ).to_frame(index=False)
    active = {(country, month): 0 for country in countries for month in months}
    # The source's separately coded Zanzibar outbreak is mapped to Tanzania,
    # the country represented in the 25-country outcome panel.
    for row in source.itertuples(index=False):
        if row.country_name not in countries:
            continue
        first = max(row.start_date.to_period("M"), FIRST_MONTH)
        last = min(row.end_date.to_period("M"), LAST_MONTH)
        if first <= last:
            for month in pd.period_range(first, last, freq="M"):
                active[(row.country_name, month)] += 1
    history["active_outbreaks_this_month"] = [
        active[(r.country, r.period)] for r in history.itertuples(index=False)
    ]

    for months_back in WINDOWS:
        count_col = f"active_outbreak_months_prior_{months_back}m"
        log_col = f"log1p_active_outbreak_months_{months_back}m"
        between_col = f"{log_col}_between"
        within_col = f"{log_col}_within"
        history[count_col] = history.groupby("country", sort=False)[
            "active_outbreaks_this_month"
        ].transform(
            lambda s: s.shift(1).rolling(months_back, min_periods=months_back).sum()
        )
        history[log_col] = np.log1p(history[count_col])
        # Country mean is calculated below on the common Jul 2014-Dec 2019
        # estimation period, not on all available history.
        history[between_col] = np.nan
        history[within_col] = np.nan

    history["yearmonth"] = history.period.astype(str)
    predictor_cols = ["country", "yearmonth", "active_outbreaks_this_month"]
    for months_back in WINDOWS:
        predictor_cols += [
            f"active_outbreak_months_prior_{months_back}m",
            f"log1p_active_outbreak_months_{months_back}m",
        ]
    panel = outcomes[["country", "yearmonth", "reactive_request", "request_this_month"]].merge(
        history[predictor_cols], on=["country", "yearmonth"],
        how="left", validate="one_to_one",
    ).sort_values(["country", "yearmonth"]).reset_index(drop=True)

    expected_months = set(pd.period_range("2014-07", "2019-12", freq="M").astype(str))
    if any(set(g.yearmonth) != expected_months for _, g in panel.groupby("country")):
        raise ValueError("At least one country lacks a complete estimation window")
    for months_back in WINDOWS:
        log_col = f"log1p_active_outbreak_months_{months_back}m"
        between_col = f"{log_col}_between"
        within_col = f"{log_col}_within"
        panel[between_col] = panel.groupby("country")[log_col].transform("mean")
        panel[within_col] = panel[log_col] - panel[between_col]
        if panel[[log_col, between_col, within_col]].isna().any().any():
            raise ValueError(f"Missing values in {months_back}-month predictor")
        if not np.allclose(panel[log_col], panel[between_col] + panel[within_col]):
            raise ValueError(f"Between/within decomposition fails for {months_back}m")
    return panel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbreaks", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    panel = build(pd.read_csv(args.outbreaks), pd.read_csv(args.outcomes))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False, float_format="%.12g")
    print(f"Saved {args.output}: {len(panel)} rows, {panel.country.nunique()} countries")
    print(f"Reactive event-months: {int(panel.reactive_request.sum())}")
    print(f"All-request event-months: {int(panel.request_this_month.sum())}")
    log_col = "log1p_active_outbreak_months_12m_within"
    no_variation = panel.groupby("country")[log_col].apply(lambda s: np.allclose(s, 0))
    print(f"No 12m within variation: {no_variation.index[no_variation].tolist()}")


if __name__ == "__main__":
    main()
