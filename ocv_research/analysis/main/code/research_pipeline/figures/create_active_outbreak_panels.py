#!/usr/bin/env python3
"""Draw Figure 1, with country means in A and monthly deviations in B.
Manuscript: Results 3.2; output is one combined PNG/PDF plus separate panels.
Panel B shows a transformed outcome, not observed request probabilities."""

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


FIGSIZE = (7.2, 4.4)
DPI = 300
MARGINS = dict(left=0.15, right=0.855, bottom=0.23, top=0.91)
Y_LIM = (-0.55, 16.0)
Y_TICKS = (0, 4, 8, 12, 16)
BLUE = "#3b6f94"
ORANGE = "#c75b35"
BASELINE = "#7b8389"
GRID = "#e9e9e9"
LEADER = "#94a1aa"
STEM = "log1p_active_outbreak_months_12m"
STYLE = {
    "font.family": "Arial",
    "font.size": 9,
    "axes.labelsize": 9.5,
    "axes.labelcolor": "#303030",
    "axes.edgecolor": "#303030",
    "axes.linewidth": 0.8,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "xtick.color": "#303030",
    "ytick.color": "#303030",
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "pdf.fonttype": 42,
}


def separate_x(values: np.ndarray, gap: float) -> np.ndarray:
    """Separate coincident circles horizontally while preserving their order."""
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


def base_figure(panel_letter: str, fig_ax=None):
    """Set common axis styling and add the panel letter."""
    plt.rcParams.update(STYLE)
    if fig_ax is None:
        fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
        fig.subplots_adjust(**MARGINS)
    else:
        fig, ax = fig_ax
    ax.set_ylim(*Y_LIM)
    ax.set_yticks(Y_TICKS)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=0.45)
    ax.spines["top"].set_visible(False)
    ax.text(0, 1.04, panel_letter, transform=ax.transAxes,
            fontweight="bold", fontsize=12, ha="left", va="bottom")
    return fig, ax


def save_panel(fig, figure_dir: Path, name: str):
    """Save matching PNG and vector PDF artwork, then close the figure."""
    fig.savefig(figure_dir / f"{name}.png", facecolor="white", dpi=DPI)
    fig.savefig(figure_dir / f"{name}.pdf", facecolor="white")
    plt.close(fig)


def draw_a(data: pd.DataFrame, figure_dir: Path, data_dir: Path, *, fig_ax=None):
    """Plot country means and request shares; fit the original, unshifted x-values."""
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
    # Fit before moving coincident circles; offsets affect display only.
    slope, intercept = np.polyfit(x, y, 1)

    fig, ax = base_figure("A", fig_ax)
    ax.set_xlim(-0.12, 4.35)
    ax.set_xticks(np.arange(0, 4.1, 1))
    ax.set_xlabel(
        "Country mean of logged outbreak activity",
        labelpad=14,
    )
    ax.set_ylabel("Months with ≥1 reactive request (% per country)", labelpad=12)
    right = ax.secondary_yaxis(
        "right", functions=(lambda pct: pct * 66 / 100, lambda months: months * 100 / 66)
    )
    right.set_ylabel("Months with ≥1 reactive request", labelpad=12)
    right.set_yticks(np.arange(0, 11))
    right.tick_params(labelsize=9)

    fig.canvas.draw()
    marker_area, edge_width = 30, 0.9
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
            color=LEADER, linewidth=0.7, linestyle=(0, (2.0, 1.1)), zorder=3,
        )
        ax.scatter(
            [row.mean_log1p_active_outbreak_months_12m],
            [row.reactive_request_month_share_pct], marker="|", s=22,
            color=LEADER, linewidths=0.7, zorder=3,
        )
    grid = np.linspace(x.min(), x.max(), 300)
    ax.plot(grid, intercept + slope * grid, color=ORANGE, linewidth=1.35,
            label="Descriptive fit", zorder=2)
    overall = 100 * data.reactive_request.mean()
    ax.axhline(overall, color=BASELINE, linewidth=0.9, linestyle=(0, (4, 3)),
               label="Overall mean", zorder=1)
    ax.scatter(summary.display_x, y, s=marker_area, facecolors="white",
               edgecolors=BLUE, linewidths=edge_width, zorder=4)
    ax.legend(frameon=False, loc="upper left", fontsize=8.5, handlelength=2.4)
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
    if fig_ax is None:
        save_panel(fig, figure_dir, "panel_a")
        summary.to_csv(data_dir / "panel_a_data.csv", index=False, float_format="%.12g")
    return summary, bounds, (float(slope), float(intercept))


def make_groups(data: pd.DataFrame) -> pd.DataFrame:
    """Keep ties together in six negative, one exact-zero and three positive groups."""
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


def draw_b(data: pd.DataFrame, figure_dir: Path, data_dir: Path, *, fig_ax=None):
    """Plot country-adjusted group means and a group-size-weighted descriptive fit."""
    grouped = make_groups(data)
    overall = float(grouped.reactive_request.mean())
    grouped["country_request_mean"] = grouped.groupby("country").reactive_request.transform("mean")
    # Remove each country's average and add the panel-wide rate back for display.
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
    # polyfit squares its weights, so sqrt(n) gives each group a total weight of n.
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

    fig, ax = base_figure("B", fig_ax)
    ax.set_xlim(0.5, 10.5)
    ax.set_xticks(ranks, [f"{int(rank)}\nn={int(size)}" for rank, size in zip(ranks, counts)])
    ax.tick_params(axis="x", labelsize=8)
    ax.set_xlabel(
        "Ordered group of within-country deviation", labelpad=14,
    )
    ax.set_ylabel("Country-adjusted outcome (×100)",
                  labelpad=12)
    ax.scatter(ranks, rates, s=30, color=BLUE, edgecolor="white", linewidth=0.5, zorder=4)
    ax.plot(ranks, summary.weighted_fit_pct, color=ORANGE, linewidth=1.35,
            label="Weighted descriptive fit", zorder=3)
    ax.axhline(100 * overall, color=BASELINE, linewidth=0.9, linestyle=(0, (4, 3)),
               label="Overall mean", zorder=1)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=8.5, handlelength=2.4)
    fig.canvas.draw()
    bounds = tuple(float(v) for v in ax.bbox.bounds)
    if fig_ax is None:
        save_panel(fig, figure_dir, "panel_b")
        summary.to_csv(data_dir / "panel_b_data.csv", index=False, float_format="%.12g")
        grouped.to_csv(data_dir / "panel_b_month_data.csv", index=False, float_format="%.12g")
    return summary, bounds, (float(slope), float(intercept)), weighted_rate


def draw_combined(data: pd.DataFrame, figure_dir: Path, data_dir: Path):
    """Place A above B at the same physical scale as the separate panels."""
    plt.rcParams.update(STYLE)
    fig = plt.figure(figsize=(FIGSIZE[0], 2 * FIGSIZE[1]), dpi=DPI)
    axes = [
        fig.add_axes([
            MARGINS["left"], (offset + MARGINS["bottom"]) / 2,
            MARGINS["right"] - MARGINS["left"],
            (MARGINS["top"] - MARGINS["bottom"]) / 2,
        ])
        for offset in (1, 0)
    ]
    _, a_bounds, _ = draw_a(data, figure_dir, data_dir, fig_ax=(fig, axes[0]))
    _, b_bounds, _, _ = draw_b(data, figure_dir, data_dir, fig_ax=(fig, axes[1]))
    # Vertical positions differ; left edges and plotting dimensions must match.
    if not np.allclose(np.array(a_bounds)[[0, 2, 3]],
                       np.array(b_bounds)[[0, 2, 3]], atol=1e-9, rtol=0):
        raise ValueError("Combined panel plotting areas are not aligned")
    save_panel(fig, figure_dir, "figure_1")


def main() -> None:
    """Read inputs, run this script and save its outputs."""
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
    draw_combined(data, args.figure_dir, args.data_dir)
    print(f"Panel A: {len(a)} circles; Σ reactive months={int(a.reactive_event_months.sum())}")
    print(f"Panel B: {len(b)} groups; Σn={int(b.n_country_months.sum())}; "
          f"Σ events={int(b.reactive_event_months.sum())}; weighted mean={weighted:.6f}%")
    print(f"Panel A descriptive fit: slope={a_fit[0]:.6f}, intercept={a_fit[1]:.6f}")
    print(f"Panel B descriptive fit: slope={b_fit[0]:.6f} pp/group, intercept={b_fit[1]:.6f}")
    print(f"Aligned plot bounds: {a_bounds}")
    print(f"Saved combined Figure 1 (A above B): {args.figure_dir / 'figure_1.png'}")


if __name__ == "__main__":
    main()
