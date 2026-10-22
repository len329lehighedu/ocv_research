# Data and coding dictionary

## Canonical original inputs: `data/source/`

- `zheng_outbreak_records.csv`: 999 source outbreak records with start/end dates and outbreak descriptors. Records active in a month are counted inclusively, including records starting before the analysis history if they overlap it. Final case totals are not used in the activity predictor. Original spelling, geographic codes and dates are retained; the crosswalk is in the builder.
- `requests.csv`: reconstructed dashboard records plus the separately sourced January 2014 South Sudan entry. Contains identifiers, country, request/decision dates, dose fields and campaign labels. Non-numeric status strings and missing entries are retained. Reactive classification follows the saved label, not the ICG/GTFCC identifier. Multiple records within a month produce one event-month.
- `deliveries.csv`: recorded delivery rounds. Preserve original columns, including the duplicate `doses_delivered` header; pandas distinguishes the second occurrence with a suffix. Reproduction code explicitly uses the original first dose column and the numeric round/interval fields. There are 100 numeric delivery-round records; 92 have decision-to-delivery intervals. These are not 100 distinct requests.

## Derived panel

`analysis/main/outputs/analysis_data/active_outbreak_panel.csv`

- `country`, `yearmonth`: unique country-month key; 25 × 66 balanced rows.
- `reactive_request`: 1 when at least one saved request is classified reactive in that month.
- `request_this_month`: 1 for at least one request of any saved campaign label.
- `active_outbreaks_this_month`: count of source records active from start month through end month inclusive. Overlapping subnational records contribute separately.
- `active_outbreak_months_prior_{1,3,6,12}m`: sum of active-record counts in the preceding calendar months; outcome month excluded.
- `log1p_active_outbreak_months_{L}m`: natural log of 1 plus the preceding sum.
- `..._between`: country mean of the logged predictor across the common 66 estimation months, not log of a raw mean.
- `..._within`: logged monthly value minus that country's logged mean.

These measure recorded activity, not case counts, severity, distinct request opportunities or real-time information. A zero is not evidence of no cholera. The inclusive temporal sensitivity replaces t−12…t−1 with t−11…t, retaining exactly 12 months and recomputing means/deviations.

## Covariate inputs and provenance

- Income: `analysis/covariates/income/country_income_fy2015.csv`, author-coded from World Bank *Global Monitoring Report 2014/2015*, Appendix F/Table F.1. FY2015 categories use 2013 Atlas GNI per capita. The binary term distinguishes low-income from other categories; it is not a direct capacity measure. Source URL and decisions are in `method_protocol.md`.
- Expenditure: `analysis/covariates/expenditure/ihme_2013/source/` retains the September 2019 IHME Global Health Spending 1995–2016 CSV, DTA and information sheet. `country_ihme_2013.csv` is the 25-country lookup. Use 2013 country-level government/total per-capita means in constant 2018 PPP dollars, transformed with ln(1+x), in separate models. CSV/DTA agreement and the lookup are checked. These are retrospectively released estimates, not necessarily direct observations.
- Prior campaign: `analysis/covariates/prior_campaign/country_prior_ocv_campaign_pre2014jul.csv` and `source_ledger.json`. A positive requires documented mass OCV administration before 1 July 2014, not merely a request, approval or shipment. Seven positives include DR Congo and South Sudan. Zero means not documented in audited sources, not verified absence. Preserve the method protocol and zero-country literature audit as coding provenance.

## External-documentation audit

`analysis/request_month_audit/curated_evidence.py` retains source metadata, date anchors, linkage assessments and unresolved questions. `PROTOCOL.md`, `search_log.json`, source ledger and the author-supplied Mozambique excerpt document the assessment. The compiler does not retrieve websites. Outputs distinguish same-country/window documentation from identification of the outbreak targeted by a request. Sources can share surveillance and one episode can support multiple rows; 17/22 is not an estimated sensitivity or count of requests explained.
