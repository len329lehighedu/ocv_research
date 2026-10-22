# Recorded cholera outbreak activity and reactive OCV requests

Data construction and analysis code accompanying the manuscript. This publication copy contains the scientific scripts, retained inputs, derived datasets, and manuscript tables/figures. Local AI-agent instructions, development tests, standalone verification scripts, private review notes and Git history are not included.

## Contents

```text
data/source/            Original retained outbreak, request and delivery CSV files
analysis/               Data construction, statistical models and figure generators
manuscript_outputs/     Table 1, Tables S1–S14, direct contrast and manuscript figures
docs/                   Data dictionary, predictor construction and output map
requirements.txt        Package versions used for reproduction
run_reproduction.py     One-command scientific workflow
```

Within `analysis/`, the modules are `main`, `panel_description`, `request_month_audit`, `leave_one_country_out`, `between_within_contrast`, `time_sensitivities`, `covariates`, and `figures`. Small retained input/code snapshots are dependencies of the frozen analyses, not alternative analysis versions.

## Run

Checked environment: Python 3.14.0 and the package versions in `requirements.txt`. From this folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B run_reproduction.py
```

The runner reconstructs the main panel, fits the models, runs the 99,999-replication bootstraps using the retained seed rules, and regenerates tables/figures. It overwrites generated outputs, not original source files. No network access, Node runtime or AI service is needed. Installation in a newly downloaded environment has not been tested; reproduction was checked in the installed environment.

The history covers July 2013–December 2019; the common estimation period is July 2014–December 2019, allowing a full prior-12-month window. The panel contains 25 countries, 1,650 country-months and 58 reactive request-months. Sources and coding decisions are described in [the data dictionary](docs/DATA_DICTIONARY.md); outputs are mapped to the manuscript in [the output map](docs/MANUSCRIPT_MAP.md).

Core input-integrity checks embedded in the scientific scripts are retained. Removing standalone development tests does not remove the production scripts' checks on keys, windows, convergence or frozen inputs. Numerical methods and seeds are unchanged. The root runner and the LOCO wrapper differ from the working version only by omitting calls to the separate test/verification suite; the audit-report instructions no longer refer to an omitted test file.

The external-documentation audit reproduces a retained human-coded evidence ledger. It does not automatically search or validate external reports, identify every request's target outbreak, or resolve the documented source uncertainties. Published comparator values are transcribed summaries, not a reconstruction of another study's unavailable request-level data.


