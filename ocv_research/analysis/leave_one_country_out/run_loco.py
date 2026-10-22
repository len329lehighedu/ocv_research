#!/usr/bin/env python3
"""Primary reactive-request model: baseline plus all 25 country omissions.

Coefficients are per unit of the logged predictor, not per SD. CIs use the
same asymptotic country-clustered sandwich (use_correction=False) as the
frozen main model. No bootstrap tests or random draws are performed here.
"""

from pathlib import Path
import argparse
import hashlib
import json
import platform
import sys
import warnings

import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.api as sm


HERE = Path(__file__).resolve().parent
STEM = "log1p_active_outbreak_months_12m"
TERMS = [STEM + "_between", STEM + "_within"]
COUNTRIES = (
    "Angola", "Benin", "Burundi", "Cameroon", "Chad", "DR Congo",
    "Ethiopia", "Ghana", "Guinea", "Ivory Coast", "Kenya", "Malawi",
    "Mozambique", "Namibia", "Niger", "Nigeria", "Republic of the Congo",
    "Sierra Leone", "Somalia", "South Sudan", "Sudan", "Tanzania", "Uganda",
    "Zambia", "Zimbabwe",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    # Unlike Python's assert, this check is not disabled by python -O.
    if not condition:
        raise ValueError(message)


def validate_panel(panel):
    require(set(panel.country.unique()) == set(COUNTRIES), "Unexpected country roster")
    require(len(panel) == 1650, "Expected 1,650 rows")
    require(not panel.duplicated(["country", "yearmonth"]).any(), "Duplicate keys")
    expected = set(pd.period_range("2014-07", "2019-12", freq="M").astype(str))
    for country, group in panel.groupby("country"):
        require(set(group.yearmonth) == expected, f"Incomplete months: {country}")
    required = ["reactive_request", "request_this_month", STEM, *TERMS]
    require(np.isfinite(panel[required].to_numpy(float)).all(), "Nonfinite input")
    require(panel.reactive_request.isin([0, 1]).all(), "Outcome is not binary")
    require(panel.reactive_request.sum() == 58, "Expected 58 reactive event-months")
    require(panel.request_this_month.sum() == 73, "Expected 73 all-request months")
    np.testing.assert_allclose(panel[STEM], panel[TERMS].sum(axis=1), rtol=0, atol=1e-12)
    means = panel.groupby("country")[STEM].transform("mean")
    np.testing.assert_allclose(panel[TERMS[0]], means, rtol=0, atol=1e-12)
    np.testing.assert_allclose(panel[TERMS[1]], panel[STEM] - means, rtol=0, atol=1e-12)


def fit_model(data):
    design = sm.add_constant(data[TERMS], has_constant="add")
    require(np.linalg.matrix_rank(design.to_numpy()) == 3, "Rank-deficient design")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fit = sm.GLM(data.reactive_request, design, family=sm.families.Binomial()).fit(
            cov_type="cluster",
            cov_kwds={"groups": data.country, "use_correction": False},
        )
    require(fit.converged, "GLM did not converge")
    require(np.isfinite(fit.params).all(), "Nonfinite coefficients")
    require(np.isfinite(fit.cov_params().to_numpy()).all(), "Nonfinite covariance")
    require((fit.bse > 0).all(), "Nonpositive standard errors")
    require(np.isfinite(fit.conf_int().to_numpy()).all(), "Nonfinite intervals")
    messages = [f"{w.category.__name__}: {w.message}" for w in caught]
    require(not any("Separation" in m or "converg" in m.lower() for m in messages),
            "Separation/convergence warning: " + "; ".join(messages))
    return fit, messages


def coefficient_rows(data, fit, omitted, baseline, messages):
    ci = fit.conf_int(alpha=0.05)
    rows = []
    for component, term in zip(("between", "within"), TERMS):
        coefficient = float(fit.params[term])
        rows.append({
            "omitted_country": omitted,
            "component": component,
            "coefficient_log_odds": coefficient,
            "ci95_low_asymptotic": float(ci.loc[term, 0]),
            "ci95_high_asymptotic": float(ci.loc[term, 1]),
            "se_country_clustered": float(fit.bse[term]),
            "baseline_coefficient": float(baseline.params[term]),
            "change_from_baseline": coefficient - float(baseline.params[term]),
            "absolute_change_from_baseline": abs(coefficient - float(baseline.params[term])),
            "countries": data.country.nunique(),
            "country_months": len(data),
            "event_months": int(data.reactive_request.sum()),
            "converged": bool(fit.converged),
            "iterations": fit.fit_history.get("iteration"),
            "warning_messages": "; ".join(messages),
            "ci_method": "asymptotic country-clustered; use_correction=False",
            "scale": "per one unit of the logged component; not standardized",
        })
    return rows


def run(panel, frozen_results, output):
    validate_panel(panel)
    baseline, messages = fit_model(panel)
    reference = frozen_results.loc[
        frozen_results.outcome.eq("reactive_request")
        & frozen_results.lookback_months.eq(12)
        & frozen_results.countries.eq(25)
    ].set_index("component")
    require(len(reference) == 2 and reference.index.is_unique, "Ambiguous frozen baseline")
    ci = baseline.conf_int()
    for component, term in zip(("between", "within"), TERMS):
        computed = [baseline.params[term], ci.loc[term, 0], ci.loc[term, 1]]
        saved = reference.loc[component, [
            "coefficient_log_odds", "ci95_low_asymptotic", "ci95_high_asymptotic",
        ]].to_numpy(float)
        np.testing.assert_allclose(computed, saved, rtol=0, atol=1e-8)
    print("PASS: reconstructed baseline matches frozen coefficients AND CIs.", flush=True)
    rows = coefficient_rows(panel, baseline, "None (full sample)", baseline, messages)
    diagnostics, failures = [], []
    for index, omitted in enumerate(COUNTRIES, start=1):
        sample = panel.loc[panel.country.ne(omitted)].copy()
        removed = panel.loc[panel.country.eq(omitted)]
        require(len(removed) == 66 and len(sample) == 1584, "Incorrect deletion size")
        require(set(sample.country.unique()) == set(COUNTRIES) - {omitted}, "Wrong deletion")
        require(sample.reactive_request.sum() + removed.reactive_request.sum() == 58,
                "Events fail to reconcile after deletion")
        diagnostic = {
            "omitted_country": omitted, "retained_countries": sample.country.nunique(),
            "removed_rows": len(removed), "retained_rows": len(sample),
            "removed_events": int(removed.reactive_request.sum()),
            "retained_events": int(sample.reactive_request.sum()),
        }
        try:
            fit, caught = fit_model(sample)
            rows.extend(coefficient_rows(sample, fit, omitted, baseline, caught))
            diagnostic.update(status="estimated", warnings="; ".join(caught))
            print(f"{index:02d}/25 omit {omitted}: N=1584, events={diagnostic['retained_events']}, "
                  f"between={fit.params[TERMS[0]]:.6f}, within={fit.params[TERMS[1]]:.6f}", flush=True)
        except (ValueError, np.linalg.LinAlgError) as error:
            # Save a visible failed row; never silently omit a difficult country.
            diagnostic.update(status="failed", warnings=str(error))
            failures.append(omitted)
            print(f"FAILED: {omitted}: {error}", flush=True)
        diagnostics.append(diagnostic)
    output.mkdir(parents=True, exist_ok=True)
    results = pd.DataFrame(rows)
    results.to_csv(output / "loco_coefficients.csv", index=False, float_format="%.17g")
    pd.DataFrame(diagnostics).to_csv(output / "country_omission_checks.csv", index=False)
    roster = panel.groupby("country", as_index=False).agg(
        country_months=("yearmonth", "size"),
        reactive_request_months=("reactive_request", "sum"),
        active_record_months=("active_outbreaks_this_month", "sum"),
    )
    roster["share_of_active_record_months"] = roster.active_record_months / roster.active_record_months.sum()
    roster.to_csv(output / "country_roster.csv", index=False, float_format="%.17g")
    require(not failures, f"Failed fits recorded in diagnostic CSV: {failures}")
    require(len(results) == 52, "Expected 2 baseline + 50 omission coefficients")
    omitted_results = results.loc[results.omitted_country.ne("None (full sample)")]
    require(set(omitted_results.omitted_country) == set(COUNTRIES), "Missing country result")
    require(omitted_results.groupby("omitted_country").size().eq(2).all(), "Missing component")
    print("\nPASS: 25/25 countries omitted exactly once, including Ethiopia; 50 LOCO coefficients.")
    for component in ("between", "within"):
        group = omitted_results.loc[omitted_results.component.eq(component)]
        extreme = group.loc[group.absolute_change_from_baseline.idxmax()]
        print(f"{component}: range [{group.coefficient_log_odds.min():.6f}, "
              f"{group.coefficient_log_odds.max():.6f}]; largest absolute change "
              f"{extreme.absolute_change_from_baseline:.6f} omitting {extreme.omitted_country}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE / "outputs")
    args = parser.parse_args()
    inputs = HERE / "inputs"
    provenance = json.loads((inputs / "provenance.json").read_text())
    for name, expected in provenance["snapshot_sha256"].items():
        require(sha256(inputs / name) == expected, f"Input changed since preparation: {name}")
    panel = pd.read_csv(inputs / "panel_rebuilt.csv")
    frozen = pd.read_csv(inputs / "active_outbreak_results_seeded.csv")
    run(panel, frozen, args.output_dir)
    for name, expected in provenance["snapshot_sha256"].items():
        require(sha256(inputs / name) == expected, f"Input changed during fitting: {name}")
    record = {
        "python": sys.version, "platform": platform.platform(),
        "numpy": np.__version__, "pandas": pd.__version__,
        "scipy": scipy.__version__, "statsmodels": statsmodels.__version__,
        "script_sha256": sha256(__file__), "input_sha256": provenance["snapshot_sha256"],
        "random_seed": None, "bootstrap_repetitions": 0,
        "reason_no_seed": "Deterministic GLM/clustered CIs; no random draws or bootstrap p-values.",
        "original_inputs_unchanged": True,
    }
    (args.output_dir / "run_manifest.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
