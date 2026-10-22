#!/usr/bin/env python3
"""Plot all 25 omissions without using p-value thresholds or rescaling."""

from pathlib import Path
import argparse
import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ocv-loco-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from run_loco import COUNTRIES, require


HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE / "outputs")
    args = parser.parse_args()
    results = pd.read_csv(args.output_dir / "loco_coefficients.csv")
    omitted = results.loc[results.omitted_country.ne("None (full sample)")]
    require(len(omitted) == 50, "Expected 50 omitted-country coefficients")
    require(set(omitted.omitted_country) == set(COUNTRIES), "Plot would omit a country")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 10.2), sharey=True, sharex=True)
    fig.subplots_adjust(left=0.18, right=0.97, bottom=0.13, top=0.84, wspace=0.16)
    y = np.arange(len(COUNTRIES))
    ethiopia_row = COUNTRIES.index("Ethiopia")
    low = min(0, omitted.ci95_low_asymptotic.min())
    high = max(0, omitted.ci95_high_asymptotic.max())
    margin = (high - low) * 0.07
    for ax, component, color in zip(axes, ("between", "within"), ("#24688c", "#ce7131")):
        data = omitted.loc[omitted.component.eq(component)].set_index("omitted_country").loc[list(COUNTRIES)]
        require(data.index.is_unique and len(data) == 25, "Repeated/missing plotted row")
        base = results.loc[results.omitted_country.eq("None (full sample)")
                           & results.component.eq(component)].iloc[0]
        ax.axhspan(ethiopia_row - 0.45, ethiopia_row + 0.45, color="#eef0f2", zorder=0)
        ax.axvline(0, color="#aeb6bd", lw=1, zorder=0)
        ax.axvline(base.coefficient_log_odds, color="#3e4952", ls="--", lw=1.4)
        ax.hlines(y, data.ci95_low_asymptotic, data.ci95_high_asymptotic, color=color, lw=1.5)
        ax.scatter(data.coefficient_log_odds, y, s=30, color=color, zorder=3)
        ax.set_title(f"{component.capitalize()}-country", loc="left", weight="bold", fontsize=13)
        ax.set_xlabel("Coefficient (log-odds per unit of logged component)", labelpad=12, fontsize=10)
        ax.set_yticks(y, COUNTRIES)
        ax.tick_params(axis="y", length=0, pad=8)
        ax.grid(axis="x", color="#e5e9ed", lw=0.7)
        ax.set_axisbelow(True)
        ax.set_ylim(24.8, -0.8)
        # Both components use the same coefficient units AND displayed limits.
        ax.set_xlim(low - margin, high + margin)
    axes[0].get_yticklabels()[ethiopia_row].set_weight("bold")
    fig.text(0.18, 0.94, "Leave-one-country-out sensitivity", fontsize=18, weight="bold")
    fig.text(0.18, 0.905, "Reactive OCV requests; preceding 12-month recorded outbreak activity",
             fontsize=12, color="#506372")
    fig.text(0.18, 0.875, "Each row omits one country: 24 countries and 1,584 country-months per model",
             fontsize=10.5, color="#506372")
    fig.legend(handles=[Line2D([0], [0], color="#3e4952", ls="--", label="Full 25-country estimate"),
                        Line2D([0], [0], color="#6e7c86", marker="o", lw=1.5,
                               label="Omission estimate and asymptotic country-clustered 95% CI")],
               loc="lower left", bbox_to_anchor=(0.175, 0.025), frameon=False, fontsize=10)
    fig.savefig(args.output_dir / "loco_coefficients.png", dpi=300)
    fig.savefig(args.output_dir / "loco_coefficients.pdf")
    plt.close(fig)
    print("Saved PNG (300 dpi) and PDF; both components contain all 25 country omissions.")


if __name__ == "__main__":
    main()
