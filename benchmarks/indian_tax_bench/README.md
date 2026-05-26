# IndianTaxBench v1.0

A benchmark of 100+ adversarial Indian tax scenarios for evaluating 
LLM-based tax advisory systems.

See plans/week_4.md for the full specification.

## Categories
1. Basic Salary (12 cases)
2. Regime Comparison (12 cases)
3. Capital Gains (15 cases)
4. Crypto / VDA (12 cases)
5. AIS Reconciliation (12 cases)
6. ITR Form Selection (10 cases)
7. Adversarial / Tricky (15 cases)
8. CTC Restructuring (12 cases)

## Running
```bash
python -m benchmarks.indian_tax_bench.runner --skip-baselines
python -m benchmarks.indian_tax_bench.runner --all
```
