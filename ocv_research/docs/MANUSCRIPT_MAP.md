# Manuscript output map

Current reference: `Research Document (3).pdf`, supplied 21 October 2026; SHA-256 `c4fe1ffd61ef244abbd9f2b1bb84147c512d08fb907eb6667b744241549d9995`. The manuscript itself is not copied into this package. This map concerns reproducible data/figures, not automatic reconstruction of manuscript prose or external citations.

| Item | File under `manuscript_outputs/` | Analysis origin |
|---|---|---|
| Table 1 | `tables/table_1_main_model.csv` | Main 25-country, 12-month model; includes odds ratios |
| Table S1 | `tables/table_s1_country_composition.csv` | Country panel composition; 66 months each, 58 events, 1,883 active record-months |
| Tables S2–S5 | Four numbered Markdown files in `tables/` | Reconstructed outbreak/request descriptions, timing and published dose comparison |
| Table S6 | `tables/table_s6_request_classification.csv` | Request classification |
| Table S7 | `tables/table_s7_dose_reconciliation.csv` | Dose arithmetic |
| Table S8 | `tables/table_s8_nonstandard_requests.csv` | Nonstandard request records |
| Table S9 | `tables/table_s9_external_documentation_audit.csv` | Audit, with source links and uncertainty fields |
| Table S10 | `tables/table_s10_robustness.csv` | All windows/outcomes/samples; asymptotic and bootstrap p-values |
| Table S11 | `tables/table_s11_any_active_months.csv` | Alternative any-active-month predictor |
| Table S12 | `tables/table_s12_leave_one_country_out.csv` | Primary plus all 25 omission models |
| Table S13 | `tables/table_s13_covariate_sensitivities.csv` | Main plus four separate adjustments, including added covariate estimates |
| Table S14 | `tables/table_s14_temporal_sensitivities.csv` | Main, year indicators, inclusive window |
| Direct contrast, Section 3.2 | `tables/between_within_contrast.csv` | Direct between-minus-within contrast |
| Figure 1A | `figures/figure_1a_between.png` | Between-country scatter |
| Figure 1B | `figures/figure_1b_within.png` | Adjusted-outcome ordered groups |
| Figure 2 | `figures/figure_2_robustness.png` | Common-reference-SD robustness coefficients |
| Figure S1 | `figures/figure_s1_delivery_rounds.png` | Delivery round positions |
| Figure S2 | `figures/figure_s2_dose_reconciliation.png` | Dose waterfall |
| Figure S3 | `figures/figure_s3_leave_one_country_out.png` | LOCO coefficients |
| Figure S4 | `figures/figure_s4_covariates.png` | Covariate sensitivity coefficients |

Underlying model tables, convergence diagnostics, seeds and plotting data remain in each `analysis/` module. CSV exports preserve more precision than the rounded manuscript display. The audit CSV intentionally retains more provenance than the compact typeset table. Comparator values attributed to Maffioli and Lu are transcribed published summaries, not regenerated from their unavailable request-level data.
