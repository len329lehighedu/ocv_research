#!/usr/bin/env python3
"""Draw both coefficients for all 25 country omissions from saved results.
Manuscript: Results 3.4; Figure S1.
Use a common axis scale; dashed lines show the full-sample estimates."""

from pathlib import Path
import argparse
import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ocv-loco-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_loco import COUNTRIES, require


HERE = Path(__file__).resolve().parent


def main():
    """Read inputs, run this script and save its outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE / "outputs")
    args = parser.parse_args()
    results = pd.read_csv(args.output_dir / "loco_coefficients.csv")
    omitted = results.loc[results.omitted_country.ne("None (full sample)")]
    require(len(omitted) == 50, "Expected 50 omitted-country coefficients")
    require(set(omitted.omitted_country) == set(COUNTRIES), "Plot would omit a country")
    plt.rcParams.update({"font.family": "Arial", "font.size": 10,
                         "axes.labelcolor": "#303030", "axes.edgecolor": "#303030",
                         "axes.linewidth": 0.8, "xtick.color": "#303030",
                         "ytick.color": "#303030", "xtick.major.width": 0.8,
                         "xtick.major.size": 3, "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 8.5), sharey=True, sharex=True)
    fig.subplots_adjust(left=0.17, right=0.95, bottom=0.11, top=0.95, wspace=0.16)
    y = np.arange(len(COUNTRIES))
    ethiopia_row = COUNTRIES.index("Ethiopia")
    low = min(0, omitted.ci95_low_asymptotic.min())
    high = max(0, omitted.ci95_high_asymptotic.max())
    margin = (high - low) * 0.07
    for ax, component, color in zip(axes, ("between", "within"), ("#3b6f94", "#c75b35")):
        data = omitted.loc[omitted.component.eq(component)].set_index("omitted_country").loc[list(COUNTRIES)]
        require(data.index.is_unique and len(data) == 25, "Repeated/missing plotted row")
        base = results.loc[results.omitted_country.eq("None (full sample)")
                           & results.component.eq(component)].iloc[0]
        ax.axhspan(ethiopia_row - 0.45, ethiopia_row + 0.45, color="#f1f1f1", zorder=0)
        ax.axvline(0, color="#aeb6bd", lw=0.8, zorder=0)
        ax.axvline(base.coefficient_log_odds, color="#7b8389", ls="--", lw=1.1)
        ax.hlines(y, data.ci95_low_asymptotic, data.ci95_high_asymptotic, color=color, lw=1.35)
        ax.scatter(data.coefficient_log_odds, y, s=30, color=color, zorder=3)
        ax.text(0, 1.02, "A" if component == "between" else "B",
                transform=ax.transAxes, ha="left", va="bottom", weight="bold", fontsize=13)
        ax.set_xlabel("Log-odds coefficient", labelpad=14, fontsize=10)
        ax.set_yticks(y, COUNTRIES)
        ax.tick_params(axis="y", length=0, pad=8)
        ax.grid(axis="x", color="#e9e9e9", lw=0.45)
        ax.set_axisbelow(True)
        ax.set_ylim(24.8, -0.8)
        # Both components use the same coefficient units AND displayed limits.
        ax.set_xlim(low - margin, high + margin)
    axes[0].get_yticklabels()[ethiopia_row].set_weight("bold")
    fig.savefig(args.output_dir / "loco_coefficients.png", dpi=300)
    fig.savefig(args.output_dir / "loco_coefficients.pdf")
    plt.close(fig)
    print("Saved PNG (300 dpi) and PDF; both components contain all 25 country omissions.")


if __name__ == "__main__":
    main()
