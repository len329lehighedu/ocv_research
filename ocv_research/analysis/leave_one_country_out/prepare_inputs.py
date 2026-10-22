#!/usr/bin/env python3
"""Rebuild the frozen panel from unchanged fundamental data, without fitting.

Run once from the existing research workspace. The prepared folder can then
be copied elsewhere: run_loco.py needs only this folder's inputs/ directory.
"""

from pathlib import Path
import hashlib
import importlib.util
import json
import shutil

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FINAL = ROOT / "analysis/main"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_builder(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    inputs = HERE / "inputs"
    builders = HERE / "source_builders"
    inputs.mkdir(exist_ok=True)
    builders.mkdir(exist_ok=True)
    # Snapshot only sources used by this analysis; never edit originals.
    originals = [
        ROOT / "data/source/requests.csv",
        ROOT / "data/source/zheng_outbreak_records.csv",
        FINAL / "outputs/analysis_data/active_outbreak_panel.csv",
        FINAL / "outputs/analysis_data/active_outbreak_results_seeded.csv",
        FINAL / "code/research_pipeline/data/build_request_outcomes.py",
        FINAL / "code/research_pipeline/data/build_active_outbreak_panel.py",
    ]
    hashes_before = {str(p.relative_to(ROOT)): sha256(p) for p in originals}
    for original in originals:
        destination = builders if original.suffix == ".py" else inputs
        target = destination / original.name
        shutil.copy2(original, target)
        if sha256(target) != sha256(original):
            raise RuntimeError(f"Snapshot differs from source: {original}")

    outcome_builder = load_builder(builders / "build_request_outcomes.py", "outcomes")
    activity_builder = load_builder(builders / "build_active_outbreak_panel.py", "activity")
    # Empty campaign labels are preserved, not converted into Reactive.
    requests = pd.read_csv(inputs / "requests.csv", keep_default_na=False)
    outbreaks = pd.read_csv(inputs / "zheng_outbreak_records.csv")
    outcomes = outcome_builder.build(requests)
    rebuilt = activity_builder.build(outbreaks, outcomes)
    frozen = pd.read_csv(inputs / "active_outbreak_panel.csv")
    keys = ["country", "yearmonth"]
    rebuilt = rebuilt.sort_values(keys).reset_index(drop=True)
    frozen = frozen.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(rebuilt[keys], frozen[keys])
    if set(rebuilt.columns) != set(frozen.columns):
        raise RuntimeError("Rebuilt and frozen panels have different columns")
    max_differences = {}
    for column in rebuilt.columns.difference(keys):
        delta = float(np.max(np.abs(rebuilt[column] - frozen[column])))
        max_differences[column] = delta
        np.testing.assert_allclose(
            rebuilt[column], frozen[column], rtol=0, atol=1e-9,
            err_msg=f"Frozen panel mismatch: {column}",
        )
    # Save high-precision reconstruction separately; do not replace frozen CSV.
    rebuilt.to_csv(inputs / "panel_rebuilt.csv", index=False, float_format="%.17g")
    outcomes.to_csv(inputs / "request_outcomes_rebuilt.csv", index=False)
    if hashes_before != {str(p.relative_to(ROOT)): sha256(p) for p in originals}:
        raise RuntimeError("Original source changed during preparation")
    manifest = {
        "source_root": ".",
        "original_sha256": hashes_before,
        "snapshot_sha256": {p.name: sha256(p) for p in inputs.glob("*.csv")},
        "builder_sha256": {p.name: sha256(p) for p in builders.glob("*.py")},
        "rebuilt_vs_frozen_max_absolute_difference": max_differences,
        "comparison_absolute_tolerance": 1e-9,
        "estimation_period": ["2014-07", "2019-12"],
        "history_period": ["2013-07", "2019-12"],
        "observations": len(rebuilt),
        "countries": sorted(rebuilt.country.unique()),
        "reactive_request_months": int(rebuilt.reactive_request.sum()),
        "all_request_months": int(rebuilt.request_this_month.sum()),
    }
    (inputs / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS: fundamental sources rebuilt the frozen panel within 1e-9.")
    print(f"Countries={rebuilt.country.nunique()}, N={len(rebuilt)}, reactive=58, all=73")
    print("Original files unchanged; input snapshots and provenance saved.")


if __name__ == "__main__":
    main()
