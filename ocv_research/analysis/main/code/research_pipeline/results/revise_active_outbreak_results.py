#!/usr/bin/env python3
"""Re-estimate the country-month models with recorded active outbreak-months.

The primary predictor for month t is log1p of the sum of the number of
outbreaks active in months t-12 through t-1. Country means and deviations are
calculated over the common July 2014--December 2019 estimation sample.

This script reports asymptotic country-clustered CIs and seeded WCLR-C
Rademacher p-values for the main and robustness models. The WCLR-C procedure
must be reconciled with the manuscript's original bootstrap implementation
before its p-values replace the manuscript's reported values.

The pending-dose secondary analysis is not included because its original
global-pending predictor has not been reconstructed and verified.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from research_pipeline.results.wild_cluster_bootstrap import wclr_c_pvalue


WINDOWS = (1, 3, 6, 12)
SAMPLES = {
    25: frozenset(),
    23: frozenset({"DR Congo", "South Sudan"}),
    22: frozenset({"DR Congo", "Nigeria", "South Sudan"}),
}
OUTCOMES = ("reactive_request", "request_this_month")


def validate(panel: pd.DataFrame) -> None:
    required = {"country", "yearmonth", "reactive_request", "request_this_month"}
    for window in WINDOWS:
        stem = f"log1p_active_outbreak_months_{window}m"
        required.update({stem, f"{stem}_between", f"{stem}_within"})
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"Missing panel columns: {sorted(missing)}")
    if panel.duplicated(["country", "yearmonth"]).any():
        raise ValueError("Duplicate country-month rows")
    if len(panel) != 1650 or panel.country.nunique() != 25:
        raise ValueError("Expected 25 countries and 1,650 months")
    if panel.isna().any().any():
        raise ValueError("Missing panel value")
    if int(panel.reactive_request.sum()) != 58:
        raise ValueError("Expected 58 reactive event-months")
    for outcome in OUTCOMES:
        if not panel[outcome].isin([0, 1]).all():
            raise ValueError(f"{outcome} must be binary")
    for window in WINDOWS:
        stem = f"log1p_active_outbreak_months_{window}m"
        if not np.allclose(
            panel[stem], panel[f"{stem}_between"] + panel[f"{stem}_within"], atol=1e-8
        ):
            raise ValueError(f"Decomposition fails for {window}m")


def fit_one(data: pd.DataFrame, outcome: str, terms: list[str]):
    X = sm.add_constant(data[terms], has_constant="add")
    fit = sm.GLM(data[outcome], X, family=sm.families.Binomial()).fit(
        cov_type="cluster",
        cov_kwds={"groups": data.country, "use_correction": False},
    )
    return X, fit


def primary_and_robustness(panel: pd.DataFrame, reps: int, seed: int) -> pd.DataFrame:
    rows = []
    for sample_index, (n_countries, excluded) in enumerate(SAMPLES.items()):
        sample = panel.loc[~panel.country.isin(excluded)].copy()
        if sample.country.nunique() != n_countries or len(sample) != 66 * n_countries:
            raise ValueError(f"Incorrect {n_countries}-country sample")
        for outcome_index, outcome in enumerate(OUTCOMES):
            for window in WINDOWS:
                stem = f"log1p_active_outbreak_months_{window}m"
                terms = [f"{stem}_between", f"{stem}_within"]
                X, fit = fit_one(sample, outcome, terms)
                ci = fit.conf_int(alpha=0.05)
                for term_index, (component, term) in enumerate(
                    zip(("between", "within"), terms), start=1
                ):
                    draw_seed = (
                        seed + 10000 * sample_index + 1000 * outcome_index
                        + 10 * window + term_index
                    )
                    bootstrap_p, observed_t = wclr_c_pvalue(
                        X.to_numpy(dtype=float),
                        sample[outcome].to_numpy(dtype=float),
                        sample.country.to_numpy(),
                        fit,
                        term_index,
                        reps,
                        draw_seed,
                    )
                    sd = float(sample[term].std(ddof=0))
                    rows.append({
                        "outcome": outcome,
                        "lookback_months": window,
                        "countries": n_countries,
                        "excluded_countries": "; ".join(sorted(excluded)),
                        "component": component,
                        "coefficient_log_odds": float(fit.params[term]),
                        "ci95_low_asymptotic": float(ci.loc[term, 0]),
                        "ci95_high_asymptotic": float(ci.loc[term, 1]),
                        "p_asymptotic": float(fit.pvalues[term]),
                        "component_sd": sd,
                        "coefficient_per_component_sd": float(fit.params[term] * sd),
                        "p_wclr_c_rademacher": bootstrap_p,
                        "t_cv1_for_wclr_c": observed_t,
                        "bootstrap_reps": reps,
                        "bootstrap_seed": draw_seed,
                        "country_months": len(sample),
                        "event_months": int(sample[outcome].sum()),
                        "aic": float(fit.aic),
                    })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reps", type=int, default=99999)
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()
    if args.reps < 0:
        parser.error("--reps must be nonnegative")
    panel = pd.read_csv(args.panel)
    validate(panel)
    results = primary_and_robustness(panel, args.reps, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(
        args.output_dir / "active_outbreak_results_seeded.csv",
        index=False,
        float_format="%.12g",
    )
    print("Saved seeded main/robustness results", len(results), "coefficient rows")
    print(results.loc[
        results.outcome.eq("reactive_request")
        & results.countries.eq(25)
        & results.lookback_months.eq(12),
        ["component", "coefficient_log_odds", "p_wclr_c_rademacher"],
    ].to_string(index=False))



if __name__ == "__main__":
    main()
