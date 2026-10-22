#!/usr/bin/env python3
"""Write the Section 3.1 and Figure 1/2 tables from the saved raw sources.

The comparison column reproduces values quoted in the current manuscript
from Maffioli and Lu (2025); those published values are not recomputed from
their unavailable request-level data. Every reconstructed value is calculated
from the inputs supplied to this script.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_pipeline.data.build_active_outbreak_panel import COUNTRY_NAMES


def table(title: str, headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    lines = [f"# {title}", "", "| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def write_tables(outbreaks: pd.DataFrame, requests: pd.DataFrame,
                 deliveries: pd.DataFrame, panel: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    starts = pd.to_datetime(outbreaks.start_date, errors="raise")
    source = outbreaks.loc[starts.dt.year.between(2013, 2019)].copy()
    country_codes = source.country.replace({"TZA_zanzibar": "TZA"})
    mapped_countries = country_codes.map(COUNTRY_NAMES)
    if mapped_countries.isna().any():
        raise ValueError("Unmapped outbreak country")
    source_countries = set(mapped_countries)
    no_outbreak = sorted(set(panel.country.unique()) - source_countries)
    if len(source) != 576 or len(source_countries) != 22 or len(no_outbreak) != 3:
        raise ValueError("Outbreak summary no longer matches the manuscript universe")
    dated_requests = requests.copy()
    dated_requests["date"] = pd.to_datetime(
        dated_requests.request_date, format="%m/%d/%Y", errors="coerce"
    )
    dated_requests = dated_requests.loc[dated_requests.date.notna()].copy()
    request_country_count = dated_requests.country.nunique()
    if request_country_count != 18:
        raise ValueError("Expected 18 countries with a dated request")

    def mean(name: str) -> float:
        return float(pd.to_numeric(source[name], errors="coerce").mean())

    outbreak_rows = [
        ("Number of countries", panel.country.nunique(), "25"),
        ("Countries with an outbreak (2013–2019)", len(source_countries), "22"),
        ("Total outbreaks", len(source), "576"),
        ("Outbreaks/year/country", f"{len(source)/(7*25):.2f} (denominator=25)",
         "3.7 (denominator=22)"),
        ("Countries with no recorded outbreak", ", ".join(no_outbreak),
         "Burundi, Sierra Leone, Sudan"),
        ("Countries requesting OCV", request_country_count, "18"),
        ("Suspected cases/outbreak", f"{mean('total_suspected_cases'):.0f}", "519"),
        ("Confirmed cases/outbreak", f"{mean('total_confirmed_cases'):.1f}", "36.4"),
        ("Deaths/outbreak", f"{mean('total_deaths'):.2f}", "4.81"),
        ("Duration (weeks)", f"{mean('duration'):.1f}", "12.9"),
        ("Threshold (cases/week)", f"{mean('threshold'):.1f}", "10.1"),
        ("Attack rate (/1,000)", f"{mean('attack_rate'):.2f}", "5.24"),
        ("CFR (%)", f"{mean('cfr'):.2f}", "1.85"),
        ("Mean R0", f"{mean('mean_R0'):.2f}", "1.90"),
        ("Rural outbreaks (%)", f"{100*source.rural_urban.str.contains('Rural', na=False).mean():.1f}", "82.6"),
        ("Population density", f"{mean('population_density'):,.0f}", "6,245.9"),
    ]
    (output_dir / "section_3_1_outbreak_comparison.md").write_text(
        table("Section 3.1: outbreak-source comparison",
              ("Indicator", "This study", "Maffioli and Lu (2025)"), outbreak_rows),
        encoding="utf-8",
    )

    req = dated_requests.copy()
    req["requested"] = pd.to_numeric(req.doses_requested, errors="coerce")
    req["approved"] = pd.to_numeric(req.doses_approved, errors="coerce")
    dashboard = req.loc[req.request_id.ne("n/a")]
    rounds = deliveries.copy()
    rounds["round"] = pd.to_numeric(rounds.round_number, errors="coerce")
    rounds["days"] = pd.to_numeric(rounds.days_since_decision, errors="coerce")
    rounds["doses"] = pd.to_numeric(rounds.doses_delivered, errors="coerce")
    rounds = rounds.loc[rounds["round"].notna()].copy()
    valid = rounds.loc[rounds.days.notna()]
    first = valid.loc[valid["round"].eq(1)]
    last = valid.sort_values("round").groupby("request_id").tail(1)
    if (len(req), dashboard.request_id.nunique(), int(dashboard.approved.gt(0).sum()),
            len(rounds), len(valid), len(first), len(last)) != (88, 87, 61, 100, 92, 61, 61):
        raise ValueError("Request/delivery summary no longer matches the manuscript")
    request_rows = [
        ("GTFCC Dashboard request IDs", dashboard.request_id.nunique(), "85"),
        ("Additional non-dashboard requests", len(req) - len(dashboard), "0"),
        ("Total requests", len(req), "85"),
        ("Dashboard requests with a positive numeric approval", int(dashboard.approved.gt(0).sum()), "60"),
        ("Delivery rounds", len(rounds), "96"),
        ("Delivery-round / approved-request count ratio", f"{len(rounds)/dashboard.approved.gt(0).sum():.2f}", "1.6"),
        ("Doses requested (millions)", f"{req.requested.sum()/1e6:.2f}", "88.14"),
        ("Doses approved (millions)", f"{req.approved.sum()/1e6:.2f}", "73.59"),
        ("Doses delivered (millions)", f"{rounds.doses.sum()/1e6:.2f}", "50.62"),
        ("Reactive requests", int(req.campaign_type.eq("Reactive").sum()), "66"),
        ("Preventive requests", int(req.campaign_type.eq("Preventive").sum()), "19"),
        ("Unclassified requests", int(req.campaign_type.eq("").sum()), "0"),
        ("Mean request-to-decision days", f"{pd.to_numeric(req.decision_days, errors='coerce').mean():.2f}", "10.4"),
        ("Mean decision-to-delivery days, all rounds", f"{valid.days.mean():.1f}", "83.3"),
    ]
    (output_dir / "section_3_1_request_comparison.md").write_text(
        table("Section 3.1: request/delivery comparison",
              ("Indicator", "This study", "Maffioli and Lu (2025)"), request_rows)
        + "\nThe count ratio uses 100 delivery rounds and 61 dashboard requests with a positive "
        "numeric approval. These are different count universes, not a mean of rounds per approved request.\n",
        encoding="utf-8",
    )

    figure_1_rows = [
        ("Decision → first delivery", "Request with a valid date", len(first), f"{first.days.mean():.1f} days"),
        ("Decision → last delivery", "Request with a valid date", len(last), f"{last.days.mean():.1f} days"),
        ("Decision → all delivery rounds", "Round with a valid date", len(valid), f"{valid.days.mean():.1f} days"),
    ]
    (output_dir / "figure_1_delivery_timing.md").write_text(
        table("Figure 1: delivery timing decomposition",
              ("Indicator", "Unit", "Observations", "Result"), figure_1_rows),
        encoding="utf-8",
    )

    cancelled = req.loc[req.note.eq("CANCELLED VIA ICG"), "requested"].sum()
    no_decision = req.loc[req.decision_date.isin(["n/a", ""]), "requested"].sum()
    partial_shortfall = (req.requested - req.approved).clip(lower=0).sum()
    approved = req.approved.sum()
    figure_2_rows = [
        ("Doses approved (This study)", f"{approved/1e6:.2f}"),
        ("Cancelled", f"{cancelled/1e6:.2f}"),
        ("No logged decision", f"{no_decision/1e6:.2f}"),
        ("Partial-approval shortfall", f"{partial_shortfall/1e6:.2f}"),
        ("Total of these components", f"{(approved+cancelled+no_decision+partial_shortfall)/1e6:.2f}"),
        ("Doses approved (Maffioli and Lu, 2025)", "73.59"),
    ]
    (output_dir / "figure_2_dose_comparison.md").write_text(
        table("Figure 2: dose arithmetic comparison", ("Category", "Doses (millions)"), figure_2_rows),
        encoding="utf-8",
    )
    print("Saved Section 3.1 comparison tables and Figure 1/2 tables")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbreaks", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--deliveries", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    write_tables(
        pd.read_csv(args.outbreaks),
        pd.read_csv(args.requests, keep_default_na=False),
        pd.read_csv(args.deliveries, keep_default_na=False),
        pd.read_csv(args.panel),
        args.output_dir,
    )


if __name__ == "__main__":
    main()
