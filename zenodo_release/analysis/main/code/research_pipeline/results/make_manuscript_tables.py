#!/usr/bin/env python3
"""Create paste-ready manuscript tables from the locked seeded model outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def ci(row: pd.Series) -> str:
    return f"[{row.ci95_low_asymptotic:.3f}, {row.ci95_high_asymptotic:.3f}]"


def pvalue(value: float, *, precision: int = 3) -> str:
    return "<0.001" if value < 0.001 else f"{value:.{precision}f}"


def make_tables(main: pd.DataFrame, alternative: pd.DataFrame, output_dir: Path) -> None:
    expected = {
        (outcome, countries, lag, component)
        for outcome in ("reactive_request", "request_this_month")
        for countries in (25, 23, 22)
        for lag in (1, 3, 6, 12)
        for component in ("between", "within")
    }
    keys = list(zip(main.outcome, main.countries, main.lookback_months, main.component))
    if len(main) != 48 or set(keys) != expected:
        raise ValueError("Main model output is not the expected 48 unique estimates")
    if len(alternative) != 12:
        raise ValueError("Alternative predictor output needs 12 coefficient rows")
    main = main.set_index(["outcome", "countries", "lookback_months", "component"])
    alternative = alternative.set_index(["outcome", "countries", "component"])
    outcome_names = {"reactive_request": "Reactive requests", "request_this_month": "All requests"}
    main_rows = []
    robustness_rows = []
    s4_rows = []
    s5_rows = []
    for outcome, label in outcome_names.items():
        for countries in (25, 23, 22):
            for lag in (1, 3, 6, 12):
                between = main.loc[(outcome, countries, lag, "between")]
                within = main.loc[(outcome, countries, lag, "within")]
                s4_rows.append({
                    "Outcome": label,
                    "Countries": countries,
                    "Lag (months)": lag,
                    "Between asymptotic p": pvalue(between.p_asymptotic),
                    "Between bootstrap p": pvalue(between.p_wclr_c_rademacher),
                    "Within asymptotic p": pvalue(within.p_asymptotic),
                    "Within bootstrap p": pvalue(within.p_wclr_c_rademacher),
                })
                if lag == 12:
                    robustness_rows.append({
                        "Outcome": label,
                        "Countries": countries,
                        "Between coefficient": f"{between.coefficient_log_odds:.3f}",
                        "Between asymptotic 95% CI": ci(between),
                        "Between bootstrap p": pvalue(between.p_wclr_c_rademacher),
                        "Within coefficient": f"{within.coefficient_log_odds:.3f}",
                        "Within asymptotic 95% CI": ci(within),
                        "Within bootstrap p": pvalue(within.p_wclr_c_rademacher),
                    })
                    if outcome == "reactive_request" and countries == 25:
                        for component, row in (("between", between), ("within", within)):
                            main_rows.append({
                                "Outcome": label,
                                "Lag (months)": lag,
                                "Component": component,
                                "Coefficient": f"{row.coefficient_log_odds:.3f}",
                                "Asymptotic 95% CI": ci(row),
                                "Bootstrap p": f"{row.p_wclr_c_rademacher:.5f}",
                            })
            alt_between = alternative.loc[(outcome, countries, "between")]
            alt_within = alternative.loc[(outcome, countries, "within")]
            s5_rows.append({
                "Outcome": label,
                "Countries": countries,
                "Country-months": int(alt_between.country_months),
                "Event-months": int(alt_between.event_months),
                "Between coefficient [asymptotic 95% CI]": f"{alt_between.coefficient_log_odds:.3f} {ci(alt_between)}",
                "Between bootstrap p": f"{alt_between.p_wclr_c_rademacher:.5f}",
                "Within coefficient [asymptotic 95% CI]": f"{alt_within.coefficient_log_odds:.3f} {ci(alt_within)}",
                "Within bootstrap p": f"{alt_within.p_wclr_c_rademacher:.5f}",
            })
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("table_3_2_main_model.csv", main_rows),
        ("table_3_3_12m_robustness.csv", robustness_rows),
        ("table_s4_pvalues.csv", s4_rows),
        ("table_s5_any_active_months.csv", s5_rows),
    ):
        pd.DataFrame(rows).to_csv(output_dir / name, index=False)
        print(f"Saved {name}: {len(rows)} rows")


def main_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--alternative", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    make_tables(pd.read_csv(args.results), pd.read_csv(args.alternative), args.output_dir)


if __name__ == "__main__":
    main_cli()
