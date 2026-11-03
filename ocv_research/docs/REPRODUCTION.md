# Reproducing the OCV analysis

## Execution

Run `python3 -B run_reproduction.py` from the package root after installing `requirements.txt`. The checked environment is Python 3.14.0, NumPy 2.4.1, pandas 2.3.3, SciPy 1.17.0, statsmodels 0.15.0, Matplotlib 3.10.8 and Pillow 12.1.0. Installation into a fresh environment has not been tested. Arial is required for exact figure typography and is not bundled.

The runner executes:

1. `analysis/main/code/research_pipeline/run_current.py`: main panel, models, descriptive tables and Figures 1–2.
2. `analysis/covariates/build_panels.py` and the separate income, expenditure and prior-campaign model scripts.
3. `analysis/leave_one_country_out/prepare_inputs.py` and `run_all.py`: 25 country-deletion fits and their figure.
4. `analysis/between_within_contrast/run_contrast.py`: direct between-minus-within contrast.
5. `analysis/time_sensitivities/run_sensitivities.py`: year indicators and outcome-month-inclusive predictor.
6. `analysis/request_month_audit/build_roster.py` and `compile_audit.py`: zero-prior-activity roster and retained human-coded evidence.
7. `analysis/delivery_provenance.py`, supplementary plotting scripts and `analysis/export_manuscript_outputs.py`.

Source files are not overwritten. Generated outputs, including diagnostic reports, are written beside the analyses. Internal review reports and execution logs are not distributed. Required input manifests remain to detect altered inputs; they are not substitutes for source provenance.

## Source data and panel

History covers July 2013–December 2019. Estimation covers July 2014–December 2019: 25 countries × 66 months = 1,650 rows, including 58 reactive request-months. The panel is `analysis/main/outputs/analysis_data/active_outbreak_panel.csv`.

- `data/source/zheng_outbreak_records.csv`: 999 intervals from [Zheng et al. (2022)](https://doi.org/10.1016/j.ijid.2022.05.039). Each record contributes separately in every month from start through end month, inclusive; overlapping subnational records are not collapsed. Zanzibar maps to Tanzania. Final case totals and the outbreak threshold are not used in the predictor. The threshold's unit is cases per 100,000 people per week, not a raw case count.
- `data/source/requests.csv`: retained [GTFCC dashboard](https://apps.epicentre-msf.org/public/app/gtfcc) records plus the separately sourced January 2014 South Sudan record below. `reactive_request` equals one for at least one explicitly reactive record in that country-month. `request_this_month` covers any saved campaign label. Multiple records in a month produce one event-month; an ID prefix does not determine campaign type.
- `data/source/deliveries.csv`: dashboard delivery rounds. The first original `doses_delivered` column is used; its duplicate header is retained. Deliveries do not determine regression outcomes.

`active_outbreaks_this_month` counts active records. `active_outbreak_months_prior_{1,3,6,12}m` sums counts over preceding months, excluding the outcome month. `log1p_active_outbreak_months_{L}m = ln(1 + count)`. Its `_between` component is the country's mean logged value across the 66 estimation months; `_within` is the monthly logged value minus that mean. This is the mean of logs, not the log of a raw mean. These measures are not cases, severity, distinct request opportunities or information necessarily available at submission. Zero does not establish absence of cholera.

### South Sudan and delivery-source limitations

The January 2014 South Sudan record has no dashboard ID and precedes estimation. [Abubakar et al.](https://doi.org/10.1371/journal.pmed.1001901), [S1 Figure](https://doi.org/10.1371/journal.pmed.1001901.s001), dates the request to 24 January and initial approval to 30 January (six elapsed days): 188,000 doses initially approved plus 64,000 on 5 February. The retained 252,000 approved total combines these. Requested quantity 326,000 is imputed as twice 163,000, not an observed request quantity.

Delivery summaries use recorded numeric intervals, not reconstructed dates. There are 100 numeric delivery-round records and 92 numeric decision-to-delivery intervals. First-round summaries use round 1; last-round summaries use the largest round with a numeric interval per ID. Each has 61 IDs. Missing intervals are excluded, not zeroed. Negative values remain unresolved: Tanzania `2015-I05-D01`, round 1, −7 days; Zimbabwe `2018-I11-D01`, rounds 1 and 2, −1 day each.

Cameroon `2019-I03-D02` has 691,200 delivered doses but no exact matching request ID. Its interval is `unknown`; `-355 DAYS SINCE REQUEST ACCEPTED` is not treated as a numeric interval. No date or linkage is inferred. The ratio 100/61 compares different count universes, not mean rounds per approved request. `analysis/delivery_provenance.py` exports exception data.

## Models, inference and figures

Models are pooled binomial logistic regressions with between/within terms, not country-fixed-effects logistic regressions. Confidence intervals are normal asymptotic country-clustered intervals with `use_correction=False`. Bootstrap p-values use restricted score-linearized WCLR-C, country Rademacher weights, CV1 studentization and the plus-one rule. The confidence intervals are not bootstrap intervals.

Bootstrap repetitions: 99,999. Main/robustness base seed: 20261007 with sample/outcome/window/component offsets recorded in result rows. Main prior-12-month between/within seeds: 20261128/20261129; direct contrast seed: 20261007. Covariate and temporal models retain their script-specific seeds. LOCO has no bootstrap p-values. Production checks on keys, windows, input agreement and convergence remain enabled.

Figure 1B groups `100 × (monthly reactive indicator − country mean + overall mean)`, not an observed probability. It uses six negative quantile groups, an exact-zero group (7), and three positive quantile groups, keeping ties together. Figure 2 uses full-25-country component-specific population SDs as common references within each window across country samples and outcomes. The inclusive sensitivity replaces t−12…t−1 with t−11…t, retaining exactly 12 months; it cannot establish within-month ordering. Year indicators use 2015–2019 with July–December 2014 as reference, not year-month fixed effects.

### Baseline covariates

Each adjustment is separate, on the unchanged main panel. Coefficient movement does not quantify a proportion explained or establish capacity mechanisms.

- Income: `analysis/covariates/income/country_income_fy2015.csv`, author-coded from the World Bank [Global Monitoring Report 2014/2015, Appendix F, Table F.1, p. 220](https://www.worldbank.org/content/dam/Worldbank/gmr/gmr2014/GMR_2014_Appendices.pdf). FY2015 categories use 2013 Atlas GNI per capita. The covariate is low-income versus other included categories.
- Expenditure: `analysis/covariates/expenditure/ihme_2013/country_ihme_2013.csv`, from the September 2019 [IHME Global Health Spending 1995–2016 release](https://doi.org/10.6069/DDZE-FY49). Original CSV, DTA and information sheet remain in `source/`. Separate models use 2013 country-level government and total per-capita means in constant 2018 PPP dollars, transformed with `ln(1+x)`. These retrospective estimates are not necessarily direct country-year observations. Scripts check CSV/DTA agreement.
- Prior campaign: `analysis/covariates/prior_campaign/country_prior_ocv_campaign_pre2014jul.csv`. A positive requires documented mass OCV administration before 1 July 2014, regardless of purpose or funding. Requests, approvals, shipments, small trials and traveller vaccination alone do not qualify. Interrupted campaigns qualify if administration preceded cutoff. Seven positives: DR Congo, Guinea, Mozambique, South Sudan, Sudan, Tanzania and Uganda. Country-specific sources, passages and the Ethiopia boundary are in `source_ledger.json`. Eighteen zeros mean not documented, not verified absence. DR Congo's November 2013 Kalemie administration is documented by [Massing et al.](https://doi.org/10.1371/journal.pntd.0006369).

## External-documentation audit

All 22 reactive request-months with zero preceding activity are audited: 24 request-record IDs in 12 countries; 20 also lack request-month activity. No source data or fitted panel are recoded. `curated_evidence.py` retains metadata, supporting passages, date bounds, correspondence and unresolved questions; `evidence_categories.py` applies current categories. `outputs/source_ledger.csv` provides titles, issuers, dates, URLs, passage locators, limitations and supplementary citation mappings. Stable source IDs differ from manuscript numbers.

The search was targeted, not systematic. Recoverable English queries date to 17 October 2026 and combine country, cholera/AWD, year/month, vaccine/campaign and locations, including targeted WHO and ReliefWeb searches. The retained internal query log covers only that resumed session, not every earlier search. English content was used without a systematic non-English search. Le Minh reviewed and finalized classifications; Wayne reviewed grouping and source validity, not an independently duplicated classification. Later reports were eligible when describing the actual t−12…t−1 window; publication dates are not onset dates. Full-source follow-up occurred on 22–24 October. Scripts do not download or revalidate reports.

Current categories: DD=2 (date/dose correspondence, not independent confirmation of a dashboard ID), Q=1 (quantity-only candidate, not confirmed identity), CW=14 (country/window correspondence only), NE=5 (preceding activity not established, not absence). Thus 3/14/5 requires distinguishing DD from Q. Activity was documented for 17/22, including 15/20 also lacking request-month activity. Sources may share surveillance, and episodes can support multiple rows; these are not sensitivity estimates or counts of requests explained. Legacy evidence grades in retained data are not current categories.

The author-supplied complete WHO Week 13 bulletin was read on 22 October: PDF page 4, printed page 03, SHA-256 `5fd96139c7f930b1eeea16d535afdfede390ac789f322ab38cac59d916da107e`. It documents northern Mozambique activity in March 2018, not the target of the March 2019 request. The public URL and locator remain in the ledger; the third-party bulletin and earlier screenshot are not redistributed. Week 40 bulletin metadata use the retained ReliefWeb URL. Annual totals alone do not establish activity inside a narrower window. Source disagreement and uncertain linkage remain explicit.

## Outputs

`manuscript_outputs/tables/` contains Table 1, Tables S1–S12 and the direct contrast. `manuscript_outputs/figures/` contains Figures 1, 2, S1 and S2; Figure 1 combines A/B in one PNG and vector PDF. Captions are supplied in the manuscript, not in this package. Earlier manuscript exports are not distributed or recreated by the exporter. Intermediate data, model-result JSON and figure data remain beside generating scripts.

Reference manuscript: `Research Document - main (2).pdf`, SHA-256 `0cc46016fe9f7e3768c29910a3cdd85e2548fd85d8401c2d96b0c07d8eaed583`; not redistributed. Reproduction reconstructs analytical outputs, not typeset pages or independent source verification. Original data rights and conditions remain with their providers.
