"""Collect manuscript-numbered tables/figures without changing any fitted model."""
from pathlib import Path
import json
import shutil
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.panel_description.audit_recorded_opportunity import audit


def main():
    dest = ROOT / "manuscript_outputs"
    tables, figures = dest / "tables", dest / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    saved = ROOT / "analysis/main/outputs"
    results = pd.read_csv(saved / "analysis_data/active_outbreak_results_seeded.csv")
    primary = results.loc[(results.outcome == "reactive_request") &
                          (results.countries == 25) & (results.lookback_months == 12)].copy()
    assert len(primary) == 2
    for new, old in [("odds_ratio", "coefficient_log_odds"),
                     ("or_ci95_low", "ci95_low_asymptotic"), ("or_ci95_high", "ci95_high_asymptotic")]:
        primary[new] = np.exp(primary[old])
    primary.to_csv(tables / "table_1_main_model.csv", index=False, float_format="%.17g")
    countries, _, _ = audit()
    country_table = countries[["country", "reactive_request_months", "active_record_months_panel"]].copy()
    country_table.insert(1, "country_months", 66)
    assert country_table.active_record_months_panel.sum() == 1883
    assert country_table.reactive_request_months.sum() == 58
    country_table.to_csv(tables / "table_s1_country_composition.csv", index=False)
    # Published comparator values are transcribed inputs, not estimates of this study.
    markdown_tables = {
        "section_3_1_outbreak_comparison.md": ("s2", "Outbreak-source descriptive comparison"),
        "section_3_1_request_comparison.md": ("s3", "Request and delivery descriptive comparison"),
        "figure_1_delivery_timing.md": ("s4", "Decision-to-delivery timing"),
        "figure_2_dose_comparison.md": ("s5", "Dose-total arithmetic comparison"),
    }
    for filename, (number, title) in markdown_tables.items():
        text = (saved / "tables" / filename).read_text()
        text = f"# Table {number.upper()}. {title}\n" + text[text.index("\n"):]
        (tables / f"table_{number}_{filename}").write_text(text)
    csv_tables = {
        "supplement_s1_request_classification.csv": "table_s6_request_classification.csv",
        "supplement_s2_dose_reconciliation.csv": "table_s7_dose_reconciliation.csv",
        "supplement_s3_nonstandard_requests.csv": "table_s8_nonstandard_requests.csv",
        "table_s4_pvalues.csv": "table_s10_robustness.csv",
        "table_s5_any_active_months.csv": "table_s11_any_active_months.csv",
    }
    for source, target in csv_tables.items():
        shutil.copy2(saved / "tables" / source, tables / target)
    audit_dir = ROOT / "analysis/request_month_audit/outputs"
    shutil.copy2(audit_dir / "supplementary_audit_22.csv", tables / "table_s9_external_documentation_audit.csv")
    loco = pd.read_csv(ROOT / "analysis/leave_one_country_out/outputs/loco_coefficients.csv")
    wide = []
    for country, group in loco.groupby("omitted_country", sort=False):
        row = {"country_omitted": country, "reactive_request_months_retained": int(group.event_months.iloc[0])}
        for item in group.itertuples(index=False):
            for field in ("coefficient_log_odds", "ci95_low_asymptotic", "ci95_high_asymptotic"):
                row[f"{item.component}_{field}"] = getattr(item, field)
        wide.append(row)
    pd.DataFrame(wide).to_csv(tables / "table_s12_leave_one_country_out.csv", index=False, float_format="%.17g")
    from analysis.figures.plot_covariate_sensitivity import load_estimates
    covariates, _, _ = load_estimates()
    income = json.loads((ROOT / "analysis/covariates/income/income_sensitivity_results.json").read_text())
    exp = json.loads((ROOT / "analysis/covariates/expenditure/ihme_2013/ihme_expenditure_sensitivity_results.json").read_text())
    prior = json.loads((ROOT / "analysis/covariates/prior_campaign/prior_campaign_sensitivity_results.json").read_text())
    added = {
        "main": None,
        "income": next(v for k, v in income["coefficients"].items() if not k.startswith("log1p_active_outbreak")),
        "government": next(v for k, v in exp["models"]["government"]["coefficients"].items() if not k.startswith("log1p_active_outbreak")),
        "total": next(v for k, v in exp["models"]["total"]["coefficients"].items() if not k.startswith("log1p_active_outbreak")),
        "prior": next(v for k, v in prior["coefficients"].items() if not k.startswith("log1p_active_outbreak")),
    }
    sensitivity = []
    for model in dict.fromkeys(r["model"] for r in covariates):
        group = [r for r in covariates if r["model"] == model]
        row = {"model": model, "label": group[0]["label"]}
        for item in group:
            for field in ("coefficient_log_odds", "ci95_low_asymptotic", "ci95_high_asymptotic", "p_wclr_c_rademacher"):
                row[f"{item['component']}_{field}"] = item[field]
        cov = added[model]
        row.update(added_covariate_coefficient=None if cov is None else cov["coefficient_log_odds"],
                   added_covariate_ci95_low=None if cov is None else cov["ci95_log_odds_cluster_asymptotic"][0],
                   added_covariate_ci95_high=None if cov is None else cov["ci95_log_odds_cluster_asymptotic"][1])
        sensitivity.append(row)
    pd.DataFrame(sensitivity).to_csv(tables / "table_s13_covariate_sensitivities.csv", index=False, float_format="%.17g")
    shutil.copy2(ROOT / "analysis/time_sensitivities/outputs/comparison_results.csv",
                 tables / "table_s14_temporal_sensitivities.csv")
    shutil.copy2(ROOT / "analysis/between_within_contrast/outputs/contrast_results.csv",
                 tables / "between_within_contrast.csv")
    for source, target in {
        "analysis/main/outputs/figures/panel_a.png": "figure_1a_between.png",
        "analysis/main/outputs/figures/panel_b.png": "figure_1b_within.png",
        "analysis/main/outputs/figures/robustness_coefficient_plot_sample_layout.png": "figure_2_robustness.png",
        "analysis/figures/delivery_rounds/delivery_round_positions.png": "figure_s1_delivery_rounds.png",
        "analysis/figures/reconciliation_outputs/figure2_reconciliation_revised.png": "figure_s2_dose_reconciliation.png",
        "analysis/leave_one_country_out/outputs/loco_coefficients.png": "figure_s3_leave_one_country_out.png",
        "analysis/figures/covariate_sensitivity/covariate_sensitivity_coefficient_plot.png": "figure_s4_covariates.png",
    }.items():
        shutil.copy2(ROOT / source, figures / target)
    print("Exported Table 1, Tables S1–S14, contrast data, and seven figure files.")


if __name__ == "__main__":
    main()
