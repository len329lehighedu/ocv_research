#!/usr/bin/env python3
"""Run the manuscript analyses without the separate development/test suite."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def invoke(*arguments, cwd=ROOT):
    print('\n>>> ' + ' '.join(str(x) for x in arguments), flush=True)
    subprocess.run([sys.executable, '-B', *map(str, arguments)], cwd=cwd, check=True)


def main():
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'ocv-zenodo-mpl'))
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    invoke('-m', 'research_pipeline.run_current', '--reps', 99999, '--seed', 20261007,
           cwd=ROOT / 'analysis/main/code')
    for script in (
        'analysis/covariates/build_panels.py',
        'analysis/covariates/income/run_income_sensitivity.py',
        'analysis/covariates/expenditure/ihme_2013/run_ihme_sensitivities.py',
        'analysis/covariates/prior_campaign/run_prior_campaign_sensitivity.py',
        'analysis/leave_one_country_out/prepare_inputs.py',
        'analysis/leave_one_country_out/run_all.py',
        'analysis/between_within_contrast/run_contrast.py',
        'analysis/time_sensitivities/run_sensitivities.py',
        'analysis/request_month_audit/build_roster.py',
        'analysis/request_month_audit/compile_audit.py',
        'analysis/figures/plot_delivery_rounds.py',
        'analysis/figures/plot_figure2_reconciliation.py',
        'analysis/figures/plot_covariate_sensitivity.py',
        'analysis/export_manuscript_outputs.py',
    ):
        invoke(script)
    print('\nCompleted manuscript data construction, analyses, tables and figures.')


if __name__ == '__main__':
    main()
