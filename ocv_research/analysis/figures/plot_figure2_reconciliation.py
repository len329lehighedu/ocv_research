#!/usr/bin/env python3
"""Reproduce Figure 2 from the reconstructed OCV request records.

The figure reconciles independently summed requested and approved dose totals.
All arithmetic uses unrounded dose counts; only plotted labels use millions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REQUESTS = ROOT / "data/source" / "requests.csv"
DEFAULT_PNG = ROOT / "analysis/figures/reconciliation_outputs" / "figure2_reconciliation_revised.png"
DEFAULT_CSV = ROOT / "analysis/figures/reconciliation_outputs" / "figure2_reconciliation_data.csv"


def build_stages(source: pd.DataFrame) -> pd.DataFrame:
    req = source.copy()
    req["date"] = pd.to_datetime(req["request_date"], format="%m/%d/%Y", errors="coerce")
    req = req.loc[req["date"].notna()].copy()
    req["requested"] = pd.to_numeric(req["doses_requested"], errors="coerce")
    req["approved"] = pd.to_numeric(req["doses_approved"], errors="coerce")

    requested = int(req["requested"].sum())
    approved = int(req["approved"].sum())
    not_approved = int(req.loc[req["doses_approved"].eq("NOT APPROVED"), "requested"].sum())
    cancelled = int(req.loc[req["note"].eq("CANCELLED VIA ICG"), "requested"].sum())
    no_decision = int(req.loc[req["decision_date"].isin(["n/a", ""]), "requested"].sum())
    shortfall = int((req["requested"] - req["approved"]).clip(lower=0).sum())
    excess = int((req["approved"] - req["requested"]).clip(lower=0).sum())
    missing_requested = req.loc[req["requested"].isna() & req["approved"].notna()]
    approved_missing_requested = int(missing_requested["approved"].sum())

    # These two exceptions should remain named rather than being silently pooled.
    assert set(req.loc[(req["approved"] - req["requested"]) > 0, "country"]) == {"Tanzania"}
    assert set(missing_requested["country"]) == {"Malawi"}

    adjustments = [
        ("Requested", requested),
        ("Not approved", -not_approved),
        ("Cancelled", -cancelled),
        ("No logged decision", -no_decision),
        ("Partial-approval shortfall", -shortfall),
        ("Tanzania: approved excess", excess),
        ("Malawi: approved with missing requested dose", approved_missing_requested),
    ]
    cumulative = requested
    rows = [{"stage": "Requested", "change_doses": requested, "cumulative_doses": requested}]
    for name, change in adjustments[1:]:
        cumulative += change
        rows.append({"stage": name, "change_doses": change, "cumulative_doses": cumulative})
    assert cumulative == approved, f"waterfall {cumulative:,} != approved {approved:,}"
    rows.append({"stage": "Approved", "change_doses": approved, "cumulative_doses": approved})
    return pd.DataFrame(rows)


def plot(stages: pd.DataFrame, out: Path) -> None:
    blue, red, green = "#205878", "#c85a47", "#2c8568"
    gray, ink, muted = "#a8b2b9", "#263743", "#5f7180"
    labels = [
        "Requested", "Not\napproved", "Cancelled", "No logged\ndecision",
        "Partial-approval\nshortfall", "Tanzania\nexcess",
        "Malawi\nmissing dose", "Approved",
    ]
    values = stages["change_doses"].to_numpy(dtype=float) / 1e6
    totals = stages["cumulative_doses"].to_numpy(dtype=float) / 1e6
    x = np.arange(len(stages))
    width = 0.67

    fig, ax = plt.subplots(figsize=(11.2, 6.4), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_ylim(0, 99)
    ax.set_xlim(-0.55, 7.55)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#e6ebee", lw=0.8)

    for i in range(1, 7):
        ax.plot([x[i - 1] + width / 2, x[i] - width / 2],
                [totals[i - 1], totals[i - 1]], color=gray, lw=1.15, zorder=1)
    ax.plot([x[6] + width / 2, x[7] - width / 2],
            [totals[6], totals[6]], color=gray, lw=1.15, zorder=1)

    for i in range(8):
        if i in (0, 7):
            bottom, height, color = 0, totals[i], blue
        else:
            bottom = min(totals[i - 1], totals[i])
            height = abs(values[i])
            color = red if values[i] < 0 else green
        ax.bar(x[i], height, width=width, bottom=bottom,
               color=color, edgecolor="white", linewidth=0.5, zorder=2)

    ax.text(0, totals[0] + 1.3, "89.09", ha="center", va="bottom",
            fontsize=11.5, fontweight="bold", color=ink)
    for i in (1, 3, 4):
        mid = (totals[i - 1] + totals[i]) / 2
        ax.text(i, mid, f"{values[i]:+.2f}", ha="center", va="center",
                fontsize=10, fontweight="semibold", color="white")

    ax.annotate(f"{values[2]:+.2f}", xy=(2, (totals[1] + totals[2]) / 2),
                xytext=(2, 77), ha="center", va="center", fontsize=9.5, color=ink,
                arrowprops={"arrowstyle": "-", "color": muted, "lw": 0.8})
    for i, label_y in ((5, 63.0), (6, 68.0)):
        ax.annotate(f"{values[i]:+.2f}", xy=(i, totals[i]), xytext=(i, label_y),
                    ha="center", va="center", fontsize=9.5, color=ink,
                    arrowprops={"arrowstyle": "-", "color": muted, "lw": 0.8})
    ax.text(7, totals[7] + 1.3, "54.00", ha="center", va="bottom",
            fontsize=11.5, fontweight="bold", color=ink)

    ax.set_xticks(x, labels, fontsize=9.1, color=ink)
    ax.tick_params(axis="x", length=0, pad=11)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.tick_params(axis="y", labelsize=9.5, colors=ink, length=0)
    ax.set_ylabel("OCV doses (millions)", fontsize=10.5, color=ink, labelpad=10)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#a8b2b9")

    fig.suptitle("Reconciliation of requested and approved OCV doses",
                 x=0.07, y=0.975, ha="left", fontsize=15, fontweight="bold", color=ink)
    fig.text(0.07, 0.925, "Reconstructed request records, January 2014–December 2019",
             ha="left", fontsize=10, color=muted)
    fig.text(0.07, 0.058,
             "Based on 88 dated request records, including one separately published South Sudan record. "
             "Totals use unrounded doses.\n"
             "Malawi: one request record has no logged requested-dose quantity but has 676,000 approved doses.",
             ha="left", va="center", fontsize=8.6, color=muted, linespacing=1.5)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.84, bottom=0.20)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    stages = build_stages(pd.read_csv(args.requests, keep_default_na=False))
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    stages.to_csv(args.csv, index=False)
    plot(stages, args.png)
    print(stages.to_string(index=False))
    print(f"PNG: {args.png}")
    print(f"CSV: {args.csv}")


if __name__ == "__main__":
    main()
