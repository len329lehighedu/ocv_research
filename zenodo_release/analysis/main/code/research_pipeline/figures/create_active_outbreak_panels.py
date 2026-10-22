#!/usr/bin/env python3
"""Draw Figure 3A/B for the recorded active outbreak-months predictor.

Panel A shows 25 country means, with display-only offsets for coincident
circles. Panel B uses six tied-preserving negative quantile groups, one group
for exactly zero within-country deviation, and three tied-preserving positive
quantile groups. These are ordered groups, not ten equal-sized deciles.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ocv-active-mpl"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FIGSIZE = (9.0, 5.9)
DPI = 300
MARGINS = dict(left=0.125, right=0.87, bottom=0.325, top=0.83)
Y_LIM = (-0.55, 16.0)
Y_TICKS = (0, 4, 8, 12, 16)
BLUE = "#245f86"
ORANGE = "#cf5c35"
BASELINE = "#73808a"
GRID = "#e2e7eb"
NOTE = "#526777"
LEADER = "#693c87"
STEM = "log1p_active_outbreak_months_12m"


def separate_x(values: np.ndarray, gap: float) -> np.ndarray:
    """Order-preserving least-squares offsets with minimum visual spacing."""
    blocks: list[list[float | int]] = []
    for value in values - np.arange(len(values)) * gap:
        blocks.append([float(value), 1])
        while len(blocks) > 1 and float(blocks[-2][0]) > float(blocks[-1][0]):
            right, left = blocks.pop(), blocks.pop()
            count = int(left[1]) + int(right[1])
            blocks.append([
                (float(left[0]) * int(left[1]) + float(right[0]) * int(right[1])) / count,
                count,
            ])
    centers = np.concatenate([
        np.repeat(max(0.0, float(value)), int(count)) for value, count in blocks
    ])
    return centers + np.arange(len(values)) * gap


def base_figure(title: str):
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.subplots_adjust(**MARGINS)
    ax.set_ylim(*Y_LIM)
    ax.set_yticks(Y_TICKS)
    ax.tick_params(axis="both", labelsize=10)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.spines["top"].set_visible(False)
    ax.set_title(title, loc="left", fontweight="bold", fontsize=15, pad=31)
    fig.text(
        MARGINS["left"], 0.855,
        "25 countries; 1,650 country-months; 58 reactive event-months",
        fontsize=10, color=NOTE, zorder=20,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.25},
    )
    return fig, ax


def draw_a(data: pd.DataFrame, figure_dir: Path, data_dir: Path):
    summary = data.groupby("country", as_index=False).agg(
        mean_log1p_active_outbreak_months_12m=(STEM, "mean"),
        reactive_event_months=("reactive_request", "sum"),
        observed_months=("reactive_request", "size"),
    )
    summary["reactive_request_month_share_pct"] = (
        100 * summary.reactive_event_months / summary.observed_months
    )
    assert len(summary) == 25 and summary.reactive_event_months.sum() == 58
    assert summary.observed_months.eq(66).all()
    x = summary.mean_log1p_active_outbreak_months_12m.to_numpy()
    y = summary.reactive_request_month_share_pct.to_numpy()
    slope, intercept = np.polyfit(x, y, 1)

    fig, ax = base_figure("A  Between-country differences")
    ax.set_xlim(-0.12, 4.35)
    ax.set_xticks(np.arange(0, 4.1, 1))
    ax.set_xlabel(
        "Country mean of ln(1 + active outbreak-months in preceding 12 months)",
        fontsize=11, labelpad=10,
    )
    ax.set_ylabel("Months with ≥1 reactive OCV request (% per country)", fontsize=11, labelpad=10)
    right = ax.secondary_yaxis(
        "right", functions=(lambda pct: pct * 66 / 100, lambda months: months * 100 / 66)
    )
    right.set_ylabel("Months with ≥1 reactive OCV request (of 66)", fontsize=11, labelpad=12)
    right.set_yticks(np.arange(0, 11))
    right.tick_params(labelsize=10)

    fig.canvas.draw()
    marker_area, edge_width = 40, 1.3
    marker_diameter = (np.sqrt(marker_area) + edge_width) * DPI / 72
    gap_pixels = (np.sqrt(marker_area) + edge_width + 3) * DPI / 72
    gap_data = gap_pixels * np.diff(ax.get_xlim())[0] / ax.bbox.width
    summary["display_x"] = summary.mean_log1p_active_outbreak_months_12m
    for _, group in summary.groupby("reactive_event_months"):
        ordered = group.sort_values(["mean_log1p_active_outbreak_months_12m", "country"])
        summary.loc[ordered.index, "display_x"] = separate_x(
            ordered.mean_log1p_active_outbreak_months_12m.to_numpy(), gap_data
        )
    summary["display_x_offset"] = (
        summary.display_x - summary.mean_log1p_active_outbreak_months_12m
    )
    moved = summary.display_x_offset.abs().gt(1e-10)
    for row in summary.loc[moved].itertuples():
        ax.plot(
            [row.mean_log1p_active_outbreak_months_12m, row.display_x],
            [row.reactive_request_month_share_pct] * 2,
            color=LEADER, linewidth=2.1, linestyle=(0, (2.0, 1.1)), zorder=3,
        )
        ax.scatter(
            [row.mean_log1p_active_outbreak_months_12m],
            [row.reactive_request_month_share_pct], marker="|", s=38,
            color=LEADER, linewidths=1.6, zorder=3,
        )
    grid = np.linspace(x.min(), x.max(), 300)
    ax.plot(grid, intercept + slope * grid, color=ORANGE, linewidth=1.8,
            label="Descriptive fit (original x values)", zorder=2)
    overall = 100 * data.reactive_request.mean()
    ax.axhline(overall, color=BASELINE, linewidth=1, linestyle="--",
               label=f"Overall rate: {overall:.2f}% (58/1,650)", zorder=1)
    ax.scatter(summary.display_x, y, s=marker_area, facecolors="white",
               edgecolors=BLUE, linewidths=edge_width, zorder=4)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    fig.text(
        MARGINS["left"], 0.092,
        "Each circle represents one country. Small horizontal offsets separate overlapping circles;\n"
        "y values and the fit use original x. Each country contributes 66 months.\n"
        "Lines are descriptive; model-based inference is reported in the main text.",
        fontsize=8.4, color=NOTE, linespacing=1.35,
    )
    fig.canvas.draw()
    pixels = ax.transData.transform(
        summary[["display_x", "reactive_request_month_share_pct"]].to_numpy()
    )
    distances = np.linalg.norm(pixels[:, None, :] - pixels[None, :, :], axis=2)
    np.fill_diagonal(distances, np.inf)
    if distances.min() <= marker_diameter or summary.display_x.min() < 0:
        raise ValueError("Panel A circles overlap or a display x is below zero")
    summary["descriptive_fit_pct_at_original_x"] = intercept + slope * x
    summary["leader_drawn"] = moved
    bounds = tuple(float(v) for v in ax.bbox.bounds)
    fig.savefig(figure_dir / "panel_a.png", facecolor="white")
    plt.close(fig)
    summary.to_csv(data_dir / "panel_a_data.csv", index=False, float_format="%.12g")
    return summary, bounds, (float(slope), float(intercept))


def make_groups(data: pd.DataFrame) -> pd.DataFrame:
    grouped = data.copy()
    deviation = grouped[f"{STEM}_within"]
    negative = deviation.lt(0)
    positive = deviation.gt(0)
    zero = deviation.eq(0)
    if not (negative | positive | zero).all() or int(zero.sum()) != 264:
        raise ValueError("Unexpected within-deviation distribution")
    grouped["ordered_group"] = 0
    grouped.loc[negative, "ordered_group"] = (
        pd.qcut(deviation[negative], 6, labels=False, duplicates="raise").astype(int) + 1
    )
    grouped.loc[zero, "ordered_group"] = 7
    grouped.loc[positive, "ordered_group"] = (
        pd.qcut(deviation[positive], 3, labels=False, duplicates="raise").astype(int) + 8
    )
    if set(grouped.ordered_group) != set(range(1, 11)):
        raise ValueError("Expected ten ordered groups without splitting ties")
    return grouped


def draw_b(data: pd.DataFrame, figure_dir: Path, data_dir: Path):
    grouped = make_groups(data)
    overall = float(grouped.reactive_request.mean())
    grouped["country_request_mean"] = grouped.groupby("country").reactive_request.transform("mean")
    grouped["adjusted_outcome_pct"] = 100 * (
        grouped.reactive_request - grouped.country_request_mean + overall
    )
    summary = grouped.groupby("ordered_group", as_index=False).agg(
        n_country_months=("reactive_request", "size"),
        reactive_event_months=("reactive_request", "sum"),
        n_countries=("country", "nunique"),
        minimum_within_deviation=(f"{STEM}_within", "min"),
        mean_within_deviation=(f"{STEM}_within", "mean"),
        maximum_within_deviation=(f"{STEM}_within", "max"),
        adjusted_rate_pct=("adjusted_outcome_pct", "mean"),
        mean_country_baseline=("country_request_mean", "mean"),
    )
    summary["raw_rate_pct"] = 100 * summary.reactive_event_months / summary.n_country_months
    ranks = summary.ordered_group.to_numpy()
    rates = summary.adjusted_rate_pct.to_numpy()
    counts = summary.n_country_months.to_numpy()
    slope, intercept = np.polyfit(ranks, rates, 1, w=np.sqrt(counts))
    summary["weighted_fit_pct"] = intercept + slope * ranks
    weighted_rate = float(np.average(rates, weights=counts))
    if (
        len(summary) != 10 or counts.sum() != 1650
        or summary.reactive_event_months.sum() != 58
        or not np.isclose(weighted_rate, 100 * overall, atol=1e-10)
    ):
        raise ValueError("Panel B totals do not reconcile")
    if summary.loc[summary.ordered_group.eq(7), "n_country_months"].iloc[0] != 264:
        raise ValueError("Exactly-zero group must contain 264 country-months")
    if not np.isclose(summary.loc[summary.ordered_group.eq(7), "adjusted_rate_pct"].iloc[0],
                      100 * overall, atol=1e-10):
        raise ValueError("Exactly-zero group should equal the overall rate")

    fig, ax = base_figure("B  Within-country deviations")
    ax.set_xlim(0.5, 10.5)
    ax.set_xticks(ranks, [f"{int(rank)}\nn={int(size)}" for rank, size in zip(ranks, counts)])
    ax.set_xlabel(
        "Ordered group of within-country deviation in ln(1 + 12-month active outbreak-months)",
        fontsize=11, labelpad=10,
    )
    ax.set_ylabel("Country-adjusted request outcome (×100)",
                  fontsize=11, labelpad=10)
    ax.scatter(ranks, rates, s=40, color=BLUE, edgecolor="white", linewidth=0.6, zorder=4)
    ax.plot(ranks, summary.weighted_fit_pct, color=ORANGE, linewidth=1.8,
            label="Descriptive fit (weighted by group size)", zorder=3)
    ax.axhline(100 * overall, color=BASELINE, linewidth=1, linestyle="--",
               label=f"Overall rate: {100 * overall:.2f}% (58/1,650)", zorder=1)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    fig.text(
        MARGINS["left"], 0.092,
        "Adjusted outcome = 100 × (monthly indicator − country mean + overall mean).\n"
        "Six negative quantile groups, an exact-zero group (7), then three positive quantile groups; ties stay together.\n"
        "Group 7 contains 264 months from four countries and equals the overall rate by construction.\n"
        "Adjusted rates need not equal raw proportions. Lines are descriptive; model-based inference is in the text.",
        fontsize=7.8, color=NOTE, linespacing=1.28,
    )
    fig.canvas.draw()
    bounds = tuple(float(v) for v in ax.bbox.bounds)
    fig.savefig(figure_dir / "panel_b.png", facecolor="white")
    plt.close(fig)
    summary.to_csv(data_dir / "panel_b_data.csv", index=False, float_format="%.12g")
    grouped.to_csv(data_dir / "panel_b_month_data.csv", index=False, float_format="%.12g")
    return summary, bounds, (float(slope), float(intercept)), weighted_rate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    data = pd.read_csv(args.panel)
    if data.duplicated(["country", "yearmonth"]).any():
        raise ValueError("Duplicate country-months")
    if len(data) != 1650 or data.country.nunique() != 25:
        raise ValueError("Expected 25 countries x 66 months")
    if not data.groupby("country").size().eq(66).all():
        raise ValueError("Expected 66 months per country")
    if int(data.reactive_request.sum()) != 58:
        raise ValueError("Expected 58 reactive event-months")
    expected = data.groupby("country")[STEM].transform("mean")
    if not np.allclose(data[f"{STEM}_between"], expected):
        raise ValueError("Between-country values do not match country means")
    if not np.allclose(data[f"{STEM}_within"], data[STEM] - expected):
        raise ValueError("Within-country values do not match deviations")
    args.figure_dir.mkdir(parents=True, exist_ok=True)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    a, a_bounds, a_fit = draw_a(data, args.figure_dir, args.data_dir)
    b, b_bounds, b_fit, weighted = draw_b(data, args.figure_dir, args.data_dir)
    if not np.allclose(a_bounds, b_bounds, atol=1e-9, rtol=0):
        raise ValueError("Panel plotting areas are not aligned")
    print(f"Panel A: {len(a)} circles; Σ reactive months={int(a.reactive_event_months.sum())}")
    print(f"Panel B: {len(b)} groups; Σn={int(b.n_country_months.sum())}; "
          f"Σ events={int(b.reactive_event_months.sum())}; weighted mean={weighted:.6f}%")
    print(f"Panel A descriptive fit: slope={a_fit[0]:.6f}, intercept={a_fit[1]:.6f}")
    print(f"Panel B descriptive fit: slope={b_fit[0]:.6f} pp/group, intercept={b_fit[1]:.6f}")
    print(f"Aligned plot bounds: {a_bounds}")


if __name__ == "__main__":
    main()
