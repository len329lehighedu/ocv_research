# Recorded-opportunity audit for the frozen 25-country panel

11 October 2026. Descriptive audit only; no model was fitted or revised.

## Scope and definitions

The denominator remains all 25 countries × 66 months (July 2014–December
2019), or 1,650 country-months. The outcome is the frozen dashboard-classified
reactive request-month indicator (58 event-months). The outbreak source is the
999-row Zheng et al. file. Five rows belong to Mali or Guinea-Bissau, outside
the 25-country panel; 994 source rows map to the panel countries. The one
`TZA_zanzibar` row is included under Tanzania.

An *active record-month* means one Zheng source row whose recorded start–end
interval touches a calendar month, with both endpoint months included.
Concurrent rows are counted separately. This is not a count of independent
epidemics, affected persons, true cholera events, or feasible requests. The
frozen lag-12 predictor sums these active record-months over months m−12 to
m−1, excluding outcome month m. The country mean is the mean of
`ln(1 + lag-12 count)` over the 66 estimation months. A positive-lag month
means its raw lag-12 count exceeds zero.

The audit script reconstructs every current-month and lag-12 count directly
from source dates, separately from the original shift/rolling implementation.
All 1,650 current counts, lag-12 counts, logged values, country means, and
within deviations reconcile to the frozen panel to numerical tolerance. It
also verifies all 58 reactive outcomes against `request_outcomes.csv`.

## Main findings

- Only 316/1,650 country-months (19.2%) contain at least one active Zheng
  record in the outcome month. They contain 27/58 reactive request-months.
  The other 31 request-months have no same-month active source record.
- Only 647/1,650 country-months (39.2%) have a positive prior-12-month
  predictor. They contain 36/58 reactive request-months. The other 22/58
  (37.9%) have a zero lag-12 predictor; 20 of those 22 also have no active
  record in the request month.
- Four countries have a zero lag-12 predictor for all 66 months: Burundi,
  Republic of the Congo, Sierra Leone, and Sudan. Together they account for
  264 country-months and five reactive request-months. Seven countries have
  no active record *during the estimation period*; Benin, Guinea and Namibia
  nevertheless have positive lag-12 months because of earlier source records.
- The 504 source rows whose date intervals overlap the estimation period
  generate 1,883 active record-months across the 25 countries. Ethiopia
  (973), DR Congo (277), and Nigeria (179) account for 1,429/1,883 (75.9%)
  of these record-months, yet 15/58 reactive request-months. Large
  cross-country differences in the recorded predictor may therefore reflect
  the source's geographic detail and surveillance coverage as well as
  disease activity. This pattern alone cannot quantify each explanation.

### Cross-classification of country-months

| Prior 12 months have active record? | Outcome month has active record? | Country-months | Reactive request-months |
|:--|:--|--:|--:|
| No | No | 986 | 20 |
| No | Yes | 17 | 2 |
| Yes | No | 348 | 11 |
| Yes | Yes | 299 | 25 |
| **Total** | | **1,650** | **58** |

These are *observed-source* strata, not eligibility strata. For example,
restricting the sample to outcome months with an active source record would
retain only 27/58 event-months and change the research question. Restricting
to positive lag-12 months would retain 36/58. Neither restriction identifies
requests caused by a particular outbreak.

### Country-level audit

`Records in panel` counts source rows whose intervals intersect July
2014–December 2019. `Active record-months` sums active source rows across
those 66 months. `Active months` counts months with at least one such row.
`Positive lag months` counts months with at least one recorded outbreak-month
in m−12 through m−1. Request columns count reactive *country-months*.

| Country | Records in panel | Active record-months | Active months | Positive lag months | Mean log lag-12 | Reactive requests | Requests at zero lag | Requests at zero current |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| Angola | 1 | 3 | 3 | 14 | 0.2643 | 0 | 0 | 0 |
| Benin | 0 | 0 | 0 | 10 | 0.2905 | 0 | 0 | 0 |
| Burundi | 0 | 0 | 0 | 0 | 0.0000 | 1 | 1 | 1 |
| Cameroon | 14 | 59 | 20 | 45 | 1.6593 | 3 | 0 | 2 |
| Chad | 2 | 8 | 4 | 15 | 0.4407 | 2 | 1 | 1 |
| DR Congo | 75 | 277 | 65 | 66 | 3.9281 | 7 | 0 | 0 |
| Ethiopia | 247 | 973 | 40 | 49 | 3.4751 | 3 | 1 | 2 |
| Ghana | 1 | 2 | 2 | 13 | 0.2041 | 0 | 0 | 0 |
| Guinea | 0 | 0 | 0 | 4 | 0.0604 | 1 | 0 | 1 |
| Ivory Coast | 1 | 2 | 2 | 13 | 0.2041 | 0 | 0 | 0 |
| Kenya | 14 | 48 | 23 | 51 | 1.6761 | 0 | 0 | 0 |
| Malawi | 10 | 39 | 20 | 50 | 1.6170 | 5 | 1 | 1 |
| Mozambique | 1 | 4 | 4 | 15 | 0.3158 | 5 | 5 | 5 |
| Namibia | 0 | 0 | 0 | 10 | 0.1952 | 0 | 0 | 0 |
| Niger | 9 | 29 | 9 | 33 | 1.1786 | 3 | 1 | 1 |
| Nigeria | 58 | 179 | 46 | 66 | 3.4299 | 5 | 0 | 0 |
| Republic of the Congo | 0 | 0 | 0 | 0 | 0.0000 | 0 | 0 | 0 |
| Sierra Leone | 0 | 0 | 0 | 0 | 0.0000 | 1 | 1 | 1 |
| Somalia | 3 | 12 | 6 | 17 | 0.5377 | 2 | 0 | 2 |
| South Sudan | 31 | 111 | 25 | 53 | 2.4077 | 9 | 1 | 4 |
| Sudan | 0 | 0 | 0 | 0 | 0.0000 | 3 | 3 | 3 |
| Tanzania | 28 | 112 | 30 | 47 | 2.1535 | 2 | 2 | 2 |
| Uganda | 5 | 15 | 12 | 49 | 1.2813 | 0 | 0 | 0 |
| Zambia | 2 | 6 | 3 | 14 | 0.3769 | 4 | 4 | 4 |
| Zimbabwe | 2 | 4 | 2 | 13 | 0.3015 | 2 | 1 | 1 |
| **Total** | **504** | **1,883** | **316** | **647** | | **58** | **22** | **31** |

The zero-lag request-months are enumerated by the read-only audit script.
They span 12 countries, so the mismatch is not confined to one outlier.
Mozambique contributes five and Zambia four; all nine have neither current-
month nor prior-12-month source activity in their request months. These
descriptive counts should prompt source review, not recoding or deletion.

## Reviewer-style interpretation and decision

**What the audit supports:** The paper can say that the *recorded* outbreak
measure captures very uneven observable exposure across countries, and that
many dashboard-classified reactive requests occur outside recorded-source
activity in the same month or previous 12 months. The frozen between
coefficient therefore cannot be interpreted as a per-outbreak request
propensity or as evidence that higher recorded activity is *only* a capacity
effect. The audit strengthens the need to state measurement limitations.

**What it does not support:** Zero Zheng records do not prove absence of
cholera, absence of operational opportunity, or incorrect reactive coding.
Source rows can represent multiple subnational reporting units for an
epidemic. Their number is influenced by spatial resolution, reporting
coverage, outbreak-extraction rules, and time; source rows are not
independent opportunities. The request data do not link requests to source
records. The comparison is ecological and descriptive, not causal.

The Zheng et al. article reports gaps between outbreaks and only 54% average
surveillance-data coverage across the study period (range 5–100%), with
heterogeneous sources and case definitions. WHO explicitly cautions that
annual cholera reporting can be absent, unstable, under- or over-reported,
and non-comparable between countries. These external statements explain why
source zero is ambiguous; no independent WHO case series was merged into
this audit.

## Reproducibility and sources

Run, without modifying files:

```bash
python3 -B -m research_pipeline.opportunity.audit_recorded_opportunity
```

Local inputs: `final_output/fundamental_data/zheng_outbreak_records.csv`,
`final_output/tables_and_graphs/analysis_data/active_outbreak_panel.csv`, and
`final_output/tables_and_graphs/analysis_data/request_outcomes.csv`.

- Zheng Q et al. *Cholera outbreaks in sub-Saharan Africa during 2010–2019:
  a descriptive analysis*. International Journal of Infectious Diseases,
  2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC9439956/
- WHO. *Cholera cases and deaths*: annual reported-data scope and reporting
  limitations. https://www.who.int/emergencies/surveillance/cholera-cases-and-deaths
