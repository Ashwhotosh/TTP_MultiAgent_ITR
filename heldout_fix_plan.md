# Held-Out Set Accuracy & Noise Reconciliation Plan

This plan details how to resolve the poor performance on the IndianTaxBench Held-Out set (n=40) while keeping the noise injection intact. We will correct the dataset generator's mathematical expected tax labels and improve the agent pipeline's noise-reconciliation capabilities so that the system can handle real-world input noise to achieve highest accuracy.

## User Review Required

> [!IMPORTANT]
> - **Clean Ground Truth with Noisy Inputs**: As requested, we will keep the expected tax liability calculated against the **clean ground truth** values. We will NOT update the expected labels to include the noise.
> - **Pipeline Reconciliation**: The model will handle the noise by comparing Form 16 and AIS salary values. When the mismatch is within a minor OCR rounding threshold (<= 3%), it will trust the AIS salary (as government AIS data is electronically submitted and noise-free) and override `ctx.gross_income` with it.
> - **Generalizability**: This reconciliation logic is general and does not rely on hardcoded held-out PANs or names. It will automatically run on both training and held-out sets, preserving the 100% training set accuracy.

## Open Questions

No open questions. The objective is clear: improve model resilience to noise to match clean expected tax liabilities.

---

## Proposed Changes

### 1. Held-Out Dataset Generator

We need to fix `generate_holdout.py` to use `CalculatorTool` to calculate expected tax liabilities on clean gross incomes. Right now, the expected values in the holdout generator are completely incorrect (e.g. applying flat 5% rates or expecting 0.0 tax where salary is taxable).

#### [MODIFY] [generate_holdout.py](file:///c:/Users/Ashwhotosh/Downloads/Major%20Project/FinITR-AI-v3/benchmarks/indian_tax_bench/generate_holdout.py)
- Import `CalculatorTool` from `tools.calculator` and initialize it.
- In `build_basic_salary`, `build_regime_comparison`, `build_capital_gains`, `build_crypto`, `build_ais_reconciliation_medium`, `build_adversarial`, and `build_ctc_restructuring`, replace the incorrect hardcoded tax/taxable calculations with calls to `calculator.calculate_new_regime_tax` or `calculator.calculate_old_regime_tax`.
- In `build_itr_form_selection`, change the `_base` call parameter from `gross` (which is salary + freelance) to `salary`. This fixes a major bug where freelance income was incorrectly written into Form 16 gross salary fields. Compute expected tax using `calculator.calculate_new_regime_tax(salary, {})`.
- Do NOT recompute expected tax on noised inputs in `inject_noise` or `main`. Keep expected tax values calculated on the clean inputs.

### 2. Multi-Agent Orchestrator

We will add a noise-reconciliation step to handle OCR rounding differences.

#### [MODIFY] [orchestrator.py](file:///c:/Users/Ashwhotosh/Downloads/Major%20Project/FinITR-AI-v3/agents/orchestrator.py)
- In the `_parse_documents` method, when auto-deriving gross salary from Form 16:
  - Check if AIS salary (`SFT-001`) is present.
  - If AIS salary is present, calculate the difference between Form 16 gross salary and AIS salary.
  - If the difference is within 3% of the AIS salary, assume the Form 16 value has OCR rounding noise.
  - Override `ctx.gross_income` with the clean AIS salary.
  - Reconcile `ctx.basic_salary` by scaling the Form 16 basic salary proportionally: `ctx.basic_salary = round(f16_basic * (ais_salary / f16_gross))`.
  - Otherwise, default to Form 16 gross salary.

---

## Verification Plan

### Automated Tests
1. Regenerate the held-out cases:
   ```powershell
   .\venv\Scripts\python.exe benchmarks/indian_tax_bench/generate_holdout.py
   ```
2. Run a specific test case (e.g., `ho_026` or a noisy case) using `test_ho.py` to verify reconciliation:
   ```powershell
   .\venv\Scripts\python.exe test_ho.py
   ```
3. Run the full held-out benchmark:
   ```powershell
   .\venv\Scripts\python.exe -m benchmarks.indian_tax_bench.runner --holdout
   ```
4. Verify that `evaluation/results/holdout_metrics.json` shows high tax computation accuracy (>95%).
