"""Generate the delivery-round-position histogram (Figure S1) from source rows."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = pd.read_csv(ROOT / "data/source/deliveries.csv", keep_default_na=False)
    rounds = pd.to_numeric(source.round_number, errors="coerce").dropna()
    counts = rounds.astype(int).value_counts().sort_index()
    assert counts.index.tolist() == list(range(1, 8))
    assert counts.tolist() == [69, 14, 6, 6, 3, 1, 1] and counts.sum() == 100
    out = ROOT / "analysis/figures/delivery_rounds"
    out.mkdir(exist_ok=True)
    counts.rename_axis("round_position").rename("delivery_records").to_csv(out / "figure_data.csv")
    fig, ax = plt.subplots(figsize=(10.8, 6.4))
    ax.bar(counts.index, counts.values, color="#266c8d", width=.7)
    for x, y in counts.items():
        ax.text(x, y + 1, str(y), ha="center", va="bottom", weight="bold", color="#24485b")
    ax.set(title="Recorded OCV deliveries by round position", xlabel="Delivery round position",
           ylabel="Number of recorded delivery rounds", xticks=list(range(1, 8)), ylim=(0, 78))
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#edf0f2")
    fig.subplots_adjust(bottom=.2, top=.88, left=.1, right=.98)
    fig.text(.1, .06, "Bars count delivery records at each round position (100 rounds total),\n"
             "not requests with exactly that many rounds.", fontsize=10, color="#526879")
    fig.savefig(out / "delivery_round_positions.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
