"""Robustness coefficient plot in the supplied three-column, eight-row layout.

Uses the seeded active-outbreak results. Estimates and asymptotic CIs are
multiplied by the full 25-country predictor-component SD for each lag window.
The reference SD is held fixed across samples and outcomes, not re-estimated
after country exclusions. Between and within components retain separate SDs.
Bootstrap p-values remain in the results table, not in the plotted whiskers.
"""

from __future__ import annotations

import argparse
import csv
import os
import math
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ocv-active-mpl"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUTCOMES = ("reactive_request", "request_this_month")
LAGS = (1, 3, 6, 12)
SAMPLES = (25, 23, 22)
COMPONENTS = ("between", "within")
COMPONENT_STYLES = {
    "between": ("#28648a", 0.38, "Between"),
    "within": ("#d66035", -0.38, "Within"),
}


def read_results(path: Path) -> dict[tuple[str, str, int, int], dict[str, float]]:
    results = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            outcome = raw["outcome"]
            component = raw["component"]
            lag = int(raw["lookback_months"])
            sample = int(raw["countries"])
            if outcome not in OUTCOMES or component not in COMPONENTS:
                raise ValueError(f"Unexpected outcome/component: {outcome}/{component}")
            if lag not in LAGS or sample not in SAMPLES:
                raise ValueError(f"Unexpected lag/sample: {lag}/{sample}")
            key = (outcome, component, lag, sample)
            if key in results:
                raise ValueError(f"Duplicate estimate: {key}")
            sd = float(raw["component_sd"])
            if sd <= 0:
                raise ValueError(f"Nonpositive component SD: {key}")
            beta = float(raw["coefficient_log_odds"])
            low = float(raw["ci95_low_asymptotic"])
            high = float(raw["ci95_high_asymptotic"])
            if not low <= beta <= high:
                raise ValueError(f"CI does not contain estimate: {key}")
            if not all(math.isfinite(v) for v in (sd, beta, low, high)):
                raise ValueError(f"Nonfinite estimate or SD: {key}")
            results[key] = {
                "beta": beta,
                "low": low,
                "high": high,
                "original_sample_sd": sd,
                "bootstrap_p": float(raw["p_wclr_c_rademacher"]),
            }
    expected = {
        (outcome, component, lag, sample)
        for outcome in OUTCOMES
        for component in COMPONENTS
        for lag in LAGS
        for sample in SAMPLES
    }
    if set(results) != expected:
        raise ValueError(f"Expected 48 estimates; missing={expected - set(results)}")
    for component in COMPONENTS:
        for lag in LAGS:
            reference_sd = results[(OUTCOMES[0], component, lag, 25)]["original_sample_sd"]
            other_sd = results[(OUTCOMES[1], component, lag, 25)]["original_sample_sd"]
            if not math.isclose(reference_sd, other_sd, rel_tol=1e-10):
                raise ValueError(f"Outcome-specific reference SD differs: {component}/{lag}")
            for outcome in OUTCOMES:
                for sample in SAMPLES:
                    value = results[(outcome, component, lag, sample)]
                    value["reference_sd_25"] = reference_sd
                    for field in ("beta", "low", "high"):
                        value[field] *= reference_sd
    return results


def draw(results: dict, output: Path) -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "xtick.labelsize": 9,
        "ytick.labelsize": 10,
        "savefig.dpi": 300,
    })
    fig, axes = plt.subplots(8, 3, figsize=(12.4, 13.4), sharex=True, sharey=True)

    lows = [value["low"] for value in results.values()]
    highs = [value["high"] for value in results.values()]
    span = max(highs) - min(lows)
    x_limits = (min(lows) - 0.07 * span, max(highs) + 0.07 * span)

    for outcome_index, outcome in enumerate(OUTCOMES):
        for lag_index, lag in enumerate(LAGS):
            row_index = outcome_index * len(LAGS) + lag_index
            for sample_index, sample in enumerate(SAMPLES):
                ax = axes[row_index, sample_index]
                ax.axvline(0, color="#687a86", linestyle="--", linewidth=1, zorder=1)
                ax.grid(axis="x", color="#dfe6ea", linewidth=0.8, zorder=0)
                for component, (color, y, _) in COMPONENT_STYLES.items():
                    value = results[(outcome, component, lag, sample)]
                    ax.errorbar(
                        value["beta"], y,
                        xerr=[[value["beta"] - value["low"]],
                              [value["high"] - value["beta"]]],
                        fmt="o", color=color, ecolor=color, markersize=5.2,
                        capsize=2.7, elinewidth=1.45, markeredgewidth=0.7,
                        zorder=3,
                    )
                ax.set_xlim(*x_limits)
                ax.set_ylim(-1.05, 1.05)
                ax.set_yticks([])
                ax.spines[["top", "left", "right"]].set_visible(False)
                ax.spines["bottom"].set_color("#6c7e89")
                ax.tick_params(axis="x", length=3, color="#687a86")
                if sample_index == 0:
                    ax.set_ylabel(f"{lag}m", rotation=0, labelpad=31,
                                  va="center", weight="medium")
                if row_index == 0:
                    ax.set_title(f"{sample} countries", weight="semibold", pad=11)
                if row_index != 7:
                    ax.tick_params(axis="x", labelbottom=False)

    handles = [
        Line2D([0], [0], color=color, marker="o", linewidth=1.5,
               markersize=6, label=label)
        for color, _, label in COMPONENT_STYLES.values()
    ]
    fig.suptitle("Recorded outbreak activity and OCV requests",
                 fontsize=16, weight="semibold", y=0.989)
    fig.text(0.5, 0.957,
             "Common 25-country reference SDs; whiskers are 95% asymptotic country-clustered CIs",
             ha="center", fontsize=9.7, color="#536b7b")
    fig.legend(handles=handles, loc="upper center", ncol=2,
               bbox_to_anchor=(0.5, 0.936), frameon=False,
               handlelength=2.0, columnspacing=2.6)
    fig.text(0.025, 0.678, "A  Reactive requests (primary)",
             rotation=90, va="center", ha="center", fontsize=11.5,
             weight="semibold")
    fig.text(0.025, 0.329, "B  All requests (secondary)",
             rotation=90, va="center", ha="center", fontsize=11.5,
             weight="semibold")
    fig.supxlabel("Log-odds coefficient per 1 reference SD (full 25-country sample)", y=0.082,
                 fontsize=10.5)
    fig.text(0.13, 0.052,
             "23 countries: excludes DR Congo and South Sudan. 22 countries: also excludes Nigeria.",
             fontsize=8.8, color="#536b7b")
    fig.text(0.13, 0.038,
             "Reference SDs vary by window and component, but are fixed across all three samples and both outcomes (July 2014–December 2019).",
             fontsize=8.5, color="#536b7b")
    fig.text(0.13, 0.024,
             "Wild-cluster-bootstrap p-values are reported separately; their significance thresholds may disagree with asymptotic CIs.",
             fontsize=8.8, color="#536b7b")
    fig.subplots_adjust(left=0.13, right=0.985, top=0.886,
                        bottom=0.135, hspace=0.24, wspace=0.18)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, facecolor="white", dpi=300)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path,
        default=Path(__file__).resolve().parents[3] / "outputs" / "analysis_data"
        / "active_outbreak_results_seeded.csv",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[3] / "outputs" / "figures"
        / "robustness_coefficient_plot_sample_layout.png",
    )
    args = parser.parse_args()
    results = read_results(args.results)
    draw(results, args.output)
    print(f"Plotted {len(results)} estimates from {args.results}")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
