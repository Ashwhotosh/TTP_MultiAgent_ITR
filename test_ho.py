import json
from benchmarks.indian_tax_bench.runner import IndianTaxBenchRunner

def main():
    runner = IndianTaxBenchRunner()
    with open("benchmarks/indian_tax_bench/holdout/ho_026.json") as f:
        case = json.load(f)
    print("EXPECTED:", json.dumps(case["expected"], indent=2))
    
    pred = runner.run_system_case(case)
    print("PREDICTED:", json.dumps(pred, indent=2))
    
    from evaluation.metrics import evaluate_case
    metrics = evaluate_case(pred, case)
    print("METRICS:", json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
