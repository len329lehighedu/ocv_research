#!/usr/bin/env python3
"""Two prespecified IHME 2013 expenditure sensitivities; frozen files stay read-only.

Read method_protocol.md first. All source, panel, and benchmark gates run before
either adjusted model is reported. The two expenditure measures are never joint.
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
ROOT = HERE.parents[3]
FROZEN = ROOT / "analysis/main"
PANEL = HERE / "active_outbreak_panel_ihme_2013.csv"
LOOKUP = HERE / "country_ihme_2013.csv"
SOURCE_CSV = HERE / "source/IHME_HEALTH_SPENDING_1995_2016_Y2019M09D30.CSV"
SOURCE_DTA = HERE / "source/IHME_HEALTH_SPENDING_1995_2016_Y2019M09D30.DTA"
SOURCE_INFO = HERE / "source/IHME_HEALTH_SPENDING_1995_2016_INFO_SHEET_Y2019M09D30.pdf"
COUNTRY_CROSSWALK = ROOT / "analysis/covariates/income/country_income_fy2015.csv"
SOURCE_PANEL = FROZEN / "outputs/analysis_data/active_outbreak_panel.csv"
SOURCE_RESULTS = FROZEN / "outputs/analysis_data/active_outbreak_results_seeded.csv"
SOURCE_OUTBREAKS = ROOT / "data/source/zheng_outbreak_records.csv"
BOOTSTRAP = FROZEN / "code/research_pipeline/results/wild_cluster_bootstrap.py"
BETWEEN = "log1p_active_outbreak_months_12m_between"
WITHIN = "log1p_active_outbreak_months_12m_within"
LOG = "log1p_active_outbreak_months_12m"
COUNT = "active_outbreak_months_prior_12m"
GOV_RAW = "ghes_per_cap_ppp_2013"
GOV_LOG = "log1p_ghes_per_cap_ppp_2013"
TOTAL_RAW = "the_per_cap_ppp_2013"
TOTAL_LOG = "log1p_the_per_cap_ppp_2013"
SEEDS = {BETWEEN: 20261128, WITHIN: 20261129}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_bootstrap():
    spec = importlib.util.spec_from_file_location("frozen_wclr_c", BOOTSTRAP)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the frozen WCLR-C implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.wclr_c_pvalue


def validate_ihme_releases() -> dict:
    """Check all released cells against DTA, then exact 25-country 2013 support."""
    csv = pd.read_csv(SOURCE_CSV)
    dta = pd.read_stata(SOURCE_DTA)
    assert csv.shape == dta.shape == (4554, 84)
    assert list(csv.columns) == list(dta.columns)
    assert not csv.duplicated(["location_id", "year"]).any()
    assert not dta.duplicated(["location_id", "year"]).any()
    csv = csv.sort_values(["location_id", "year"]).reset_index(drop=True)
    dta = dta.sort_values(["location_id", "year"]).reset_index(drop=True)
    for column in csv.columns:
        if pd.api.types.is_numeric_dtype(csv[column]):
            np.testing.assert_allclose(
                csv[column].to_numpy(dtype=float),
                dta[column].to_numpy(dtype=float),
                rtol=1e-9, atol=1e-9, equal_nan=True,
                err_msg=f"DTA/CSV mismatch: {column}",
            )
        else:
            assert csv[column].fillna("").astype(str).equals(
                dta[column].fillna("").astype(str)
            ), f"DTA/CSV mismatch: {column}"
    countries = csv.loc[(csv.year == 2013) & (csv.level == "Country")].copy()
    assert len(countries) == countries.iso3.nunique() == 195
    crosswalk = pd.read_csv(COUNTRY_CROSSWALK)
    assert len(crosswalk) == crosswalk.iso3.nunique() == 25
    subset = countries.loc[countries.iso3.isin(crosswalk.iso3)]
    assert len(subset) == subset.iso3.nunique() == 25
    for stem in ("ghes_per_cap_ppp", "the_per_cap_ppp"):
        fields = [f"{stem}_{suffix}" for suffix in ("mean", "lower", "upper")]
        assert subset[fields].notna().all().all(), f"Missing IHME {stem} field"
        assert np.isfinite(subset[fields].to_numpy(dtype=float)).all()
        assert (subset[fields].to_numpy(dtype=float) >= 0).all()
        assert (subset[fields[1]] <= subset[fields[0]]).all()
        assert (subset[fields[0]] <= subset[fields[2]]).all()
    assert (subset.ghes_per_cap_ppp_mean <= subset.the_per_cap_ppp_mean).all()
    ssd = subset.loc[subset.iso3.eq("SSD")]
    assert len(ssd) == 1
    assert (float(ssd.ghes_per_cap_ppp_mean.iloc[0]),
            float(ssd.the_per_cap_ppp_mean.iloc[0])) == (103.0, 274.0)
    assert SOURCE_INFO.is_file()
    return {
        "release_rows": len(csv),
        "release_columns": len(csv.columns),
        "year_2013_country_rows": len(countries),
        "matched_country_rows": len(subset),
        "all_released_csv_dta_cells_agree": True,
        "south_sudan_2013": {
            "government_ppp_mean": 103.0,
            "government_ppp_ui": [79.0, 133.0],
            "total_ppp_mean": 274.0,
            "total_ppp_ui": [235.0, 321.0],
        },
    }


def validate_direct_interval_formula(panel: pd.DataFrame) -> dict:
    """Independently count overlap of each outbreak interval with [m-12,m-1]."""
    crosswalk = pd.read_csv(COUNTRY_CROSSWALK)
    name_by_code = dict(zip(crosswalk.iso3, crosswalk.country_panel))
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
    for row in panel.itertuples(index=False):
        m = pd.Period(row.yearmonth, freq="M").ordinal
        count = sum(max(0, min(end, m - 1) - max(start, m - 12) + 1)
                    for start, end in grouped[row.country])
        assert count == getattr(row, COUNT), (row.country, row.yearmonth)
    return {"checked_country_months": len(panel), "source_outbreak_records": len(records)}


def fit(data: pd.DataFrame, terms: list[str]):
    X = sm.add_constant(data[terms], has_constant="add")
    result = sm.GLM(data.reactive_request, X, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": data.country, "use_correction": False}
    )
    return X, result


def validate_frozen_benchmark(panel: pd.DataFrame) -> dict:
    frozen = pd.read_csv(SOURCE_RESULTS)
    _, reference = fit(panel, [BETWEEN, WITHIN])
    rows = frozen.loc[
        frozen.outcome.eq("reactive_request")
        & frozen.lookback_months.eq(12)
        & frozen.countries.eq(25)
    ]
    assert len(rows) == 2
    ci = reference.conf_int(alpha=0.05)
    for term, component in ((BETWEEN, "between"), (WITHIN, "within")):
        row = rows.loc[rows.component.eq(component)].iloc[0]
        assert np.isclose(reference.params[term], row.coefficient_log_odds, atol=1e-10)
        assert np.isclose(ci.loc[term, 0], row.ci95_low_asymptotic, atol=1e-10)
        assert np.isclose(ci.loc[term, 1], row.ci95_high_asymptotic, atol=1e-10)
        assert np.isclose(reference.aic, row.aic, atol=1e-9)
    return {
        "between_coefficient": float(reference.params[BETWEEN]),
        "within_coefficient": float(reference.params[WITHIN]),
        "aic": float(reference.aic),
        "frozen_p_between": float(rows.loc[rows.component.eq("between"), "p_wclr_c_rademacher"].iloc[0]),
        "frozen_p_within": float(rows.loc[rows.component.eq("within"), "p_wclr_c_rademacher"].iloc[0]),
    }


def validate_panel(panel: pd.DataFrame, source: pd.DataFrame, lookup: pd.DataFrame) -> dict:
    assert len(panel) == len(source) == 1650
    assert list(panel.columns[:len(source.columns)]) == list(source.columns)
    pd.testing.assert_frame_equal(panel[source.columns], source, check_dtype=False)
    assert not panel.duplicated(["country", "yearmonth"]).any()
    assert panel.country.nunique() == 25
    assert panel.reactive_request.isin([0, 1]).all()
    assert int(panel.reactive_request.sum()) == 58
    assert not panel.isna().any().any()
    expected_months = list(pd.period_range("2014-07", "2019-12", freq="M").astype(str))
    assert len(lookup) == lookup.country_panel.nunique() == lookup.iso3.nunique() == 25
    lookup_by_country = lookup.set_index("country_panel")
    rows = []
    for country, part in panel.groupby("country", sort=True):
        assert part.yearmonth.tolist() == expected_months, country
        assert country in lookup_by_country.index
        record = lookup_by_country.loc[country]
        for raw, logged in ((GOV_RAW, GOV_LOG), (TOTAL_RAW, TOTAL_LOG)):
            value = float(record[raw])
            assert value >= 0 and np.isfinite(value)
            assert part[raw].nunique() == part[logged].nunique() == 1, country
            assert np.allclose(part[raw], value, atol=1e-12)
            assert np.allclose(part[logged], np.log1p(value), atol=1e-12)
            assert np.isclose(record[logged], np.log1p(value), atol=1e-12)
        assert part[BETWEEN].nunique() == 1
        assert np.isclose(part[WITHIN].mean(), 0, atol=1e-10)
        assert np.isclose(part[LOG].mean(), part[BETWEEN].iloc[0], atol=1e-10)
        rows.append({
            "country": country,
            "iso3": record.iso3,
            "mean_recorded_log_activity": float(part[BETWEEN].iloc[0]),
            "government_ppp_2013": float(record[GOV_RAW]),
            "total_ppp_2013": float(record[TOTAL_RAW]),
            "reactive_event_months": int(part.reactive_request.sum()),
            "within_sd": float(part[WITHIN].std(ddof=0)),
        })
    assert np.allclose(panel[LOG], np.log1p(panel[COUNT]), atol=1e-10)
    assert np.allclose(panel[LOG], panel[BETWEEN] + panel[WITHIN], atol=1e-10)
    assert (panel[COUNT] >= 0).all()
    assert np.allclose(panel[COUNT], np.rint(panel[COUNT]))
    country_table = pd.DataFrame(rows)
    assert country_table.reactive_event_months.sum() == 58
    assert country_table.loc[country_table.country.eq("South Sudan"), "reactive_event_months"].iloc[0] == 9
    assert country_table.loc[country_table.country.eq("South Sudan"), "government_ppp_2013"].iloc[0] == 103
    assert country_table.loc[country_table.country.eq("South Sudan"), "total_ppp_2013"].iloc[0] == 274
    assert set(country_table.loc[country_table.mean_recorded_log_activity.eq(0), "country"]) == {
        "Burundi", "Republic of the Congo", "Sierra Leone", "Sudan"
    }
    return {
        "countries": rows,
        "zero_between_countries": sorted(country_table.loc[country_table.mean_recorded_log_activity.eq(0), "country"]),
        "correlation_log_government_total": float(panel[[GOV_LOG, TOTAL_LOG]].drop_duplicates().corr().iloc[0, 1]),
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


def fit_sensitivity(panel: pd.DataFrame, term: str, reps: int, bootstrap) -> dict:
    terms = [BETWEEN, WITHIN, term]
    country = panel.groupby("country", sort=True).first()
    correlation = float(country[BETWEEN].corr(country[term]))
    assert abs(correlation) < 0.9, f"Near-collinear {term} and between activity"
    raw = sm.add_constant(panel[terms], has_constant="add").to_numpy(dtype=float)
    standardized = raw.copy()
    std = raw[:, 1:].std(axis=0)
    assert (std > 0).all()
    standardized[:, 1:] = (raw[:, 1:] - raw[:, 1:].mean(axis=0)) / std
    condition = float(np.linalg.cond(standardized))
    assert np.linalg.matrix_rank(raw) == 4 and condition < 30, f"Poorly conditioned {term} design"
    X, adjusted = fit(panel, terms)
    assert adjusted.converged and np.isfinite(adjusted.params).all()
    assert np.isfinite(adjusted.bse).all()
    pred = np.asarray(adjusted.fittedvalues)
    assert np.isfinite(pred).all() and pred.min() > 1e-12 and pred.max() < 1 - 1e-12
    deletions = []
    for omitted in sorted(panel.country.unique()):
        _, deletion = fit(panel.loc[panel.country.ne(omitted)], terms)
        assert deletion.converged and np.isfinite(deletion.params).all(), omitted
        deletions.append({"omitted_country": omitted, **{
            name: float(deletion.params[name]) for name in terms
        }})
    coefficients = {name: coefficient_record(adjusted, name) for name in terms}
    for name in (BETWEEN, WITHIN):
        p, observed_t = bootstrap(
            X.to_numpy(dtype=float), panel.reactive_request.to_numpy(dtype=float),
            panel.country.to_numpy(), adjusted, X.columns.get_loc(name), reps, SEEDS[name]
        )
        coefficients[name].update({
            "p_wclr_c_rademacher": None if np.isnan(p) else float(p),
            "t_cv1_for_wclr_c": observed_t,
            "bootstrap_reps": reps,
            "bootstrap_seed": SEEDS[name],
        })
    return {
        "formula": f"logit P(reactive_request_cm=1) = alpha + beta_B*between12_c + beta_W*within12_cm + gamma*{term}_c",
        "aic": float(adjusted.aic),
        "coefficients": coefficients,
        "diagnostics": {
            "country_level_expenditure_between_correlation": correlation,
            "standardized_design_condition_number": condition,
            "fitted_probability_range": [float(pred.min()), float(pred.max())],
            "one_country_deleted_coefficients": deletions,
            "one_country_deleted_ranges": {
                name: [min(r[name] for r in deletions), max(r[name] for r in deletions)]
                for name in terms
            },
        },
    }


def run(reps: int) -> dict:
    source_check = validate_ihme_releases()
    panel = pd.read_csv(PANEL)
    source_panel = pd.read_csv(SOURCE_PANEL)
    lookup = pd.read_csv(LOOKUP)
    panel_check = validate_panel(panel, source_panel, lookup)
    interval_check = validate_direct_interval_formula(panel)
    benchmark = validate_frozen_benchmark(panel)
    bootstrap = load_frozen_bootstrap()
    government = fit_sensitivity(panel, GOV_LOG, reps, bootstrap)
    total = fit_sensitivity(panel, TOTAL_LOG, reps, bootstrap)
    return {
        "status": "optional_ihme_expenditure_sensitivities_not_frozen_main",
        "specification_protocol": "method_protocol.md",
        "n_countries": 25,
        "n_country_months": len(panel),
        "n_reactive_event_months": int(panel.reactive_request.sum()),
        "ci_method": "95% normal country-cluster sandwich; use_correction=False",
        "bootstrap_method": "Frozen restricted score-linearized WCLR-C, Rademacher, CV1 observed t; outbreak-activity terms only",
        "frozen_benchmark_reproduced": benchmark,
        "models": {"government": government, "total": total},
        "diagnostics": {
            "ihme_release": source_check,
            "panel": panel_check,
            "independent_interval_count_check": interval_check,
        },
        "source_sha256": {
            str(p.relative_to(ROOT)): sha256(p) for p in (
                PANEL, LOOKUP, SOURCE_CSV, SOURCE_DTA, SOURCE_INFO,
                COUNTRY_CROSSWALK, SOURCE_PANEL, SOURCE_RESULTS,
                SOURCE_OUTBREAKS, BOOTSTRAP,
            )
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=99999)
    parser.add_argument("--output", type=Path, default=HERE / "ihme_expenditure_sensitivity_results.json")
    args = parser.parse_args()
    if args.reps < 0:
        parser.error("--reps must be nonnegative")
    result = run(args.reps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"Saved {args.output}")
    for name, model in result["models"].items():
        print(name, {term: record["coefficient_log_odds"] for term, record in model["coefficients"].items()})


if __name__ == "__main__":
    main()
