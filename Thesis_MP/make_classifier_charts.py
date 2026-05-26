"""
make_classifier_charts.py -- Two data-backed figures for the classifier results.

Both read ONLY the stored metrics in
    models/transaction_classifier_v2_metrics.json
so no number is invented here.

Writes:
    Thesis_MP/2.Thesis_Image/result5_classifier_f1.png   (per-class F1, 12 classes)
    Thesis_MP/2.Thesis_Image/result6_cascade_usage.png   (stage usage split)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "models" / "transaction_classifier_v2_metrics.json"
OUT = Path(__file__).resolve().parent / "2.Thesis_Image"

# label -> (display name, tax role)  role in {"I": income, "D": deduction, "N": neutral}
META = {
    "CAPITAL_MARKET":        ("Capital Market",        "I"),
    "CRYPTO_TRANSACTION":    ("Crypto Transaction",    "I"),
    "DIVIDEND_INCOME":       ("Dividend Income",       "I"),
    "FREELANCE_INCOME":      ("Freelance Income",      "I"),
    "INTEREST_INCOME":       ("Interest Income",       "I"),
    "SALARY_INCOME":         ("Salary Income",         "I"),
    "INVESTMENT_TAX_SAVING": ("Tax-Saving Investment", "D"),
    "INSURANCE_PREMIUM":     ("Insurance Premium",     "D"),
    "RENT_PAID":             ("Rent Paid (HRA)",       "D"),
    "LOAN_EMI":              ("Loan EMI",              "N"),
    "REGULAR_EXPENSE":       ("Regular Expense",       "N"),
    "TRANSFER":              ("Transfer",              "N"),
}

ROLE_COLOR = {"I": "#0CA678", "D": "#1C7ED6", "N": "#ADB5BD"}
ROLE_NAME = {"I": "Income (must not be missed)",
             "D": "Deduction (miss only under-claims)",
             "N": "Tax-neutral"}


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def chart_f1(d: dict) -> None:
    per = d["per_category"]
    # order: income first, then deduction, then neutral; within group by F1 desc
    rank = {"I": 0, "D": 1, "N": 2}
    items = sorted(
        META.items(),
        key=lambda kv: (rank[kv[1][1]], -per[kv[0]]["f1-score"]),
    )
    names = [v[0] for _, v in items]
    roles = [v[1] for _, v in items]
    f1 = [per[k]["f1-score"] * 100 for k, _ in items]
    colors = [ROLE_COLOR[r] for r in roles]

    y = list(range(len(items)))[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    bars = ax.barh(y, f1, color=colors, edgecolor="white", height=0.66)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlim(0, 109)
    ax.set_xlabel("F1 score (%)", fontsize=11)
    ax.set_title("Transaction Classifier -- Per-Class F1 (80-sample held-out set)",
                 fontsize=12.5, fontweight="bold")
    ax.grid(axis="x", color="#E9ECEF", linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for b, v in zip(bars, f1):
        ax.text(v + 1.2, b.get_y() + b.get_height() / 2,
                f"{v:.1f}", va="center", fontsize=9.5, fontweight="bold")

    macro = d["per_category"]["macro avg"]["f1-score"] * 100
    ax.axvline(macro, color="#E8590C", linestyle="--", linewidth=1.4)
    ax.text(macro, len(items) - 0.4, f" macro avg {macro:.1f}%",
            color="#E8590C", fontsize=9.5, fontweight="bold", va="bottom")

    handles = [plt.Rectangle((0, 0), 1, 1, color=ROLE_COLOR[r]) for r in ("I", "D", "N")]
    ax.legend(handles, [ROLE_NAME[r] for r in ("I", "D", "N")],
              loc="upper center", bbox_to_anchor=(0.5, -0.10),
              ncol=3, fontsize=9, frameon=False)

    fig.tight_layout()
    out = OUT / "result5_classifier_f1.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"wrote {out}")
    plt.close(fig)


def chart_cascade(d: dict) -> None:
    su = d["stage_usage"]
    pattern = su["pattern"]
    ml = su["ml"]
    llm = su["llm_fallback"]
    total = pattern + ml + llm

    labels = ["Stage 1: Regex rules", "Stage 2: kNN similarity", "Stage 3: LLM fallback"]
    counts = [pattern, ml, llm]
    colors = ["#0CA678", "#1C7ED6", "#F08C00"]

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    bars = ax.bar(labels, counts, color=colors, edgecolor="white", width=0.6)
    ax.set_ylabel("Transactions resolved (of 80)", fontsize=11)
    ax.set_ylim(0, max(counts) * 1.22)
    ax.set_title("Cascade Stage Usage -- where the 80 test cases were resolved",
                 fontsize=12, fontweight="bold")
    ax.grid(axis="y", color="#E9ECEF", linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for b, c in zip(bars, counts):
        pct = 100 * c / total + 1e-9   # round half up (56.25 -> 56.3) to match prose
        ax.text(b.get_x() + b.get_width() / 2, c + 0.8,
                f"{c}\n({pct:.1f}%)", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    fig.tight_layout()
    out = OUT / "result6_cascade_usage.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"wrote {out}")
    plt.close(fig)


def main() -> None:
    d = load()
    OUT.mkdir(parents=True, exist_ok=True)
    chart_f1(d)
    chart_cascade(d)


if __name__ == "__main__":
    main()
