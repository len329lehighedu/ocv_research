"""Plot baseline-covariate sensitivities against the frozen primary model.

Uses saved estimates only; no models or bootstrap tests are rerun. Whiskers
are the original cluster-asymptotic CIs, not CIs for coefficient differences.
"""

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
COMPONENTS = {"between": (BETWEEN, "#28648a"), "within": (WITHIN, "#d66035")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_estimates():
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
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5,
                         "axes.titlesize": 12, "xtick.labelsize": 10, "svg.fonttype": "none"})
    fig = plt.figure(figsize=(14, 7.2), facecolor="white")
    grid = fig.add_gridspec(1, 4, width_ratios=[1, .17, 1, .17],
                           left=.27, right=.96, bottom=.23, top=.69, wspace=.12)
    plot_axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 2])]
    delta_axes = [fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[0, 3])]
    for i, (component, (_, color)) in enumerate(COMPONENTS.items()):
        ax, dx = plot_axes[i], delta_axes[i]
        rows = [r for r in data if r["component"] == component]
        base = rows[0]["coefficient_log_odds"]
        ax.axhspan(3.65, 4.35, color="#f0f3f5", zorder=0)
        ax.axvline(0, color="#a1aab1", linewidth=1.0, zorder=1)
        ax.axvline(base, color=color, linestyle=(0, (4, 3)), linewidth=1.35, alpha=.9, zorder=2)
        ax.grid(axis="x", color="#e3e8eb", linewidth=.75)
        ax.set_axisbelow(True)
        for row in rows:
            y = 4 - row["model_order"]
            beta, low, high = (row[k] for k in ("coefficient_log_odds", "ci95_low_asymptotic", "ci95_high_asymptotic"))
            ax.errorbar(beta, y, xerr=[[beta - low], [high - beta]],
                        fmt="D" if row["model"] == "main" else "o", color=color,
                        markersize=7.7 if row["model"] == "main" else 6.7,
                        elinewidth=1.75, capsize=3.5, markeredgewidth=1, zorder=3)
            dx.text(.5, y, "Reference" if row["model"] == "main" else f"{row['change_from_main_point_estimate']:+.4f}",
                    ha="center", va="center", fontsize=9.4, color="#364957")
        ax.set_ylim(-.55, 4.65)
        dx.set_ylim(ax.get_ylim())
        dx.set_xlim(0, 1)
        dx.axis("off")
        dx.text(.5, 4.92, "Change\nfrom main", ha="center", va="bottom", fontsize=9.3, color="#536b7b")
        ax.set_yticks(range(5))
        ax.set_yticklabels([r["label"] for r in rows[::-1]] if i == 0 else [])
        ax.tick_params(axis="y", length=0, pad=15)
        if i == 0:
            for tick in ax.get_yticklabels():
                if tick.get_text() == "Main model":
                    tick.set_weight("semibold")
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.spines["bottom"].set_color("#8899a4")
        ax.set_title(f"{'A' if i == 0 else 'B'}  {'Between-country' if i == 0 else 'Within-country'} component\nMain coefficient = {base:.3f}",
                     loc="left", weight="semibold", pad=15)
        ax.set_xlabel("Log-odds coefficient", labelpad=12)
        ax.set_xlim((-.025, .78) if i == 0 else (-.32, .37))
        ax.set_xticks([0, .2, .4, .6] if i == 0 else [-.3, -.2, -.1, 0, .1, .2, .3])
    fig.text(.035, .935, "Baseline-covariate sensitivity of outbreak-activity estimates",
             fontsize=17, weight="semibold", color="#243a48")
    fig.text(.035, .88, "Reactive OCV request-months; prior 12-month activity; 25 countries; 1,650 country-months; 58 events",
             fontsize=10.5, color="#536b7b")
    legend = [
        Line2D([0], [0], marker="D", color="#536b7b", linestyle="none", markersize=7, label="Main model"),
        Line2D([0], [0], marker="o", color="#536b7b", linestyle="none", markersize=6, label="One covariate added separately"),
        Line2D([0], [0], color="#536b7b", linestyle="--", linewidth=1.3, label="Main coefficient reference"),
    ]
    fig.legend(handles=legend, loc="upper left", bbox_to_anchor=(.028, .835),
               frameon=False, ncol=3, fontsize=9.8, columnspacing=2.0, handlelength=2)
    fig.text(.035, .105, "Whiskers: asymptotic 95% country-clustered confidence intervals. Bootstrap p-values are reported separately.",
             fontsize=9.2, color="#536b7b")
    fig.text(.035, .064, "Changes are point-estimate differences, not effects of covariates or statistical tests of coefficient differences. Panel x-axis ranges differ.",
             fontsize=9.0, color="#536b7b")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    legend_box = fig.legends[0].get_window_extent(renderer)
    for ax in plot_axes:
        assert not legend_box.overlaps(ax._left_title.get_window_extent(renderer)), "Legend/title overlap"
    fig.savefig(output / "covariate_sensitivity_coefficient_plot.png", dpi=300, facecolor="white")
    fig.savefig(output / "covariate_sensitivity_coefficient_plot.svg", facecolor="white")
    plt.close(fig)


def main():
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
                  "models_refitted": False, "dpi": 300, "figsize_inches": [14, 7.2]}
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
        "The change columns subtract the primary point estimate from each adjusted point estimate; they are not causal covariate effects "
        "or confidence intervals/tests for differences between models. Panel x-axis ranges differ. "
        "Wild-cluster-bootstrap p-values are reported separately in the sensitivity table.\n",
        encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "estimates": data}, indent=2))


if __name__ == "__main__":
    main()
