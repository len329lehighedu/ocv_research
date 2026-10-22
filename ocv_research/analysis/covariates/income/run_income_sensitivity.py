#!/usr/bin/env python3
"""Prespecified FY2015-income sensitivity; never edits the frozen analysis.

Read method_protocol.md before use. Validation and benchmark reproduction must
pass before any adjusted fit is reported. Outputs are a separate JSON record.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / "analysis/main"
PANEL = HERE / "active_outbreak_panel_income_fy2015.csv"
SOURCE_PANEL = FROZEN / "outputs/analysis_data/active_outbreak_panel.csv"
SOURCE_RESULTS = FROZEN / "outputs/analysis_data/active_outbreak_results_seeded.csv"
SOURCE_OUTBREAKS = ROOT / "data/source/zheng_outbreak_records.csv"
INCOME_LOOKUP = HERE / "country_income_fy2015.csv"
BOOTSTRAP = FROZEN / "code/research_pipeline/results/wild_cluster_bootstrap.py"
BETWEEN = "log1p_active_outbreak_months_12m_between"
WITHIN = "log1p_active_outbreak_months_12m_within"
LOG = "log1p_active_outbreak_months_12m"
COUNT = "active_outbreak_months_prior_12m"
INCOME = "low_income_fy2015"
TERMS = [BETWEEN, WITHIN, INCOME]
SEEDS = {BETWEEN: 20261128, WITHIN: 20261129}


def frozen_bootstrap_function():
    """Load the exact frozen implementation without copying its algorithm."""
    spec = importlib.util.spec_from_file_location("frozen_wclr_c", BOOTSTRAP)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen WCLR-C implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.wclr_c_pvalue


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_direct_interval_formula(panel: pd.DataFrame) -> dict:
    """Independently count record×month intersections, not a rolling transform.

    For record i and month m, its prior-year contribution is
    max(0, min(end_i,m-1) - max(start_i,m-12) + 1), in integer month units.
    This catches a current-month leak, endpoint error, and Zanzibar omission.
    """
    lookup = pd.read_csv(INCOME_LOOKUP)
    assert len(lookup) == 25 and lookup.country_panel.nunique() == 25
    assert set(lookup.country_panel) == set(panel.country)
    name_by_code = dict(zip(lookup.iso3, lookup.country_panel))
    name_by_code["TZA_zanzibar"] = "Tanzania"
    records = pd.read_csv(SOURCE_OUTBREAKS, usecols=["country", "start_date", "end_date"])
    assert int(records.country.eq("TZA_zanzibar").sum()) == 1
    starts = pd.to_datetime(records.start_date, errors="raise").dt.to_period("M")
    ends = pd.to_datetime(records.end_date, errors="raise").dt.to_period("M")
    assert (starts <= ends).all()
    grouped: dict[str, list[tuple[int, int]]] = {c: [] for c in panel.country.unique()}
    for code, start, end in zip(records.country, starts, ends):
        country = name_by_code.get(code)
        if country in grouped:
            grouped[country].append((start.ordinal, end.ordinal))
    checked = 0
    for row in panel.itertuples(index=False):
        m = pd.Period(row.yearmonth, freq="M").ordinal
        independent = sum(
            max(0, min(end, m - 1) - max(start, m - 12) + 1)
            for start, end in grouped[row.country]
        )
        assert independent == getattr(row, COUNT), (row.country, row.yearmonth)
        checked += 1
    return {"checked_country_months": checked, "source_outbreak_records": len(records)}


def fit(data: pd.DataFrame, terms: list[str]):
    X = sm.add_constant(data[terms], has_constant="add")
    result = sm.GLM(data["reactive_request"], X, family=sm.families.Binomial()).fit(
        cov_type="cluster",
        cov_kwds={"groups": data.country, "use_correction": False},
    )
    return X, result


def validate(panel: pd.DataFrame, source: pd.DataFrame) -> dict:
    assert len(panel) == len(source) == 1650
    assert list(panel.columns[:len(source.columns)]) == list(source.columns)
    pd.testing.assert_frame_equal(panel[source.columns], source, check_dtype=False)
    assert not panel.duplicated(["country", "yearmonth"]).any()
    assert panel.country.nunique() == 25
    assert panel.reactive_request.isin([0, 1]).all()
    assert panel[INCOME].isin([0, 1]).all()
    assert not panel.isna().any().any()
    assert int(panel.reactive_request.sum()) == 58
    expected_months = list(pd.period_range("2014-07", "2019-12", freq="M").astype(str))
    countries = []
    for country, part in panel.groupby("country", sort=True):
        assert part.yearmonth.tolist() == expected_months, country
        assert part[INCOME].nunique() == 1, country
        assert part.income_fy2015_group.nunique() == 1, country
        assert part[BETWEEN].nunique() == 1, country
        assert np.isclose(part[WITHIN].mean(), 0, atol=1e-10), country
        assert np.isclose(part[LOG].mean(), part[BETWEEN].iloc[0], atol=1e-10), country
        expected_income = int(part.income_fy2015_group.iloc[0] == "LIC")
        assert int(part[INCOME].iloc[0]) == expected_income, country
        countries.append({
            "country": country,
            "income_group": part.income_fy2015_group.iloc[0],
            "low_income_fy2015": int(part[INCOME].iloc[0]),
            "mean_recorded_log_activity": float(part[BETWEEN].iloc[0]),
            "reactive_event_months": int(part.reactive_request.sum()),
            "within_sd": float(part[WITHIN].std(ddof=0)),
        })
    assert np.allclose(panel[LOG], np.log1p(panel[COUNT]), atol=1e-10)
    assert np.allclose(panel[LOG], panel[BETWEEN] + panel[WITHIN], atol=1e-10)
    assert (panel[COUNT] >= 0).all()
    assert np.allclose(panel[COUNT], np.rint(panel[COUNT]))
    c = pd.DataFrame(countries)
    assert c.groupby("low_income_fy2015").size().to_dict() == {0: 10, 1: 15}
    event_by_group = c.groupby("low_income_fy2015").reactive_event_months.sum().to_dict()
    assert event_by_group == {0: 24, 1: 34}
    group_corr = float(c[INCOME].corr(c.mean_recorded_log_activity))
    assert abs(group_corr) < 0.9, "Near-collinear income and country-mean activity"
    raw = sm.add_constant(panel[TERMS], has_constant="add").to_numpy(dtype=float)
    standardized = raw.copy()
    standardized[:, 1:] = (raw[:, 1:] - raw[:, 1:].mean(axis=0)) / raw[:, 1:].std(axis=0)
    condition_number = float(np.linalg.cond(standardized))
    assert np.linalg.matrix_rank(raw) == 4, "Rank-deficient design"
    assert condition_number < 30, "Poorly conditioned design"
    return {
        "countries": countries,
        "income_between_correlation_country_level": group_corr,
        "standardized_design_condition_number": condition_number,
        "event_months_by_binary_income_group": event_by_group,
        "zero_between_countries": [row["country"] for row in countries if row["mean_recorded_log_activity"] == 0],
    }


def validate_frozen_benchmark(panel: pd.DataFrame, results: pd.DataFrame) -> dict:
    X, fit0 = fit(panel, [BETWEEN, WITHIN])
    rows = results.loc[
        results.outcome.eq("reactive_request")
        & results.lookback_months.eq(12)
        & results.countries.eq(25)
    ]
    assert len(rows) == 2
    ci = fit0.conf_int(alpha=0.05)
    for term, component in ((BETWEEN, "between"), (WITHIN, "within")):
        row = rows.loc[rows.component.eq(component)].iloc[0]
        assert np.isclose(fit0.params[term], row.coefficient_log_odds, atol=1e-10)
        assert np.isclose(ci.loc[term, 0], row.ci95_low_asymptotic, atol=1e-10)
        assert np.isclose(ci.loc[term, 1], row.ci95_high_asymptotic, atol=1e-10)
        assert np.isclose(fit0.aic, row.aic, atol=1e-9)
    return {
        "between_coefficient": float(fit0.params[BETWEEN]),
        "within_coefficient": float(fit0.params[WITHIN]),
        "aic": float(fit0.aic),
        "source_bootstrap_p_between": float(rows.loc[rows.component.eq("between"), "p_wclr_c_rademacher"].iloc[0]),
        "source_bootstrap_p_within": float(rows.loc[rows.component.eq("within"), "p_wclr_c_rademacher"].iloc[0]),
    }


def coefficient_record(result, term: str) -> dict:
    ci = result.conf_int(alpha=0.05).loc[term]
    beta = float(result.params[term])
    return {
        "coefficient_log_odds": beta,
        "odds_ratio": float(np.exp(beta)),
        "ci95_log_odds_cluster_asymptotic": [float(ci.iloc[0]), float(ci.iloc[1])],
        "ci95_odds_ratio_cluster_asymptotic": [float(np.exp(ci.iloc[0])), float(np.exp(ci.iloc[1]))],
    }


def run(reps: int) -> dict:
    panel = pd.read_csv(PANEL)
    source = pd.read_csv(SOURCE_PANEL)
    frozen = pd.read_csv(SOURCE_RESULTS)
    diagnostics = validate(panel, source)
    diagnostics["independent_interval_count_check"] = validate_direct_interval_formula(panel)
    benchmark = validate_frozen_benchmark(panel, frozen)
    X, adjusted = fit(panel, TERMS)
    assert adjusted.converged, "Adjusted GLM did not converge"
    assert np.isfinite(adjusted.params).all()
    assert np.isfinite(adjusted.bse).all()
    pred = np.asarray(adjusted.fittedvalues)
    assert np.isfinite(pred).all()
    assert pred.min() > 1e-12 and pred.max() < 1 - 1e-12, "Potential separation"
    # A sensitivity to any single country is a diagnostic, never a model-selection menu.
    deletions = []
    for country in sorted(panel.country.unique()):
        _, deletion_fit = fit(panel.loc[panel.country.ne(country)], TERMS)
        if not deletion_fit.converged or not np.isfinite(deletion_fit.params).all():
            raise RuntimeError(f"Unstable one-country-deleted fit: {country}")
        deletions.append({"omitted_country": country, **{
            term: float(deletion_fit.params[term]) for term in TERMS
        }})
    diagnostics["one_country_deleted_coefficients"] = deletions
    diagnostics["one_country_deleted_ranges"] = {
        term: [min(r[term] for r in deletions), max(r[term] for r in deletions)]
        for term in TERMS
    }
    wclr_c = frozen_bootstrap_function()
    coefficients = {term: coefficient_record(adjusted, term) for term in TERMS}
    for term in (BETWEEN, WITHIN):
        p, observed_t = wclr_c(
            X.to_numpy(dtype=float),
            panel.reactive_request.to_numpy(dtype=float),
            panel.country.to_numpy(),
            adjusted,
            X.columns.get_loc(term),
            reps,
            SEEDS[term],
        )
        coefficients[term].update({
            "p_wclr_c_rademacher": None if np.isnan(p) else float(p),
            "t_cv1_for_wclr_c": observed_t,
            "bootstrap_reps": reps,
            "bootstrap_seed": SEEDS[term],
        })
    diagnostics["fitted_probability_range"] = [float(pred.min()), float(pred.max())]
    return {
        "status": "optional_sensitivity_not_frozen_main",
        "formula": "logit P(reactive_request_cm=1) = intercept + beta_B * between12_c + beta_W * within12_cm + gamma * low_income_fy2015_c",
        "n_countries": 25,
        "n_country_months": len(panel),
        "n_reactive_event_months": int(panel.reactive_request.sum()),
        "asymptotic_ci": "Country-clustered sandwich, use_correction=False; 95% normal CI",
        "bootstrap": "Frozen restricted score-linearized WCLR-C; Rademacher; CV1 observed/studentized t",
        "aic": float(adjusted.aic),
        "coefficients": coefficients,
        "frozen_benchmark_reproduced": benchmark,
        "diagnostics": diagnostics,
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in (
            PANEL, INCOME_LOOKUP, SOURCE_PANEL, SOURCE_OUTBREAKS, SOURCE_RESULTS, BOOTSTRAP
        )},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=99999)
    parser.add_argument("--output", type=Path, default=HERE / "income_sensitivity_results.json")
    args = parser.parse_args()
    if args.reps < 0:
        parser.error("--reps must be nonnegative")
    result = run(args.reps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"Saved {args.output}")
    for term, record in result["coefficients"].items():
        print(term, record)


if __name__ == "__main__":
    main()
