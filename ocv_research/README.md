# OCV requests and recorded outbreak activity

Code, retained source data, derived datasets, tables and figures accompanying the OCV manuscript. Release 1.1.5, 2 November 2026.

## Contents

- `data/source/`: retained outbreak, request and delivery CSV files.
- `analysis/`: data construction, models, plotting, coding ledgers and analytical outputs.
- `manuscript_outputs/`: current numbered tables and figures. Captions are supplied in the manuscript, not in this package.
- `docs/reproduction.md`: execution instructions, variable definitions, sources and interpretation limits.
- `requirements.txt`: package versions used for reproduction.
- `run_reproduction.py`: complete scientific workflow.

## Run

From this directory, using Python 3.14.0:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B run_reproduction.py
```

The workflow reconstructs the panel, fits models, runs the seeded 99,999-replication bootstraps, and exports tables and figures. It overwrites generated outputs, not original source files. No network access or AI service is needed to run the analysis; dependency installation may require internet access. Arial must be installed for the supplied figure typography; the font is not redistributed.

Internal review notes, correction/change logs, search-execution logs, standalone development tests and generated diagnostic reports are excluded. Source/coding ledgers, required input-integrity manifests and model-result JSON files remain because they support the analysis. Running scripts can generate new diagnostic reports locally; these are not bundled in the upload.

See [reproduction instructions and data definitions](docs/reproduction.md) before interpreting or modifying the analysis. The external-documentation audit reproduces retained human assessments; it does not rerun a literature search or independently validate source passages. Third-party source data retain their original ownership and terms.
