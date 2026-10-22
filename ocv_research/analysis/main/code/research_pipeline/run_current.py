#!/usr/bin/env python3
"""Rebuild the data and figures used by the current outbreak-activity manuscript.

Run from ``analysis/main/code`` with
``python3 -B -m research_pipeline.run_current``. Outputs default to the
sibling ``outputs/`` directory; use ``--output-root`` for a
disposable check.
This frozen release maps the source's TZA_zanzibar record to Tanzania.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT.parent
SOURCES = PACKAGE.parents[1] / "data/source"


def invoke(module: str, *args: object, capture: Path | None = None) -> None:
    command = [sys.executable, "-B", "-m", module, *(str(arg) for arg in args)]
    result = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    if capture is not None:
        capture.parent.mkdir(parents=True, exist_ok=True)
        capture.write_text(result.stdout, encoding="utf-8")
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=PACKAGE / "outputs")
    parser.add_argument("--reps", type=int, default=99999)
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()
    if args.reps < 1:
        parser.error("--reps must be positive")
    output_root = args.output_root.resolve()
    analysis_dir = output_root / "analysis_data"
    table_dir = output_root / "tables"
    figure_dir = output_root / "figures"
    figure_data_dir = output_root / "figure_data"
    outcome = analysis_dir / "request_outcomes.csv"
    panel = analysis_dir / "active_outbreak_panel.csv"

    invoke(
        "research_pipeline.data.build_request_outcomes",
        "--requests", SOURCES / "requests.csv", "--output", outcome,
    )
    invoke(
        "research_pipeline.data.build_active_outbreak_panel",
        "--outbreaks", SOURCES / "zheng_outbreak_records.csv",
        "--outcomes", outcome, "--output", panel,
    )
    invoke(
        "research_pipeline.results.reproduce_descriptive_results",
        "--outbreaks", SOURCES / "zheng_outbreak_records.csv",
        "--requests", SOURCES / "requests.csv",
        "--deliveries", SOURCES / "deliveries.csv",
        capture=analysis_dir / "descriptive_results.txt",
    )
    invoke(
        "research_pipeline.results.make_descriptive_manuscript_tables",
        "--outbreaks", SOURCES / "zheng_outbreak_records.csv",
        "--requests", SOURCES / "requests.csv",
        "--deliveries", SOURCES / "deliveries.csv",
        "--panel", panel, "--output-dir", table_dir,
    )
    invoke(
        "research_pipeline.results.reproduce_request_reconciliation",
        "--requests", SOURCES / "requests.csv", "--output-dir", table_dir,
    )
    invoke(
        "research_pipeline.results.revise_active_outbreak_results",
        "--panel", panel, "--output-dir", analysis_dir,
        "--reps", args.reps, "--seed", args.seed,
    )
    invoke(
        "research_pipeline.supplement.revise_any_active_months_sensitivity",
        "--outbreaks", SOURCES / "zheng_outbreak_records.csv",
        "--panel", panel,
        "--output", analysis_dir / "any_active_months_sensitivity_seeded.csv",
        "--reps", args.reps, "--seed", args.seed,
    )
    invoke(
        "research_pipeline.results.make_manuscript_tables",
        "--results", analysis_dir / "active_outbreak_results_seeded.csv",
        "--alternative", analysis_dir / "any_active_months_sensitivity_seeded.csv",
        "--output-dir", table_dir,
    )
    invoke(
        "research_pipeline.figures.create_active_outbreak_panels",
        "--panel", panel, "--figure-dir", figure_dir,
        "--data-dir", figure_data_dir,
    )
    invoke(
        "research_pipeline.figures.plot_active_outbreak_robustness_sample_layout",
        "--results", analysis_dir / "active_outbreak_results_seeded.csv",
        "--output", figure_dir / "robustness_coefficient_plot_sample_layout.png",
    )


if __name__ == "__main__":
    main()
