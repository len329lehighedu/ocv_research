"""Draw covariate-adjusted coefficients beside the saved main estimates.
Manuscript: Results 3.5.1; Figure S2.
Whiskers are coefficient CIs, not CIs for changes from the main model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ocv-sensitivity-mpl"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
BETWEEN = "log1p_active_outbreak_months_12m_between"
WITHIN = "log1p_active_outbreak_months_12m_within"
COMPONENTS = {"between": (BETWEEN, "#3b6f94"), "within": (WITHIN, "#c75b35")}


def sha(path: Path) -> str:
    """Return the file SHA-256 used to detect input changes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_estimates():
    """Read saved main and adjusted coefficients with their original CIs."""
    source = {
        "main": ROOT / "analysis/main/outputs/analysis_data/active_outbreak_results_seeded.csv",
        "income": ROOT / "analysis/covariates/income/income_sensitivity_results.json",
        "expenditure": ROOT / "analysis/covariates/expenditure/ihme_2013/ihme_expenditure_sensitivity_results.json",
        "prior": ROOT / "analysis/covariates/prior_campaign/prior_campaign_sensitivity_results.json",
    }
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in source.values()}
    with source["main"].open(newline="", encoding="utf-8-sig") as f:
        main_rows = [r for r in csv.DictReader(f) if r["outcome"] == "reactive_request"
                     and int(r["lookback_months"]) == 12 and int(r["countries"]) == 25]
    assert len(main_rows) == 2 and {r["component"] for r in main_rows} == set(COMPONENTS)
    main = {}
    for r in main_rows:
        assert int(r["country_months"]) == 1650 and int(r["event_months"]) == 58
        main[r["component"]] = {
            "coefficient_log_odds": float(r["coefficient_log_odds"]),
            "ci95_log_odds_cluster_asymptotic": [float(r["ci95_low_asymptotic"]), float(r["ci95_high_asymptotic"])],
            "p_wclr_c_rademacher": float(r["p_wclr_c_rademacher"]),
        }
    income = json.loads(source["income"].read_text())
    exp = json.loads(source["expenditure"].read_text())
    prior = json.loads(source["prior"].read_text())
    for obj in (income, exp, prior):
        assert obj["n_countries"] == 25 and obj["n_country_months"] == 1650
        assert obj["n_reactive_event_months"] == 58
    # Fail rather than accidentally plot the archived six-country coding.
    assert prior["diagnostics"]["ledger"]["positive_count"] == 7
    assert "DR Congo" in prior["diagnostics"]["ledger"]["positive_countries"]
    definitions = [
        ("main", "Main model", "Main", main),
        ("income", "+ Income group (FY2015)", "Income", income["coefficients"]),
        ("government", "+ Government expenditure (2013)", "Expenditure", exp["models"]["government"]["coefficients"]),
        ("total", "+ Total expenditure (2013)", "Expenditure", exp["models"]["total"]["coefficients"]),
        ("prior", "+ Documented prior OCV campaign", "Prior campaign", prior["coefficients"]),
    ]
    data = []
    for order, (key, label, family, estimates) in enumerate(definitions):
        for component, (term, _) in COMPONENTS.items():
            value = estimates[component if key == "main" else term]
            beta = value["coefficient_log_odds"]
            low, high = value["ci95_log_odds_cluster_asymptotic"]
            assert low <= beta <= high
            data.append({
                "model_order": order, "model": key, "label": label, "covariate_group": family,
                "component": component, "coefficient_log_odds": beta,
                "ci95_low_asymptotic": low, "ci95_high_asymptotic": high,
                "p_wclr_c_rademacher": value["p_wclr_c_rademacher"],
                "change_from_main_point_estimate": beta - main[component]["coefficient_log_odds"],
                "countries": 25, "country_months": 1650, "reactive_event_months": 58,
                "lookback_months": 12, "scale": "per one unit of corresponding log predictor component",
            })
    return data, source_hashes, source


def draw(data, output: Path):
    """Plot aligned model labels and coefficient intervals; keep panel-specific axis ranges."""
    plt.rcParams.update({"font.family": "Arial", "font.size": 10.5,
                         "axes.labelcolor": "#303030", "axes.edgecolor": "#303030",
                         "axes.linewidth": 0.8, "xtick.color": "#303030",
                         "ytick.color": "#303030", "xtick.major.width": 0.8,
                         "xtick.major.size": 3, "xtick.labelsize": 10,
                         "svg.fonttype": "none"})
    fig = plt.figure(figsize=(12, 5.6), facecolor="white")
    grid = fig.add_gridspec(1, 3, left=.10, right=.985, bottom=.17, top=.84,
                           width_ratios=[.68, 1, 1], wspace=.14)
    label_axis = fig.add_subplot(grid[0, 0])
    label_axis.set_ylim(-.55, 4.65)
    label_axis.set_axis_off()
    row_labels = []
    for row in [r for r in data if r["component"] == "between"]:
        row_labels.append(label_axis.text(
            0, 4 - row["model_order"], row["label"],
            transform=label_axis.get_yaxis_transform(), ha="left", va="center",
            weight="semibold" if row["model"] == "main" else "normal",
        ))
    plot_axes = [fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[0, 2])]
    for i, (component, (_, color)) in enumerate(COMPONENTS.items()):
        ax = plot_axes[i]
        rows = [r for r in data if r["component"] == component]
        base = rows[0]["coefficient_log_odds"]
        ax.axhspan(3.65, 4.35, color="#f1f1f1", zorder=0)
        ax.axvline(0, color="#aeb6bd", linewidth=0.8, zorder=1)
        ax.axvline(base, color=color, linestyle=(0, (4, 3)), linewidth=1.1, alpha=.9, zorder=2)
        ax.grid(axis="x", color="#e9e9e9", linewidth=.45)
        ax.set_axisbelow(True)
        for row in rows:
            y = 4 - row["model_order"]
            beta, low, high = (row[k] for k in ("coefficient_log_odds", "ci95_low_asymptotic", "ci95_high_asymptotic"))
            ax.errorbar(beta, y, xerr=[[beta - low], [high - beta]],
                        fmt="D" if row["model"] == "main" else "o", color=color,
                        markersize=6.7 if row["model"] == "main" else 5.7,
                        elinewidth=1.35, capsize=3, markeredgewidth=0.8, zorder=3)
        ax.set_ylim(-.55, 4.65)
        ax.set_yticks([])
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.text(0, 1.025, "A" if i == 0 else "B", transform=ax.transAxes,
                ha="left", va="bottom", weight="semibold", fontsize=12)
        ax.set_xlabel("Log-odds coefficient", labelpad=14)
        ax.set_xlim((-.025, .78) if i == 0 else (-.32, .37))
        ax.set_xticks([0, .2, .4, .6] if i == 0 else [-.3, -.2, -.1, 0, .1, .2, .3])
    legend = [
        Line2D([0], [0], marker="D", color="#7b8389", linestyle="none", markersize=6.7, label="Main model"),
        Line2D([0], [0], marker="o", color="#7b8389", linestyle="none", markersize=5.7, label="One covariate added separately"),
        Line2D([0], [0], color="#7b8389", linestyle="--", linewidth=1.1, label="Main coefficient reference"),
    ]
    legend_center = (plot_axes[0].get_position().x0 + plot_axes[1].get_position().x1) / 2
    fig.legend(handles=legend, loc="upper center", bbox_to_anchor=(legend_center, .995),
               frameon=False, ncol=3, fontsize=9.8, columnspacing=2.0, handlelength=2)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    legend_box = fig.legends[0].get_window_extent(renderer)
    label_column = label_axis.get_window_extent(renderer)
    for label in row_labels:
        assert label.get_window_extent(renderer).x1 <= label_column.x1, "Row label exceeds its column"
    for ax in plot_axes:
        assert not legend_box.overlaps(ax.get_window_extent(renderer)), "Legend/plot overlap"
    fig.savefig(output / "covariate_sensitivity_coefficient_plot.png", dpi=300, facecolor="white")
    fig.savefig(output / "covariate_sensitivity_coefficient_plot.svg", facecolor="white")
    plt.close(fig)


def main():
    """Read inputs, run this script and save its outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis/figures/covariate_sensitivity")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data, hashes, source = load_estimates()
    with (args.output_dir / "covariate_sensitivity_plot_data.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
    draw(data, args.output_dir)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in source.values()}, "Input changed during plotting"
    provenance = {"source_sha256": hashes, "script_sha256": sha(Path(__file__)),
                  "model_count": 5, "plotted_estimate_count": 10,
                  "corrected_prior_positive_country_count": 7,
                  "models_refitted": False, "dpi": 300, "figsize_inches": [12, 5.6]}
    (args.output_dir / "plot_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (args.output_dir / "caption.md").write_text(
        "Baseline-covariate sensitivity of between- and within-country associations with reactive OCV request-months. "
        "Each model contains both components of logged recorded outbreak activity in the preceding 12 months. "
        "Diamonds show the primary model estimates; circles show estimates after adding one country-level baseline covariate separately. "
        "Government and total health expenditure are alternative models, not jointly entered covariates. "
        "All models use the same 25 countries and 1,650 country-months, including 58 reactive request-months. "
        "The prior-campaign model uses the corrected seven-country documented-history indicator, including Kalemie, DR Congo, in November 2013. "
        "Coefficients are per one-unit increase in the relevant log-transformed predictor component, not per standard deviation. "
        "Whiskers are asymptotic 95% confidence intervals based on country-clustered standard errors. "
        "Dashed colored lines mark the corresponding primary coefficient; the gray vertical line marks zero. "
        "Panel x-axis ranges differ. "
        "Wild-cluster-bootstrap p-values are reported separately in the sensitivity table.\n",
        encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "estimates": data}, indent=2))


if __name__ == "__main__":
    main()
