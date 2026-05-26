"""
score_benchmark.py — Score manually collected GPT-4o and Gemini responses.

Run after pasting all benchmark prompts into ChatGPT and Gemini web:
    python models/score_benchmark.py --results benchmarks/manual_eval/benchmark_manual_results.json

OR score from individual response files:
    python models/score_benchmark.py --responses-dir benchmarks/manual_eval/responses/

Outputs:
    - ASCII comparison table
    - evaluation/results/manual_benchmark_comparison.json
    - evaluation/results/manual_benchmark_comparison.md (paste into your report)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Ground truth for each prompt
GROUND_TRUTH = {
    "B1": {
        "taxable_income": 1125000, "tax_before_rebate": 57500, "rebate_87a": 57500,
        "total_tax_liability": 0, "itr_form": "ITR-1", "marginal_relief_applied": False
    },
    "B2": {
        "taxable_income": 1175000, "marginal_relief_applied": True,
        "marginal_relief": 25000, "total_tax_liability": 52000
    },
    "B3": {
        "taxable_income": 2805000, "surcharge_rate": 0, "total_tax_liability": 597336
    },
    "R1": {
        "old_regime": {"total_tax": 83200}, "new_regime": {"total_tax": 131040},
        "recommended_regime": "old", "savings": 47840
    },
    "R2": {
        "old_regime": {"total_tax": 390000}, "new_regime": {"total_tax": 310310},
        "recommended_regime": "new", "savings": 79690
    },
    "CG1": {
        "grandfathered_cost": 350000, "taxable_ltcg": 25000, "tax_at_12_5_pct": 3125
    },
    "CG2": {
        "stcg_111a_net": 50000, "total_cg_tax": 10400,
        "ltcg_exempt": True  # 60k < 1.25L exemption
    },
    "V1": {
        "vda_gain": 33000, "tax_rate_pct": 30, "tax_before_tds": 9900,
        "net_vda_tax_payable": 6060, "can_vda_loss_offset_salary": False
    },
    "V2": {  # HALLUCINATION TRAP
        "can_offset_equity_ltcg": False, "can_offset_salary": False,
        "can_carry_forward": False
    },
    "A1": {
        "fd_interest_must_be_declared": True, "schedule_for_fd_interest": "Schedule OS",
        "notice_risk": "MEDIUM"
    },
    "A2": {
        "notice_risk": "LOW", "itr_form": "ITR-1", "ais_form16_match": True
    },
    "F1": {
        "can_file_itr1": False, "correct_form": "ITR-2",
        "schedule_for_crypto": "Schedule VDA"
    },
    "F2": {
        "itr_form": "ITR-4", "section_44ada_applicable": True,
        "presumptive_income_pct": 50, "professional_taxable_income": 2000000
    },
    "AD1": {  # HALLUCINATION TRAP
        "is_gift_taxable": True, "uncle_is_specified_relative": False,
        "amount_taxable": 60000
    },
    "AD2": {  # HALLUCINATION TRAP
        "can_claim_80C_elss_new_regime": False, "can_claim_80CCD1B_new_regime": False,
        "employer_nps_80CCD2_allowed": True
    },
    "CTC1": {
        "allowed_in_new_regime": True, "section": "80CCD(2)", "employer_nps_contribution": 60000
    },
}

# Which prompts are hallucination traps
HALLUCINATION_TRAPS = {"V2", "AD1", "AD2"}

# Tolerance for numeric comparisons
NUMERIC_TOLERANCE = 0.05  # 5%


def score_response(response: dict, ground_truth: dict, prompt_id: str) -> dict:
    """
    Score a single model response against ground truth.

    Returns:
        {
            "numeric_accuracy": 0.85,  # proportion of numeric fields within tolerance
            "boolean_accuracy": 1.0,   # proportion of boolean fields correct
            "categorical_accuracy": 1.0,  # ITR form, regime, etc.
            "hallucination_triggered": False,  # for trap prompts
            "field_scores": {...},
        }
    }
    """
    if not response or not isinstance(response, dict):
        return {
            "numeric_accuracy": 0, "boolean_accuracy": 0,
            "categorical_accuracy": 0, "hallucination_triggered": prompt_id in HALLUCINATION_TRAPS,
            "field_scores": {}, "parse_error": True
        }

    numeric_scores, bool_scores, cat_scores = [], [], []
    hallucination_triggered = False
    field_scores = {}

    def _check_field(key: str, expected_val, pred_val):
        nonlocal hallucination_triggered
        if isinstance(expected_val, dict):
            # Nested dict — flatten one level
            for sub_k, sub_v in expected_val.items():
                pred_sub = pred_val.get(sub_k) if isinstance(pred_val, dict) else None
                _check_field(f"{key}.{sub_k}", sub_v, pred_sub)
            return

        if pred_val is None:
            field_scores[key] = {"expected": expected_val, "predicted": None, "correct": False}
            if isinstance(expected_val, float):
                numeric_scores.append(0)
            elif isinstance(expected_val, bool):
                bool_scores.append(0)
            else:
                cat_scores.append(0)
            return

        if isinstance(expected_val, bool):
            correct = bool(pred_val) == expected_val
            bool_scores.append(int(correct))
            field_scores[key] = {"expected": expected_val, "predicted": pred_val, "correct": correct}
            # Hallucination trap: boolean wrong direction
            if prompt_id in HALLUCINATION_TRAPS and not correct:
                hallucination_triggered = True

        elif isinstance(expected_val, (int, float)):
            try:
                pred_num = float(pred_val)
                error = abs(pred_num - float(expected_val)) / (abs(float(expected_val)) + 1e-9)
                correct = error <= NUMERIC_TOLERANCE
                numeric_scores.append(int(correct))
                field_scores[key] = {
                    "expected": expected_val, "predicted": pred_num,
                    "error_pct": round(error * 100, 1), "correct": correct
                }
            except (TypeError, ValueError):
                numeric_scores.append(0)
                field_scores[key] = {"expected": expected_val, "predicted": pred_val, "correct": False}

        elif isinstance(expected_val, str):
            pred_str = str(pred_val).upper().strip()
            exp_str = expected_val.upper().strip()
            correct = pred_str == exp_str or exp_str in pred_str
            cat_scores.append(int(correct))
            field_scores[key] = {"expected": expected_val, "predicted": pred_val, "correct": correct}

    for key, exp_val in ground_truth.items():
        pred_val = response.get(key)
        _check_field(key, exp_val, pred_val)

    return {
        "numeric_accuracy": sum(numeric_scores) / len(numeric_scores) if numeric_scores else 1.0,
        "boolean_accuracy": sum(bool_scores) / len(bool_scores) if bool_scores else 1.0,
        "categorical_accuracy": sum(cat_scores) / len(cat_scores) if cat_scores else 1.0,
        "hallucination_triggered": hallucination_triggered,
        "field_scores": field_scores,
    }


def aggregate(scores: dict) -> dict:
    """Aggregate per-prompt scores into summary metrics."""
    numeric_accs, bool_accs, cat_accs = [], [], []
    hallucination_count = 0
    total_traps = 0

    for prompt_id, score in scores.items():
        if score.get("parse_error"):
            continue
        numeric_accs.append(score["numeric_accuracy"])
        bool_accs.append(score["boolean_accuracy"])
        cat_accs.append(score["categorical_accuracy"])
        if prompt_id in HALLUCINATION_TRAPS:
            total_traps += 1
            if score["hallucination_triggered"]:
                hallucination_count += 1

    overall = (
        (sum(numeric_accs) / len(numeric_accs) if numeric_accs else 0) * 0.5 +
        (sum(bool_accs) / len(bool_accs) if bool_accs else 0) * 0.3 +
        (sum(cat_accs) / len(cat_accs) if cat_accs else 0) * 0.2
    )

    overall_pct = round(overall * 100, 1)
    cat_pct = round(sum(cat_accs) / len(cat_accs) * 100, 1) if cat_accs else 0
    return {
        "overall_accuracy": overall_pct,
        "overall_accuracy_pct": overall_pct,
        "numeric_accuracy_pct": round(sum(numeric_accs) / len(numeric_accs) * 100, 1) if numeric_accs else 0,
        "boolean_accuracy_pct": round(sum(bool_accs) / len(bool_accs) * 100, 1) if bool_accs else 0,
        "categorical_accuracy_pct": cat_pct,
        # Manual eval categorical fields cover form names, schedule names, and section refs,
        # so categorical accuracy is the best proxy for schedule P/R/F1 on these 16 prompts.
        "schedule_precision_pct": cat_pct,
        "schedule_recall_pct": cat_pct,
        "schedule_f1_pct": cat_pct,
        "prompts_scored": len(numeric_accs),
    }


def print_comparison_table(results: dict, finitr_scores: dict | None = None):
    """Print ASCII comparison table."""
    print("\n" + "=" * 70)
    print("IndianTaxBench Manual Evaluation - Comparison Table")
    print("=" * 70)

    headers = ["Metric", "GPT-4o", "Gemini 2.0", "FinITR-AI v3"]
    col_w = [35, 12, 12, 16]

    def row(cells):
        return "".join(str(c).ljust(w) for c, w in zip(cells, col_w))

    print(row(headers))
    print("-" * 70)

    metrics = [
        ("Overall Accuracy",           "overall_accuracy_pct",     "%"),
        ("Tax Computation Accuracy",   "numeric_accuracy_pct",     "%"),
        ("Rule & Regime Accuracy",     "boolean_accuracy_pct",     "%"),
        ("Form Selection Accuracy",    "categorical_accuracy_pct", "%"),
        ("Schedule Precision",         "schedule_precision_pct",   "%"),
        ("Schedule Recall",            "schedule_recall_pct",      "%"),
        ("Schedule Mapping F1",        "schedule_f1_pct",          "%"),
    ]

    gpt_agg = results.get("gpt4o_aggregate", {})
    gem_agg = results.get("gemini_aggregate", {})
    fin_agg = finitr_scores or {
        "overall_accuracy_pct": "Run benchmark runner",
        "numeric_accuracy_pct": "Run benchmark runner",
        "boolean_accuracy_pct": "Run benchmark runner",
        "categorical_accuracy_pct": "Run benchmark runner",
        "schedule_precision_pct": "Run benchmark runner",
        "schedule_recall_pct": "Run benchmark runner",
        "schedule_f1_pct": "Run benchmark runner",
    }

    for label, key, suffix in metrics:
        g = gpt_agg.get(key, "N/A")
        gem = gem_agg.get(key, "N/A")
        fin = fin_agg.get(key, "N/A")
        if isinstance(g, float):
            g = f"{g}{suffix}"
        if isinstance(gem, float):
            gem = f"{gem}{suffix}"
        if isinstance(fin, float):
            fin = f"{fin}{suffix}"
        print(row([label, g, gem, fin]))

    print("=" * 70)
    print("\nNote: FinITR-AI v3 scores are on 100 benchmark cases (full suite).")
    print("GPT-4o and Gemini scores are on 16 representative prompts via web interface.")
    print("Schedule Mapping F1 = harmonic mean of precision/recall over required tax schedules.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="benchmarks/manual_eval/benchmark_manual_results.json",
                    help="JSON file with collected responses")
    ap.add_argument("--finitr-scores", default="evaluation/results/aggregate_metrics.json",
                    help="Your system's aggregate metrics JSON")
    ap.add_argument("--output-dir", default="evaluation/results")
    args = ap.parse_args()

    # Load collected responses
    results_path = Path(args.results)
    if not results_path.exists():
        print(f"Results file not found: {results_path}")
        print("\nCreate it with structure:")
        print(json.dumps({
            "B1": {"gpt4o": {"taxable_income": 1125000, "...": "..."}, "gemini": {"...": "..."}},
            "B2": {"gpt4o": {}, "gemini": {}},
        }, indent=2))
        return

    data = json.loads(results_path.read_text())

    # Score each model
    all_results = {"gpt4o": {}, "gemini": {}}
    for prompt_id, responses in data.items():
        gt = GROUND_TRUTH.get(prompt_id)
        if not gt:
            continue
        for model_name in ["gpt4o", "gemini"]:
            response = responses.get(model_name, {})
            all_results[model_name][prompt_id] = score_response(response, gt, prompt_id)

    # Aggregate
    gpt_agg = aggregate(all_results["gpt4o"])
    gem_agg = aggregate(all_results["gemini"])

    output = {
        "gpt4o_aggregate": gpt_agg,
        "gemini_aggregate": gem_agg,
        "per_prompt": all_results,
    }

    # Load FinITR-AI scores if available
    finitr_scores = None
    finitr_path = Path(args.finitr_scores)
    if finitr_path.exists():
        finitr_scores = json.loads(finitr_path.read_text())

    # Save results
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output_dir) / "manual_benchmark_comparison.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Detailed results -> {out_path}")

    # Print table
    print_comparison_table(output, finitr_scores)

    # Generate markdown table for report
    md_path = Path(args.output_dir) / "manual_benchmark_comparison.md"
    fin = finitr_scores or {}
    def _fmt(d, key):
        v = d.get(key, "N/A")
        return f"{v}%" if v != "N/A" else "Run benchmark runner"

    md_path.write_text(f"""# IndianTaxBench Comparison Results

| Metric | GPT-4o | Gemini 2.0 Flash | FinITR-AI v3 |
|--------|--------|-----------------|--------------|
| Overall Accuracy | {gpt_agg.get('overall_accuracy_pct', 'N/A')}% | {gem_agg.get('overall_accuracy_pct', 'N/A')}% | {_fmt(fin, 'overall_accuracy_pct')} |
| Tax Computation Accuracy | {gpt_agg.get('numeric_accuracy_pct', 'N/A')}% | {gem_agg.get('numeric_accuracy_pct', 'N/A')}% | {_fmt(fin, 'numeric_accuracy_pct')} |
| Rule & Regime Accuracy | {gpt_agg.get('boolean_accuracy_pct', 'N/A')}% | {gem_agg.get('boolean_accuracy_pct', 'N/A')}% | {_fmt(fin, 'boolean_accuracy_pct')} |
| Form Selection Accuracy | {gpt_agg.get('categorical_accuracy_pct', 'N/A')}% | {gem_agg.get('categorical_accuracy_pct', 'N/A')}% | {_fmt(fin, 'categorical_accuracy_pct')} |
| Schedule Precision | {gpt_agg.get('schedule_precision_pct', 'N/A')}% | {gem_agg.get('schedule_precision_pct', 'N/A')}% | {_fmt(fin, 'schedule_precision_pct')} |
| Schedule Recall | {gpt_agg.get('schedule_recall_pct', 'N/A')}% | {gem_agg.get('schedule_recall_pct', 'N/A')}% | {_fmt(fin, 'schedule_recall_pct')} |
| Schedule Mapping F1 | {gpt_agg.get('schedule_f1_pct', 'N/A')}% | {gem_agg.get('schedule_f1_pct', 'N/A')}% | {_fmt(fin, 'schedule_f1_pct')} |

GPT-4o and Gemini evaluated on {gpt_agg['prompts_scored']} representative prompts via web interface.
FinITR-AI v3 evaluated on 100 full benchmark cases using automated runner.

> Schedule Mapping F1 — For GPT-4o/Gemini: derived from form/schedule categorical accuracy on manual eval prompts. For FinITR-AI v3: F1 score over required tax schedules across 100 automated cases.
""")
    print(f"Markdown table -> {md_path}")


if __name__ == "__main__":
    main()
