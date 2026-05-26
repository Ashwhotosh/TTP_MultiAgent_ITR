"""
visualize.py - IndianTaxBench results visualization.

Reads results and ablation JSONs, produces a high-quality comparison chart,
and saves it as evaluation/results/comparison_metrics.png.
"""
import os
import json
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise ImportError("numpy is required. Run: pip install numpy")

try:
    import matplotlib
    matplotlib.use('Agg')  # must be before pyplot import
    import matplotlib.pyplot as plt
except ImportError:
    raise ImportError("matplotlib is required. Run: pip install matplotlib")

def generate_charts(results_dir="evaluation/results"):
    results_dir = Path(results_dir)
    results_file = results_dir / "indian_tax_bench_results.json"
    ablation_file = results_dir / "ablation_results.json"
    
    if not results_file.exists():
        print(f"Error: {results_file} not found. Run runner.py first.")
        return
    if not ablation_file.exists():
        print(f"Error: {ablation_file} not found. Run ablation.py first.")
        return
        
    # Load data
    res_data = json.loads(results_file.read_text(encoding="utf-8"))
    abl_data = json.loads(ablation_file.read_text(encoding="utf-8"))
    
    # ----------------------------------------------------
    # Subplot 1: Baseline Comparison
    # ----------------------------------------------------
    models = ["finitr_ai_v3", "gpt4o_mini", "gemini_2_0_flash", "llama_3_1_8b"]
    model_labels = {
        "finitr_ai_v3": "FinITR-AI v3 (Ours)",
        "gpt4o_mini": "GPT-4o-mini Direct",
        "gemini_2_0_flash": "Gemini-2.0-Flash Direct",
        "llama_3_1_8b": "Llama-3.1-8B Direct"
    }
    
    metrics = ["tax_accuracy", "itr_form_accuracy", "risk_accuracy", "schedule_f1", "hallucination_rate", "faithfulness_rate"]
    metric_labels = {
        "tax_accuracy": "Tax Accuracy",
        "itr_form_accuracy": "ITR Form Acc",
        "risk_accuracy": "Risk Level Acc",
        "schedule_f1": "Schedule F1",
        "hallucination_rate": "Hallucination Rate\n(Lower is Better)",
        "faithfulness_rate": "Faithfulness Rate"
    }
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 11))
    
    x = np.arange(len(metrics))
    width = 0.2
    
    for i, model in enumerate(models):
        if model not in res_data["results"]:
            continue
        model_results = res_data["results"][model]
        values = []
        for m in metrics:
            val = model_results.get(m, 0.0)
            values.append(val)
            
        ax1.bar(x + (i - 1.5) * width, values, width, label=model_labels[model])
        
    ax1.set_title("System vs LLM Baselines Performance (IndianTaxBench)", fontsize=13, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels([metric_labels[m] for m in metrics], fontsize=9)
    ax1.set_ylabel("Score (0.0 to 1.0)", fontsize=10)
    ax1.set_ylim(0, 1.15)
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    ax1.legend(loc="upper right", framealpha=0.9, fontsize=9)
    
    # ----------------------------------------------------
    # Subplot 2: Ablation Study
    # ----------------------------------------------------
    ablations = ["full_system", "no_critic", "no_ais", "no_pageindex", "no_calculator"]
    ablation_labels = {
        "full_system": "Full System",
        "no_critic": "Without CriticAgent",
        "no_ais": "Without AIS",
        "no_pageindex": "Without PageIndex",
        "no_calculator": "Without CalculatorTool"
    }
    
    abl_metrics = ["tax_accuracy", "faithfulness_rate", "hallucination_rate"]
    abl_metric_labels = {
        "tax_accuracy": "Tax Accuracy",
        "faithfulness_rate": "Faithfulness Rate",
        "hallucination_rate": "Hallucination Rate"
    }
    
    x_abl = np.arange(len(ablations))
    width_abl = 0.25
    
    colors = ["#2ecc71", "#3498db", "#e74c3c"]
    
    for i, m in enumerate(abl_metrics):
        values = []
        for abl in ablations:
            val = abl_data.get(abl, {}).get(m, 0.0)
            values.append(val)
            
        ax2.bar(x_abl + (i - 1) * width_abl, values, width_abl, label=abl_metric_labels[m], color=colors[i])
        
    ax2.set_title("Ablation Study (Effect of Core Components)", fontsize=13, fontweight='bold', pad=15)
    ax2.set_xticks(x_abl)
    ax2.set_xticklabels([ablation_labels[a] for a in ablations], fontsize=9)
    ax2.set_ylabel("Score (0.0 to 1.0)", fontsize=10)
    ax2.set_ylim(0, 1.15)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    ax2.legend(loc="upper right", framealpha=0.9, fontsize=9)
    
    plt.tight_layout(pad=3.0)
    
    output_path = results_dir / "comparison_metrics.png"
    plt.savefig(output_path, dpi=300)
    print(f"Comparison visualization generated successfully -> {output_path}")

if __name__ == "__main__":
    generate_charts()
