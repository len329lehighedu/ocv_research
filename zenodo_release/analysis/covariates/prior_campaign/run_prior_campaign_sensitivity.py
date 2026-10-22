#!/usr/bin/env python3
"""Optional, pre-protocolled baseline campaign-history sensitivity.

Read method_protocol.md. Source, country, panel, interval and frozen-model
validations are mandatory gates before the adjusted fit is reported.
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
PANEL = HERE / "active_outbreak_panel_prior_ocv_campaign.csv"
LOOKUP = HERE / "country_prior_ocv_campaign_pre2014jul.csv"
LEDGER = HERE / "source_ledger.json"
CROSSWALK = ROOT / "analysis/covariates/income/country_income_fy2015.csv"
SOURCE_PANEL = FROZEN / "outputs/analysis_data/active_outbreak_panel.csv"
SOURCE_RESULTS = FROZEN / "outputs/analysis_data/active_outbreak_results_seeded.csv"
SOURCE_OUTBREAKS = ROOT / "data/source/zheng_outbreak_records.csv"
BOOTSTRAP = FROZEN / "code/research_pipeline/results/wild_cluster_bootstrap.py"
BETWEEN = "log1p_active_outbreak_months_12m_between"
WITHIN = "log1p_active_outbreak_months_12m_within"
LOG = "log1p_active_outbreak_months_12m"
COUNT = "active_outbreak_months_prior_12m"
PRIOR = "prior_ocv_campaign_pre2014jul"
TERMS = [BETWEEN, WITHIN, PRIOR]
POSITIVE = {"DR Congo", "Guinea", "Mozambique", "South Sudan", "Sudan", "Tanzania", "Uganda"}
SEEDS = {BETWEEN: 20261128, WITHIN: 20261129}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_bootstrap():
    spec = importlib.util.spec_from_file_location("frozen_wclr_c", BOOTSTRAP)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen WCLR-C implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.wclr_c_pvalue


def validate_ledger(lookup: pd.DataFrame) -> dict:
    ledger = json.loads(LEDGER.read_text())
    crosswalk = pd.read_csv(CROSSWALK)
    assert ledger["cutoff_exclusive"] == "2014-07-01"
    assert len(crosswalk) == crosswalk.country_panel.nunique() == crosswalk.iso3.nunique() == 25
    assert len(lookup) == lookup.country_panel.nunique() == lookup.iso3.nunique() == 25
    assert lookup.country_panel.tolist() == crosswalk.country_panel.tolist()
    assert lookup.iso3.tolist() == crosswalk.iso3.tolist()
    assert lookup[PRIOR].isin([0, 1]).all()
    assert set(lookup.loc[lookup[PRIOR].eq(1), "country_panel"]) == POSITIVE
    assert int(lookup[PRIOR].sum()) == 7
    source_positives = ledger["documented_positive_countries"]
    assert len(source_positives) == 7
    assert {row["country_panel"] for row in source_positives} == POSITIVE
    positive_by_country = {row["country_panel"]: row for row in source_positives}
    for row in lookup.itertuples(index=False):
        assert row.cutoff_exclusive == "2014-07-01"
        assert row.historical_inventory_urls == " | ".join(ledger["inventory_sources"])
        if getattr(row, PRIOR) == 1:
            record = positive_by_country[row.country_panel]
            assert row.iso3 == record["iso3"]
            assert int(row.first_documented_campaign_year) == record["first_campaign_year"]
            assert record["first_campaign_year"] <= 2014
            if record["first_campaign_year"] == 2014:
                assert pd.Timestamp(record["first_documented_administration_date"]) < pd.Timestamp(ledger["cutoff_exclusive"])
            assert row.qualifying_site == record["site"]
            assert row.implementation_evidence == record["basis"]
            assert row.specific_source_url == record["specific_source"]
            assert "Implemented" in row.source_status
            assert row.specific_source_url.startswith("https://")
        else:
            assert pd.isna(row.first_documented_campaign_year)
            assert pd.isna(row.qualifying_site)
            assert pd.isna(row.implementation_evidence)
            assert pd.isna(row.specific_source_url)
            assert "absence not verified" in row.source_status
    assert lookup.loc[lookup.country_panel.eq("Ethiopia"), PRIOR].iloc[0] == 0
    assert lookup.loc[lookup.country_panel.eq("Tanzania"), "qualifying_site"].iloc[0] == "Zanzibar"
    assert lookup.loc[lookup.country_panel.eq("South Sudan"), "first_documented_campaign_year"].iloc[0] == 2012
    assert ledger["boundary_case"]["june_2014_request_is_not_campaign"] is True
    assert positive_by_country["DR Congo"]["first_documented_administration_date"] == "2013-11-25"
    assert ledger["boundary_case"]["first_documented_administration_date"] == "2014-07-24"
    return {"positive_countries": sorted(POSITIVE), "positive_count": 7,
            "not_documented_count": 18, "ethiopia_request_not_imputed_as_campaign": True,
            "drc_2013_actual_administration_documented": True}


def validate_direct_interval_formula(panel: pd.DataFrame, lookup: pd.DataFrame) -> dict:
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
    for row in panel.itertuples(index=False):
        month = pd.Period(row.yearmonth, freq="M").ordinal
        direct_count = sum(max(0, min(end, month - 1) - max(start, month - 12) + 1)
                           for start, end in grouped[row.country])
        assert direct_count == getattr(row, COUNT), (row.country, row.yearmonth)
    return {"checked_country_months": len(panel), "source_outbreak_records": len(records)}


def fit(data: pd.DataFrame, terms: list[str]):
    X = sm.add_constant(data[terms], has_constant="add")
    result = sm.GLM(data.reactive_request, X, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": data.country, "use_correction": False}
    )
    return X, result


def validate_panel(panel: pd.DataFrame, source: pd.DataFrame, lookup: pd.DataFrame) -> dict:
    assert len(panel) == len(source) == 1650
    assert list(panel.columns[:len(source.columns)]) == list(source.columns)
    pd.testing.assert_frame_equal(panel[source.columns], source, check_dtype=False)
    assert list(panel.columns[len(source.columns):]) == [PRIOR]
    assert not panel.duplicated(["country", "yearmonth"]).any()
    assert panel.country.nunique() == 25
    assert panel.reactive_request.isin([0, 1]).all()
    assert panel[PRIOR].isin([0, 1]).all()
    assert not panel.isna().any().any()
    assert int(panel.reactive_request.sum()) == 58
    expected_months = list(pd.period_range("2014-07", "2019-12", freq="M").astype(str))
    lookup_by_country = lookup.set_index("country_panel")
    countries = []
    for country, part in panel.groupby("country", sort=True):
        assert part.yearmonth.tolist() == expected_months, country
        assert country in lookup_by_country.index
        assert part[PRIOR].nunique() == 1
        assert int(part[PRIOR].iloc[0]) == int(lookup_by_country.loc[country, PRIOR])
        assert part[BETWEEN].nunique() == 1
        assert np.isclose(part[WITHIN].mean(), 0, atol=1e-10)
        assert np.isclose(part[LOG].mean(), part[BETWEEN].iloc[0], atol=1e-10)
        countries.append({
            "country": country, "iso3": lookup_by_country.loc[country, "iso3"],
            PRIOR: int(part[PRIOR].iloc[0]),
            "mean_recorded_log_activity": float(part[BETWEEN].iloc[0]),
            "reactive_event_months": int(part.reactive_request.sum()),
            "within_sd": float(part[WITHIN].std(ddof=0)),
        })
    assert np.allclose(panel[LOG], np.log1p(panel[COUNT]), atol=1e-10)
    assert np.allclose(panel[LOG], panel[BETWEEN] + panel[WITHIN], atol=1e-10)
    assert (panel[COUNT] >= 0).all()
    assert np.allclose(panel[COUNT], np.rint(panel[COUNT]))
    country_table = pd.DataFrame(countries)
    assert country_table.groupby(PRIOR).size().to_dict() == {0: 18, 1: 7}
    assert country_table.groupby(PRIOR).reactive_event_months.sum().to_dict() == {0: 31, 1: 27}
    assert country_table.loc[country_table.country.eq("South Sudan"), "reactive_event_months"].iloc[0] == 9
    assert set(country_table.loc[country_table.mean_recorded_log_activity.eq(0), "country"]) == {
        "Burundi", "Republic of the Congo", "Sierra Leone", "Sudan"
    }
    correlation = float(country_table[PRIOR].corr(country_table.mean_recorded_log_activity))
    assert abs(correlation) < 0.9
    raw = sm.add_constant(panel[TERMS], has_constant="add").to_numpy(dtype=float)
    standardized = raw.copy()
    deviations = raw[:, 1:].std(axis=0)
    assert (deviations > 0).all()
    standardized[:, 1:] = (raw[:, 1:] - raw[:, 1:].mean(axis=0)) / deviations
    condition = float(np.linalg.cond(standardized))
    assert np.linalg.matrix_rank(raw) == 4 and condition < 30
    return {
        "countries": countries,
        "documented_group_sizes": {"zero": 18, "one": 7},
        "reactive_event_months_by_documented_group": {"zero": 31, "one": 27},
        "country_level_prior_between_correlation": correlation,
        "standardized_design_condition_number": condition,
    }


def validate_frozen_benchmark(panel: pd.DataFrame) -> dict:
    frozen = pd.read_csv(SOURCE_RESULTS)
    _, base = fit(panel, [BETWEEN, WITHIN])
    rows = frozen.loc[frozen.outcome.eq("reactive_request")
                      & frozen.lookback_months.eq(12) & frozen.countries.eq(25)]
    assert len(rows) == 2
    ci = base.conf_int(alpha=0.05)
    for term, component in ((BETWEEN, "between"), (WITHIN, "within")):
        row = rows.loc[rows.component.eq(component)].iloc[0]
        assert np.isclose(base.params[term], row.coefficient_log_odds, atol=1e-10)
        assert np.isclose(ci.loc[term, 0], row.ci95_low_asymptotic, atol=1e-10)
        assert np.isclose(ci.loc[term, 1], row.ci95_high_asymptotic, atol=1e-10)
        assert np.isclose(base.aic, row.aic, atol=1e-9)
    return {
        "between_coefficient": float(base.params[BETWEEN]),
        "within_coefficient": float(base.params[WITHIN]),
        "aic": float(base.aic),
        "frozen_p_between": float(rows.loc[rows.component.eq("between"), "p_wclr_c_rademacher"].iloc[0]),
        "frozen_p_within": float(rows.loc[rows.component.eq("within"), "p_wclr_c_rademacher"].iloc[0]),
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
    lookup = pd.read_csv(LOOKUP)
    ledger_check = validate_ledger(lookup)
    panel = pd.read_csv(PANEL)
    source = pd.read_csv(SOURCE_PANEL)
    panel_check = validate_panel(panel, source, lookup)
    interval_check = validate_direct_interval_formula(panel, lookup)
    benchmark = validate_frozen_benchmark(panel)
    X, adjusted = fit(panel, TERMS)
    assert adjusted.converged and np.isfinite(adjusted.params).all()
    assert np.isfinite(adjusted.bse).all()
    prediction = np.asarray(adjusted.fittedvalues)
    assert np.isfinite(prediction).all()
    assert prediction.min() > 1e-12 and prediction.max() < 1 - 1e-12
    deletions = []
    for omitted in sorted(panel.country.unique()):
        _, deletion = fit(panel.loc[panel.country.ne(omitted)], TERMS)
        assert deletion.converged and np.isfinite(deletion.params).all(), omitted
        deletions.append({"omitted_country": omitted, **{
            term: float(deletion.params[term]) for term in TERMS
        }})
    coefficients = {term: coefficient_record(adjusted, term) for term in TERMS}
    bootstrap = load_frozen_bootstrap()
    for term in (BETWEEN, WITHIN):
        p, observed_t = bootstrap(
            X.to_numpy(dtype=float), panel.reactive_request.to_numpy(dtype=float),
            panel.country.to_numpy(), adjusted, X.columns.get_loc(term), reps, SEEDS[term],
        )
        coefficients[term].update({
            "p_wclr_c_rademacher": None if np.isnan(p) else float(p),
            "t_cv1_for_wclr_c": observed_t,
            "bootstrap_reps": reps,
            "bootstrap_seed": SEEDS[term],
        })
    return {
        "status": "optional_documented_prior_ocv_campaign_sensitivity_not_frozen_main",
        "specification_protocol": "method_protocol.md",
        "formula": "logit P(reactive_request_cm=1) = alpha + beta_B*between12_c + beta_W*within12_cm + gamma*documented_prior_campaign_pre2014jul_c",
        "n_countries": 25,
        "n_country_months": len(panel),
        "n_reactive_event_months": int(panel.reactive_request.sum()),
        "ci_method": "95% normal country-cluster sandwich; use_correction=False",
        "bootstrap_method": "Frozen restricted score-linearized WCLR-C, Rademacher, CV1 observed t; outbreak-activity terms only",
        "aic": float(adjusted.aic),
        "coefficients": coefficients,
        "frozen_benchmark_reproduced": benchmark,
        "diagnostics": {
            "ledger": ledger_check,
            "panel": panel_check,
            "independent_interval_count_check": interval_check,
            "fitted_probability_range": [float(prediction.min()), float(prediction.max())],
            "one_country_deleted_coefficients": deletions,
            "one_country_deleted_ranges": {
                term: [min(row[term] for row in deletions), max(row[term] for row in deletions)]
                for term in TERMS
            },
        },
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in (
            PANEL, LOOKUP, LEDGER, CROSSWALK, SOURCE_PANEL, SOURCE_RESULTS,
            SOURCE_OUTBREAKS, BOOTSTRAP,
            Path(__file__), ROOT / "analysis/covariates/build_panels.py", HERE / "method_protocol.md",
        )},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=99999)
    parser.add_argument("--output", type=Path, default=HERE / "prior_campaign_sensitivity_results.json")
    args = parser.parse_args()
    if args.reps < 0:
        parser.error("--reps must be nonnegative")
    result = run(args.reps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"Saved {args.output}")
    print({term: record["coefficient_log_odds"] for term, record in result["coefficients"].items()})


if __name__ == "__main__":
    main()
