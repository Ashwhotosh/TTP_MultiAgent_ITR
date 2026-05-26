"""
make_ablation_chart.py -- Rebuild the ablation figure with UNAMBIGUOUS labels.

Reads the real numbers from evaluation/results/ablation_results.json (no data is
invented here) and draws three panels -- Tax Accuracy, Risk Accuracy, and
Hallucination Rate -- so that each component's removal shows its effect somewhere.
Bars are labelled "Full System" and "Without X" (not "- X"), which is what was
being misread.

Writes:
    Thesis_MP/2.Thesis_Image/result3.png
    evaluation/results/chart_ablation.png   (keep source-of-truth in sync)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "evaluation" / "results" / "ablation_results.json"
OUT_THESIS = Path(__file__).resolve().parent / "2.Thesis_Image" / "result3.png"
OUT_SRC = ROOT / "evaluation" / "results" / "chart_ablation.png"

# row order (top -> bottom) and display labels
ROWS = [
    ("full_system",   "Full System"),
    ("no_critic",     "Without CriticAgent"),
    ("no_ais",        "Without AIS Reconciliation"),
    ("no_pageindex",  "Without PageIndex RAG"),
    ("no_calculator", "Without CalculatorTool"),
]

GREEN = "#0CA678"   # full system / good
GREY  = "#ADB5BD"   # unchanged from full
RED   = "#E03131"   # the metric this ablation damages
ORANGE = "#F08C00"


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def main() -> None:
    d = load()
    labels = [lbl for _, lbl in ROWS]
    y = list(range(len(ROWS)))[::-1]  # so first row sits at top

    def vals(key, scale=100.0):
        return [d[k][key] * scale for k, _ in ROWS]

    tax = vals("tax_accuracy")
    risk = vals("risk_accuracy")
    hall = vals("hallucination_rate")

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2))
    fig.suptitle("Ablation Study -- each bar removes ONE component from the full system\n"
                 "(data: evaluation/results/ablation_results.json; 100-case suite)",
                 fontsize=12, fontweight="bold")

    def panel(ax, data, title, baseline, higher_is_better=True, unit="%"):
        # colour: full system green; a bar is red if it diverges from the
        # full-system baseline on THIS metric, else grey (unchanged)
        colors = []
        for i, (k, _) in enumerate(ROWS):
            if k == "full_system":
                colors.append(GREEN)
            elif abs(data[i] - baseline) < 0.05:
                colors.append(GREY)            # essentially unchanged
            else:
                colors.append(RED if not higher_is_better or data[i] < baseline
                               else ORANGE)
        bars = ax.barh(y, data, color=colors, edgecolor="white", height=0.62)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9.5)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlim(0, max(100, max(data) * 1.15))
        ax.grid(axis="x", color="#E9ECEF", linewidth=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for bi, v in zip(bars, data):
            ax.text(v + 1.5, bi.get_y() + bi.get_height() / 2,
                    f"{v:.1f}{unit}", va="center", fontsize=9.5,
                    fontweight="bold")

    panel(axes[0], tax,  "Tax Accuracy (higher better)",
          baseline=tax[0], higher_is_better=True)
    panel(axes[1], risk, "Risk Accuracy (higher better)",
          baseline=risk[0], higher_is_better=True)
    panel(axes[2], hall, "Hallucination Rate (lower better)",
          baseline=hall[0], higher_is_better=False)

    fig.tight_layout(rect=[0, 0, 1, 0.90])
    OUT_THESIS.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_THESIS, dpi=150, bbox_inches="tight")
    fig.savefig(OUT_SRC, dpi=150, bbox_inches="tight")
    print(f"wrote {OUT_THESIS}")
    print(f"wrote {OUT_SRC}")
    plt.close(fig)


if __name__ == "__main__":
    main()
