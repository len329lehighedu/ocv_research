#!/usr/bin/env python3
"""Rebuild and fit the supplementary 12-month any-active-outbreak measure.

The measure is log1p of the number of preceding calendar months with at least
one recorded active outbreak. It uses the same outcomes, sample window, model,
and seeded WCLR-C procedure as revise_active_outbreak_results.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from research_pipeline.data.build_active_outbreak_panel import COUNTRY_NAMES, FIRST_MONTH, LAST_MONTH
from research_pipeline.results.revise_active_outbreak_results import OUTCOMES, SAMPLES, fit_one, validate
from research_pipeline.results.wild_cluster_bootstrap import wclr_c_pvalue


ROOT = Path(__file__).resolve().parents[3]


def build_predictor(outbreaks: pd.DataFrame, primary_panel: pd.DataFrame) -> pd.DataFrame:
    validate(primary_panel)
    countries = sorted(primary_panel.country.unique())
    months = pd.period_range(FIRST_MONTH, LAST_MONTH, freq="M")
    active = {(country, month): 0 for country in countries for month in months}

    records = outbreaks.copy()
    records["start_date"] = pd.to_datetime(records.start_date, errors="raise")
    records["end_date"] = pd.to_datetime(records.end_date, errors="raise")
    records["country_name"] = records.country.map(COUNTRY_NAMES)
    if records.country_name.isna().any():
        raise ValueError("Unmapped outbreak country code")
    for record in records.itertuples(index=False):
        # Use the same country crosswalk as the primary predictor, including
        # the separately coded Zanzibar outbreak under Tanzania.
        if record.country_name not in countries:
            continue
        first = max(record.start_date.to_period("M"), FIRST_MONTH)
        last = min(record.end_date.to_period("M"), LAST_MONTH)
        if first <= last:
            for month in pd.period_range(first, last, freq="M"):
                active[(record.country_name, month)] += 1

    history = pd.MultiIndex.from_product(
        [countries, months], names=["country", "period"]
    ).to_frame(index=False)
    history["active_outbreaks_this_month"] = [
        active[(row.country, row.period)] for row in history.itertuples(index=False)
    ]
    history["any_active_this_month"] = history.active_outbreaks_this_month.gt(0).astype(int)
    history["any_active_months_prior_12m"] = history.groupby("country", sort=False)[
        "any_active_this_month"
    ].transform(lambda s: s.shift(1).rolling(12, min_periods=12).sum())
    history["yearmonth"] = history.period.astype(str)

    panel = primary_panel.merge(
        history[["country", "yearmonth", "active_outbreaks_this_month",
                 "any_active_months_prior_12m"]],
        on=["country", "yearmonth"], how="left", validate="one_to_one",
        suffixes=("", "_rebuilt"),
    )
    if not np.array_equal(
        panel.active_outbreaks_this_month.to_numpy(),
        panel.active_outbreaks_this_month_rebuilt.to_numpy(),
    ):
        raise ValueError("Rebuilt active-outbreak counts differ from the primary panel")
    if panel.any_active_months_prior_12m.isna().any():
        raise ValueError("Missing 12-month history")
    if not panel.any_active_months_prior_12m.between(0, 12).all():
        raise ValueError("Any-active-month count must be between 0 and 12")
    stem = "log1p_any_active_months_12m"
    panel[stem] = np.log1p(panel.any_active_months_prior_12m)
    panel[f"{stem}_between"] = panel.groupby("country")[stem].transform("mean")
    panel[f"{stem}_within"] = panel[stem] - panel[f"{stem}_between"]
    if not np.allclose(panel[stem], panel[f"{stem}_between"] + panel[f"{stem}_within"]):
        raise ValueError("Between/within decomposition failed")
    return panel


def estimate(panel: pd.DataFrame, reps: int, seed: int) -> pd.DataFrame:
    stem = "log1p_any_active_months_12m"
    terms = [f"{stem}_between", f"{stem}_within"]
    rows = []
    for sample_index, (n_countries, excluded) in enumerate(SAMPLES.items()):
        sample = panel.loc[~panel.country.isin(excluded)].copy()
        if len(sample) != 66 * n_countries or sample.country.nunique() != n_countries:
            raise ValueError("Sample size mismatch")
        for outcome_index, outcome in enumerate(OUTCOMES):
            X, fit = fit_one(sample, outcome, terms)
            ci = fit.conf_int(alpha=0.05)
            for term_index, (component, term) in enumerate(
                zip(("between", "within"), terms), start=1
            ):
                draw_seed = seed + 10000 * sample_index + 1000 * outcome_index + 120 + term_index
                p_boot, t_obs = wclr_c_pvalue(
                    X.to_numpy(dtype=float), sample[outcome].to_numpy(dtype=float),
                    sample.country.to_numpy(), fit, term_index, reps, draw_seed,
                )
                rows.append({
                    "outcome": outcome,
                    "predictor": stem,
                    "countries": n_countries,
                    "excluded_countries": "; ".join(sorted(excluded)),
                    "component": component,
                    "coefficient_log_odds": float(fit.params[term]),
                    "ci95_low_asymptotic": float(ci.loc[term, 0]),
                    "ci95_high_asymptotic": float(ci.loc[term, 1]),
                    "p_asymptotic": float(fit.pvalues[term]),
                    "p_wclr_c_rademacher": p_boot,
                    "t_cv1_for_wclr_c": t_obs,
                    "bootstrap_reps": reps,
                    "bootstrap_seed": draw_seed,
                    "country_months": len(sample),
                    "event_months": int(sample[outcome].sum()),
                })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbreaks", type=Path,
                        default=ROOT / "fundamental_data" / "zheng_outbreak_records.csv")
    parser.add_argument("--panel", type=Path,
                        default=ROOT / "outputs" / "analysis_data" / "active_outbreak_panel.csv")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "outputs" / "analysis_data"
                        / "any_active_months_sensitivity_seeded.csv")
    parser.add_argument("--reps", type=int, default=99999)
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()
    panel = build_predictor(pd.read_csv(args.outbreaks), pd.read_csv(args.panel))
    results = estimate(panel, args.reps, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False, float_format="%.12g")
    print(f"Saved {len(results)} rows to {args.output}")
    print(results[["outcome", "countries", "component", "coefficient_log_odds",
                   "p_wclr_c_rademacher"]].to_string(index=False))


if __name__ == "__main__":
    main()
