# Documented pre-panel OCV campaign sensitivity protocol

Revision 13 October 2026: the original model and definition are unchanged; historical coding was corrected using documented November 2013 vaccine administration in Kalemie. Original protocol and results are preserved in `archive_pre_correction_2026-10-13/`. This correction is evidence-driven, not selected by the new coefficient. Frozen primary, income and expenditure outputs remain unchanged.

## Definition

For country c, P_c = 1 if a reviewed source documents vaccine administration during a mass OCV campaign somewhere in that country before 1 July 2014; P_c = 0 means no qualifying campaign documented in audited sources, not verified absence. Include reactive, preventive and humanitarian campaigns irrespective of product or funding. Requests, approvals and shipments alone do not qualify. Individual traveller vaccination and small volunteer immunogenicity trials are not mass campaigns. Interrupted campaigns qualify when administration preceded cutoff. Assign by implementation country; Zanzibar maps to Tanzania, not recipient nationality. Publications after cutoff may document earlier implementation. Do not use post-cutoff experience or a time-varying indicator.

Seven documented positive countries: DR Congo (Kalemie, November 2013), Guinea (2012), Mozambique (Beira 2003–04), South Sudan (Maban December 2012–February 2013; also 2014), Sudan (Darfur 2004), Tanzania (Zanzibar 2009), Uganda (Adjumani 1997). Eighteen others are not documented. Ethiopia stays zero: MSF dates first large-scale administration to 24 July–2 August 2014, although a request was submitted earlier. Evidence is in `source_ledger.json` and the zero-country audit.

## Unchanged model and sample

Use the same 25 countries, 66 months (July 2014–December 2019), 1,650 observations and 58 dashboard-classified reactive request-months. Let A_cm sum active source outbreak records in months m−12 through m−1, excluding outcome month and including each active calendar month of each record. Z_cm = ln(1+A_cm), B_c = the mean of Z over the same 66 months, W_cm = Z_cm−B_c.

Fit one pooled logistic model:

`logit Pr(Y_cm=1) = alpha + beta_B B_c + beta_W W_cm + gamma P_c`.

Do not add other country covariates jointly, redefine outcomes or windows, or drop countries. This is not country-fixed-effects logistic regression. Coefficients are per-unit log-odds associations. Gamma contrasts seven documented-history countries with 18 not-documented countries, not a causal effect of capacity or learning.

## Inference and mandatory gates

Use binomial GLM, country-cluster sandwich covariance with `use_correction=False` and normal asymptotic 95% CIs. For between/within activity terms only, reuse the frozen restricted score-linearized WCLR-C bootstrap, country Rademacher weights, 99,999 replications, fixed seeds 20261128 and 20261129. Bootstrap observed t uses CV1 studentization. Displayed CIs are not bootstrap intervals. Do not select the specification by gamma's p-value.

Before reporting:

1. Validate 25 unique country/ISO3 keys, ledger/lookup agreement, seven positives with administration evidence, cutoff dates and not-documented semantics. Check DR Congo, Ethiopia, South Sudan and Zanzibar explicitly.
2. Preserve the first 21 frozen columns byte-for-byte and all 1,650 keys, outcomes and numeric values. Country status is constant over all 66 rows.
3. Independently reconstruct all lag counts from 999 source intervals, including Zanzibar-to-Tanzania mapping; validate log transformation, country means and mean-zero deviations.
4. Refit the unadjusted model and reproduce frozen coefficients, CIs and AIC to numerical tolerance. Check adjusted rank, convergence, finite estimates, probabilities and covariance. Do not rescue a failed fit by changing the sample.
5. Report support, country-level correlation, standardized condition number and all 25 one-country-deletion fits. Seven positive countries contribute 27 reactive event-months, including South Sudan nine and DR Congo seven. Record hashes of sources, code and protocol.
6. Repeat the full seeded run and compare outputs; independently fit the likelihood with a separate Logit estimator. Verify frozen files remain unchanged.

## Sources and interpretation

WHO January 2014 guidance and WHO SAGE 2017 Table 3 support the original six settings but are not exhaustive inventories. Luquero et al. (2013) verifies Guinea implementation, Porta et al. (2014) verifies Maban administration, WHO EMRO's 2004 report verifies Darfur, and Massing et al. (2018), DOI 10.1371/journal.pntd.0006369, verifies Kalemie November 2013 administration. The ledger supplies URLs and source passages. A Methods citation to the historical inventory plus Massing is useful; a supplementary country coding table should show country, period, site, evidence and citation. Not every positive requires a distinct paper if a cited inventory explicitly documents administration for several countries.

Historical campaigns are heterogeneous, subnational and often externally managed. They may reflect earlier burden, partners and access, and adjustment may introduce pathway or collider bias. Stability does not exclude unmeasured capacity. The country mean includes future estimation months relative to early outcomes, so the model is descriptive, not a real-time forecasting rule. Zero documented history is not zero knowledge. Do not interpret coefficient differences as the fraction explained because logistic coefficients are noncollapsible. No causal, outbreak-specific opportunity or delay inference is identified.
