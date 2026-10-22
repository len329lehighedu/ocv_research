# Audit of reactive request-months with zero prior recorded activity

Protocol fixed before case classification, 17 October 2026.

## Question and unit

Audit all 22 reactive country-months with zero active record-months in the
preceding 12 calendar months in the frozen Zanzibar-inclusive panel. Twenty
also have no source record active in the request month. The 22 months link
to 24 request-record IDs, not necessarily 24 independent submissions.
This is an external-documentation audit, not a validation sample of all
58 events and not an estimate of surveillance sensitivity or specificity.

## Sources and search strategy

For every country-month search official WHO DON/AFRO, ministry/UN reports,
ReliefWeb original-issuer documents and campaign/outbreak research. Start
with country + cholera/AWD + year/month, then vaccine/campaign and relevant
place names. Search the actual t-12 through t-1 window and assess month t
separately. Later publications are eligible when they explicitly describe
earlier events; their publication date is not the outbreak date or proof
of information available to authorities at submission. A report of vaccine
delivery/campaign is not the original request date. Inaccessible full text
and uninformative searches are recorded rather than treated as negatives.
Searches are grouped by country for efficiency, but each month gets its own
temporal assessment. Stop after baseline search plus targeted follow-up
for unresolved/ambiguous cases; no target fraction must be 'explained'.

Prioritize primary issuers and direct passages. Syndication is not independent
corroboration. External reports can share underlying surveillance with Zheng;
'external' does not assert statistically independent ascertainment.

## Comparisons and evidence

Record source title, issuer, date, URL, relevant section, minimal supporting
extract, original disease label, event date(s), geography and explicit
request/campaign linkage where present. Keep these distinct:

1. evidence of outbreak activity somewhere in the country;
2. compatibility with the specific 12-month window;
3. compatibility with target geography;
4. direct identification of the request/campaign.

Most request targets are not recorded in the input CSV. Do not fill them
from a plausible campaign without labelling the linkage as provisional.
Do not infer a classification error from an ICG identifier, humanitarian
context, or a preventive campaign elsewhere in that country-year.

Evidence grades: A = explicitly linked request/campaign identification;
B = temporal/geographic compatibility without request linkage;
C = contextual or uncertain-time/geography evidence; U = unresolved.
Grade is about linkage, not truth of cholera absence. A paper describing a
campaign without an ID may establish a campaign's preventive character but
does not establish that our specific request record is mislabelled.

Use two separate categorical outputs: external preceding-window activity
(documented / timing-uncertain / not-established), and likely explanation
(external-record discordance / same-month boundary / possible label or date
discordance / contextual risk / unresolved). Explanations are hypotheses
unless record-specific evidence identifies the mechanism. No missing source
record is declared a proven compilation error: Zheng applied operational
thresholds and uninterrupted-reporting criteria, not a census of official
outbreak declarations (Methods, DOI 10.1016/j.ijid.2022.05.039).

## Guardrails

Do not recode any source, outcome, predictor or frozen estimate. Absence of
a report found by this search is not absence of cholera. Raw activity zero
can still give a negative within deviation. No result proves that source
discordance caused the within-null finding. No de-identified record is
reidentified solely on the basis of an apparent date/geography match.

## Verification gates

- Exact 22-row master, 24 unique linked record IDs, 12 countries; 20+2 current
  activity split. Join by country and month, never ID prefix alone.
- Independent interval-overlap check against unchanged fundamental outbreak
  dates for prior and current counts. Explicit Tanzania/Zanzibar mapping.
- Check t-12/t-1/t boundaries, actual versus publication dates, suspected
  versus confirmed cholera, and campaign versus request dates.
- Every classified statement links to a read source passage, not a search
  snippet; inaccessible/context-only sources cannot become positive proof.
- All master rows assessed, no duplicate counting when one source supports
  multiple months; 22-month denominator retained in summaries.
- Review strongest claims a second time, especially date/classification
  discordance. Preserve competing explanations and contradictory evidence.
- Input hashes unchanged after audit; generated outputs include a source
  ledger, search log, evidence assessments and a reproducible summary table.

## Public-only scope and classification clarification (17 October continuation)

Only public epidemiological dates, locations, disease labels, and administrative
request/campaign history are extracted. No laboratory procedures, molecular
comparisons, or experimental instructions are extracted. Sources requiring
credentials or failing public access are not used as positive evidence.

Grade A may identify an explicitly described request matching date and quantity
in our record; this is a strong reconstructed linkage, NOT confirmation of a
dashboard request ID. The table states the matching fields and limitations.
Grade B can establish activity in the same country/window without identifying
the request's target area. Grade C is context only. These are analyst judgments,
not validated probabilities. Disease activity status is evaluated separately.

Month-only dates are stored as closed month bounds, not invented day-level onset
dates. Bounds identify a reported event interval and do not assert uninterrupted
transmission throughout it. Timing conflicts are retained as timing-uncertain.
The search log records only recoverable, actually executed queries in the resumed
session, not a reconstructed history of earlier interrupted searches.
