#!/usr/bin/env python3
"""Check the human-coded audit ledger and export the supplementary table.
Manuscript: Methods 2.4; Results 3.1; Table S7.
Code checks bookkeeping and dates; it does not establish source truth."""
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from curated_evidence import SOURCES, ASSESSMENTS
from evidence_categories import category, source_citations, CATEGORY_LABELS, REFERENCE_NUMBERS

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"

def require(test, message):
    """Stop with a clear error if a required check fails."""
    if not test:
        raise ValueError(message)

def read_csv(path):
    """Read CSV rows while allowing a UTF-8 byte-order mark."""
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def digest(path):
    """Return the file SHA-256 used to detect input changes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate_assessment(row, assessment, source_map):
    """Check one reviewed case, its sources and its dated evidence anchors."""
    require(assessment["audit_id"] == row["audit_id"], "Case key mismatch")
    require(assessment["prior_activity_status"] in
            {"documented", "timing-uncertain", "not-established"}, "Invalid status")
    require(assessment["evidence_grade"] in {"A","B","C","U"}, "Invalid grade")
    require(assessment["remaining_uncertainty"], "Every case needs explicit linkage limits")
    for sid in assessment["source_ids"]:
        require(sid in source_map, "Unknown source")
        require(source_map[sid]["access_status"] in {"read","read_landing_only"},
                "Unread source used in classified evidence")
    start, end = date.fromisoformat(row["prior_window_start"]), date.fromisoformat(row["prior_window_end"])
    anchors = assessment["prior_event_anchors"]
    require(bool(anchors) == (assessment["prior_activity_status"] == "documented"),
            "Positive prior activity requires dated anchors; uncertain cases must not carry positive anchors")
    for anchor in anchors:
        sid = anchor["source_id"]
        require(sid in assessment["source_ids"], "Anchor source not cited by case")
        require(source_map[sid]["access_status"] == "read", "Anchor cannot rely on unread/landing-only source")
        require(anchor["country"] == row["country"], "Wrong-country evidence")
        lower, upper = date.fromisoformat(anchor["date_lower"]), date.fromisoformat(anchor["date_upper"])
        require(start <= lower <= upper <= end, "Anchor not fully inside preceding window")
        require(anchor["precision"] in {"day","month","reported interval"}, "Date precision missing")

def validate():
    """Check all 22 cases, 24 request IDs, category membership and retained hashes."""
    roster = read_csv(OUT / "master_roster_22.csv")
    linkage = read_csv(OUT / "request_linkage_24.csv")
    source_map = {s["source_id"]:s for s in SOURCES}
    assessment_map = {a["audit_id"]:a for a in ASSESSMENTS}
    require(len(source_map)==len(SOURCES), "Duplicate source IDs")
    require(len(assessment_map)==len(ASSESSMENTS)==22, "Duplicate/missing assessment IDs")
    require(len(roster)==22 and len({(r['country'],r['yearmonth']) for r in roster})==22,
            "Wrong/duplicate roster keys")
    require(len({r['country'] for r in roster})==12, "Country count disagreement")
    require(set(assessment_map)=={r['audit_id'] for r in roster}, "Incomplete case coverage")
    require(len(linkage)==len({r['request_id'] for r in linkage})==24, "Wrong request-ID total")
    require(sum(int(r['n_request_record_ids']) for r in roster)==24, "ID sum disagrees")
    require(sum(int(r['active_outbreaks_this_month'])==0 for r in roster)==20, "Wrong current-zero split")
    require(all(int(r['active_outbreak_months_prior_12m'])==0 for r in roster), "Non-zero prior in roster")
    panel = read_csv(HERE / "inputs/active_outbreak_panel.csv")
    expected={(r['country'],r['yearmonth']) for r in panel
              if float(r['reactive_request'])==1 and float(r['active_outbreak_months_prior_12m'])==0}
    require(expected=={(r['country'],r['yearmonth']) for r in roster}, "Roster differs from frozen panel")
    require(len(panel)==1650 and sum(float(r['reactive_request']) for r in panel)==58,
            "Wrong full panel or event total")
    for row in roster:
        validate_assessment(row, assessment_map[row['audit_id']], source_map)
        group = category(row['audit_id'])
        require((group != 'NE') ==
                (assessment_map[row['audit_id']]['prior_activity_status'] == 'documented'),
                'Revision category contradicts preceding-window activity status')
        linked=[r for r in linkage if r['audit_id']==row['audit_id']]
        require(len(linked)==int(row['n_request_record_ids']), "Per-month ID mismatch")
        require(all(r['country']==row['country'] and r['yearmonth']==row['yearmonth']
                    and r['campaign_type']=='Reactive' for r in linked), "Wrong linkage fields")
    manifest=json.loads((OUT / "input_manifest.json").read_text())
    for rel, expected_hash in manifest['source_sha256'].items():
        require(digest(HERE.parents[1] / rel)==expected_hash, f"Canonical input changed: {rel}")
    for filename, expected_hash in manifest['snapshot_sha256'].items():
        require(digest(HERE / 'inputs' / filename)==expected_hash, f"Snapshot changed: {filename}")
    # Strong administrative matches are checked against saved source observations,
    # not only against notes typed in this audit. The external passage is reviewed manually.
    req=read_csv(HERE / 'inputs/requests.csv')
    for country, request_id, request_date, qty in [
        ('Malawi','2015-I01-D01','03/06/2015',210000),
        ('Zambia','2016-I04-D01','03/24/2016',598131)]:
        matches=[r for r in req if r['country']==country and r['request_id']==request_id]
        require(len(matches)==1, "Administrative match not unique")
        require(matches[0]['request_date']==request_date and
                int(matches[0]['doses_requested'].replace(',',''))==qty, "Administrative fields mismatch")
    candidate = [r for r in req if r['country'] == 'Mozambique' and
                 r['request_id'] == '2016-I06-D01']
    require(len(candidate) == 1 and
            int(candidate[0]['doses_requested'].replace(',', '')) == 425486,
            'Quantity candidate no longer matches retained record')
    require(Counter(category(r['audit_id']) for r in roster) ==
            Counter({'DD': 2, 'Q': 1, 'CW': 14, 'NE': 5}), 'Revision partition changed')
    return roster, source_map, assessment_map

def write_csv(path, rows):
    """Write the supplied records with one header row."""
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

def main():
    """Read inputs, run this script and save its outputs."""
    roster, sources, assessments=validate()
    rows=[]; anchors=[]
    for row in roster:
        a=assessments[row['audit_id']]
        rows.append({**row, **{k:v for k,v in a.items() if k not in
                    {'audit_id','source_ids','prior_event_anchors','evidence_grade'}},
                    'legacy_evidence_grade': a['evidence_grade'],
                    'evidence_category': category(row['audit_id']),
                    'evidence_category_label': CATEGORY_LABELS[category(row['audit_id'])],
                    'sources_numbered': source_citations(row['audit_id'], a['source_ids']),
                    'source_ids':'; '.join(a['source_ids']),
                    'source_urls':'; '.join(sources[s]['url'] for s in a['source_ids'])})
        anchors.extend({'audit_id':a['audit_id'],**anchor} for anchor in a['prior_event_anchors'])
    write_csv(OUT / 'supplementary_audit_22.csv',rows)
    write_csv(OUT / 'source_ledger.csv', [
        {**source, 'manuscript_reference_number': REFERENCE_NUMBERS.get(source['source_id'], ''),
         'used_in_current_table': any(source['source_id'] in a['source_ids'] for a in ASSESSMENTS)}
        for source in SOURCES])
    write_csv(OUT / 'dated_evidence_anchors.csv',anchors)
    statuses=Counter(a['prior_activity_status'] for a in ASSESSMENTS)
    categories=Counter(r['evidence_category'] for r in rows)
    current_zero=[r for r in rows if int(r['active_outbreaks_this_month'])==0]
    summary=dict(request_months=22,request_record_ids=24,countries=12,
                 full_reactive_request_months=58,zero_prior_percent=100*22/58,
                 zero_current_month=20,prior_activity_status=dict(statuses),
                 documented_among_current_zero=sum(r['prior_activity_status']=='documented' for r in current_zero),
                 evidence_categories=dict(categories),
                 collapsed_correspondence_groups={'DD_or_Q': categories['DD'] + categories['Q'],
                                                 'CW': categories['CW'], 'NE': categories['NE']},
                 category_revision_date='2026-10-22',
                 zero_within_deviation=sum(abs(float(r['log1p_active_outbreak_months_12m_within']))<1e-12 for r in rows),
                 negative_within_deviation=sum(float(r['log1p_active_outbreak_months_12m_within']) < -1e-12 for r in rows),
                 interpretation='Counts concern country/window documentation, not requests explained, independent outbreaks, or surveillance sensitivity.',
                 no_recoding=True)
    (OUT / 'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=[
        '# Public-source audit of 22 reactive request-months', '',
        'Audit initiated: 17 October 2026; evidence-category revision: 22 October; source traceability updated through 24 October 2026. '
        'Unresolved linkage and chronology questions remain. No panel, source label or estimate was changed.', '',
        '## What was checked', '',
        'The frozen panel has 58 reactive request-months. Of these, 22 (37.9%) have zero recorded activity '
        'in the preceding 12 calendar months; 20 of the 22 also have zero in the request month. '
        'The audit covers 12 countries and 24 request-record IDs. Two months each contain two IDs; '
        'those IDs are not assumed to represent separate submissions.', '',
        'The independent interval-overlap check reproduces the 22-month roster. '
        'Request-month activity and preceding-window activity are assessed separately. '
        'Source publication dates are not treated as event dates or evidence of real-time knowledge.', '',
        '## Results of the documentation search', '',
        f'- **{statuses["documented"]}/22** months have a read public report documenting activity '
        'somewhere in the same country within the specified preceding window.',
        f'- **{statuses["timing-uncertain"]}/22** has unresolved preceding-window chronology.',
        f'- **{statuses["not-established"]}/22** lack verified preceding-window activity in the sources checked. '
        'This does not mean no cholera occurred.',
        f'- Among the 20 also having zero request-month activity, **{summary["documented_among_current_zero"]}** '
        'have external preceding-window documentation.', '',
        f'Revision categories: **{categories["DD"]} DD**, **{categories["Q"]} Q candidate**, '
        f'**{categories["CW"]} CW**, **{categories["NE"]} NE**. '
        'The combined 3/14/5 presentation does not mean three confirmed request matches. '
        'DD and Q are distinguished below; the historical A/B/C/U grades are not the current categories.', '',
        f'**These are not {statuses["documented"]} requests explained.** Most targets are not present in the request CSV; '
        'country/window compatibility cannot prove that a report describes the outbreak or area the request '
        'addressed. Multiple months may share evidence from the same episode. Reports may share underlying '
        'surveillance sources with Zheng; they are external documents, not independent ascertainment. '
        'Here, documented activity includes reported cholera cases or a reported outbreak; it does not '
        'establish that an episode satisfied Zheng\'s operational outbreak eligibility rules. '
        'An event inside a 12-month window is also not necessarily close to submission.', '',
        '## Most informative record-level observations', '',
        '1. **Malawi, March 2015:** the paper documents a 6 March request for 210,000 doses, '
        'matching the saved record, and a February outbreak. This is not merely a request-month boundary issue [S03].',
        '2. **Zambia, March 2016:** the implementation report matches both 24 March and 598,131 doses; '
        'it documents activity in February [S18].',
        '3. **Mozambique, March 2019:** WHO explicitly dates a flood-risk request to 21 March, '
        'before the formal declaration on 27 March [S07,S08]. That does not establish absence before declaration. '
        'Two saved IDs share the date; requested and arrived quantities differ. The full author-supplied bulletin, read on 22 October, establishes northern activity in March 2018 inside the prior window, but does not link that episode to this request. This row is CW, not DD. The February-2018 end statement remains discrepant [S09,S10].',
        '4. **Mozambique, August 2016:** a preventive Nampula campaign report gives exactly 425,486 '
        'requested doses [S05]. This is a strong campaign candidate but lacks the submission date/ID; '
        'a label discrepancy remains possible, not proven, and the Reactive label is unchanged.', '',
        '## Case-by-case supplementary table', '',
        'DD = date-and-dose correspondence (no independently confirmed dashboard ID); '
        'Q = quantity-only candidate (identity not established); CW = country/window documentation only; '
        'NE = preceding-window activity not established, not verified absence of cholera. '
        'All explanations are hypotheses unless explicitly evidenced.', '',
        '| ID | Country / request month | Evidence | External finding | Request-link limitation | Sources |',
        '| --- | --- | --- | --- | --- | --- |'
    ]
    for r in rows:
        cite=r['sources_numbered']+'; '+', '.join(
            f'[{sid}]({sources[sid]["url"]})' for sid in assessments[r['audit_id']]['source_ids'])
        values=[r['audit_id'],r['country']+' / '+r['yearmonth'],r['evidence_category'],
                r['external_finding'],r['request_linkage'],cite]
        lines.append('| '+' | '.join(v.replace('|','/') for v in values)+' |')
    lines += ['', '## Interpretation boundaries', '',
        '- A zero in the derived series is demonstrably not interchangeable with no documented cholera nationally. '
        'The audit does not establish the extraction mechanism behind each mismatch.',
        '- Zheng used operational thresholds and reporting-continuity criteria [S22]. Official declarations '
        'and sporadic cases need not satisfy those eligibility rules. Do not describe every discrepancy as a missing-source error.',
        '- Neither country-level discordance nor pre-emptive campaign context proves that request labels are wrong. '
        'Do not recode them from this audit.',
        '- The audit does not establish the cause or magnitude of bias in the within-country estimate, '
        'nor validate promptness of any response.',
        '- Raw zero activity can yield a negative within deviation in a country with nonzero average activity. '
        f'Among these 22 events, {summary["negative_within_deviation"]} have a negative within deviation '
        f'and {summary["zero_within_deviation"]} have zero. Do not say all 22 contribute no within-country information.', '',
        '## What remains unresolved', '',
        'Chad July 2014 lacks verified target/chronology evidence. Ethiopia July 2014, Sierra Leone August 2019, '
        'South Sudan November 2019 and Sudan September 2015 have context rather than a record-specific '
        'outbreak explanation. For Mozambique March 2019, prior-window national activity is documented, but episode identity, request-target linkage and conflicting historical end-date accounts remain unresolved. '
        'Original request applications or dashboard target-area fields would strengthen most linkages, '
        'but are not necessary to retain an honest unresolved category.', '',
        '## Reproduction and verification', '',
        'Run `python3 compile_audit.py` from this directory. '
        'The compiler exports analytical CSVs and a report; it does not access the network or rerun models. '
        'Human source judgments are transparent in `curated_evidence.py`; they cannot be automatically '
        'revalidated by code. The executable roster builder independently checks source date intervals. '
        'Canonical files and snapshots must match the frozen SHA-256 manifest.', '',
        'The search log covers recoverable executed queries in the resumed session only; '
        'no retrospective exhaustive-search log is claimed. Inaccessible ECDC PDFs are retained in '
        'the source ledger but excluded from positive evidence. The complete author-supplied WHO March 2018 bulletin was read on 22 October; the earlier screenshot is retained as historical provenance. No new systematic search is claimed by this release update.', '',
        '## Source ledger', '']
    for s in SOURCES:
        lines += [f'### {s["source_id"]}: {s["title"]}', '',
                  f'{s["issuer"]}. {s["publication_date"]}. Access: {s["access_status"]}. '
                  + (f'[Source]({s["url"]}).' if s['url'] else 'No current usable URL; historical source not used in the current table.'), '',
                  f'Passage: {s["passage_locator"]}.', '',
                  s['supporting_summary']+' '+s['limitation'], '']
    (OUT / 'AUDIT_REPORT.md').write_text('\n'.join(lines)+'\n')
    checks={
        'execution_date':date.today().isoformat(),
        'roster_and_join':'PASS: 22 months / 24 unique record IDs / 12 countries / 20+2 current-month split',
        'frozen_panel_universe':'PASS: exact key equality, 1650 rows, 58 events',
        'evidence_bookkeeping':'PASS: unique IDs, all 22 cases assessed, source references resolved',
        'dated_anchors':'PASS: same country and entire date bounds inside the stated prior window',
        'access_gate':'PASS: inaccessible and landing-only sources cannot establish positive prior activity',
        'administrative_matches':'PASS: Malawi and Zambia exact dates/quantities match saved records',
        'revision_categories':'PASS: DD=2, Q=1, CW=14, NE=5; source numbers mapped to supplied manuscript',
        'hashes':'PASS: canonical inputs, model results and snapshots unchanged',
        'manual_source_truth':'NOT AUTOMATED: source passage judgments require author review',
        'causal_explanations':'NOT ESTABLISHED',
    }
    (OUT / 'verification_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    print('PASS: bookkeeping, dates, country matching, access gates, and frozen hashes. Source truth is not an automated test.')

if __name__=='__main__':
    main()
