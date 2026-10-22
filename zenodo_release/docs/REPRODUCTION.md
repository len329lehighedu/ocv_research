# Scientific workflow

Run `python3 -B run_reproduction.py` from the package root after installing the pinned dependencies. The execution order is:

1. Main pipeline: aggregate request labels by country-month, expand recorded outbreak intervals, construct preceding 1/3/6/12-month activity, fit main/robustness models, and create tables and Figures 1–2.
2. Covariate panels and separate income, government expenditure, total expenditure and prior-campaign models.
3. All 25 leave-one-country-out models and the coefficient plot.
4. Direct between-minus-within contrast.
5. Year-indicator and outcome-month-inclusive sensitivity models.
6. The zero-prior-activity request-month roster and retained external-documentation assessments.
7. Supplementary figure generators and export of manuscript-numbered tables/figures.

The bootstrap replication count is 99,999. Main/robustness models use base seed 20261007 with the existing sample/outcome/window/component offsets, recorded in each result row. The main prior-12-month between/within seeds are 20261128 and 20261129. The contrast uses seed 20261007. Temporal alternatives and covariate models retain their documented seed rules.

Confidence intervals are asymptotic country-clustered normal intervals with `use_correction=False`. Bootstrap p-values use the retained restricted WCLR-C Rademacher procedure with CV1 studentization. These are distinct inferential calculations. Added covariate estimates have asymptotic intervals, not bootstrap p-values; LOCO models have no bootstrap p-values.

Figure 2 uses full-25-country component-specific population SDs as common references within each window across country samples. Figure 1B is a country-adjusted transformed binary outcome, not an observed probability. The external-documentation audit is human coded and is not an automatic test of external source truth.

Standalone development/test files are excluded from this publication copy. Checks embedded in scientific scripts remain because they protect input integrity and do not change the fitted specifications. Original source files are never overwritten by the runner.
