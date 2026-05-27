# Week 4: IndianTaxBench + Evaluation

## Goal
Build a benchmark of 100+ adversarial Indian tax scenarios. Run your system and 3 baselines against it. Produce a comparison table that goes into your report/paper.

---

## Task 4.1: Design IndianTaxBench Categories (Day 1)

**File**: `benchmarks/indian_tax_bench/README.md`

Create 8 categories of test cases, ~12-15 cases each:

### Category 1: Basic Salary (12 cases)
Simple salaried employee, various income levels. Tests: correct slab computation, standard deduction, 87A rebate, marginal relief.
- tc_001: Income 10L, New Regime → tax should be 0 (rebate)
- tc_002: Income 12L, New Regime → tax should be 0 (rebate threshold)
- tc_003: Income 12.5L, New Regime → marginal relief kicks in
- tc_004: Income 15L, New Regime → normal slabs
- ... etc for edge cases near slab boundaries

### Category 2: Regime Comparison (12 cases)
Same person, different deduction profiles → which regime wins?
- tc_013: 80C=1.5L, 80D=25k, HRA=2L → Old regime wins
- tc_014: No deductions at all → New regime wins
- tc_015: Only 80CCD(2) → New regime wins (80CCD(2) allowed in both)
- ... etc

### Category 3: Capital Gains (15 cases)
STCG/LTCG classification, grandfathering, exemption limits.
- tc_025: LTCG on equity held 2 years, bought in 2017 → grandfathering applies
- tc_026: LTCG 1.5L → first 1.25L exempt, 25k taxed at 12.5%
- tc_027: STCG + LTCG loss → loss offset rules
- ... etc

### Category 4: Crypto / VDA (12 cases)
Section 115BBH edge cases.
- tc_040: Crypto gain 50k → 30% flat = 15k, no exemption
- tc_041: Crypto loss 20k + equity gain 50k → loss CANNOT offset equity
- tc_042: Crypto with TDS 194S credit → net payable
- ... etc

### Category 5: AIS Reconciliation (12 cases)
Mismatch detection between AIS and declared income.
- tc_052: AIS shows FD interest 32k, Form 16 doesn't have it → flag
- tc_053: AIS shows crypto, user didn't declare → high risk
- tc_054: AIS and Form 16 salary match → no flag
- ... etc

### Category 6: ITR Form Selection (10 cases)
Which form is correct?
- tc_064: Only salary → ITR-1
- tc_065: Salary + crypto → ITR-2
- tc_066: Salary + freelance > 50L → ITR-3
- tc_067: Salary + presumptive 44ADA → ITR-4
- ... etc

### Category 7: Adversarial / Tricky (15 cases)
Designed to make LLMs hallucinate.
- tc_074: User asks about 80C under New Regime → system must say "not applicable"
- tc_075: HRA claimed but no rent receipts → should warn
- tc_076: Agricultural income 4.9L (below reporting threshold) + salary → ITR-1 ok
- tc_077: Agricultural income 6L → must declare, ITR-2
- tc_078: Gift from uncle ₹60k → taxable under 56(2)(x) (uncle is not specified relative)
- tc_079: Gift from brother ₹5L → NOT taxable (brother is specified relative)
- tc_080: Section 44ADA turnover 74L → 44ADA ok (limit 75L)
- tc_081: Section 44ADA turnover 76L → 44ADA NOT applicable, full books needed
- ... etc

### Category 8: CTC Restructuring (12 cases)
NPS optimization scenarios.
- tc_090: No employer NPS, suggest restructuring → savings calculation correct
- tc_091: Already has employer NPS 10% → suggest increasing to 14% (if govt)
- tc_092: NPS suggestion under Old Regime → 80CCD(2) available in both
- ... etc

---

## Task 4.2: Create Test Case JSON Format (Day 1)

**File**: `benchmarks/indian_tax_bench/cases/`

Each test case is a JSON file:
```json
{
    "id": "tc_001",
    "category": "basic_salary",
    "difficulty": "easy",
    "description": "Simple salaried employee, 10L income, New Regime",
    "input": {
        "gross_income": 1000000,
        "regime": "new",
        "deductions": {},
        "income_sources": ["salary"],
        "documents": {
            "form16": {"gross_salary": 1000000, "tds": 0},
            "ais": {"sft": [{"type": "salary", "amount": 1000000}]},
            "bank_transactions": []
        }
    },
    "expected": {
        "taxable_income": 925000,
        "tax_liability": 0,
        "rebate_87a_applied": true,
        "marginal_relief": 0,
        "itr_form": "ITR-1",
        "risk_level": "LOW",
        "schedules_required": ["Schedule Salary"],
        "hallucination_traps": ["Should NOT recommend 80C", "Should NOT recommend 80D"]
    },
    "evaluation_fields": ["tax_liability", "itr_form", "risk_level"]
}
```

Create a script to generate all test case JSON files:
**File**: `benchmarks/indian_tax_bench/generate_cases.py`

---

## Task 4.3: Build Benchmark Runner (Day 2-3)

**File**: `benchmarks/indian_tax_bench/runner.py`

```python
class IndianTaxBenchRunner:
    def run_system(self, test_cases: list[dict]) -> list[dict]:
        """Run our system on all test cases."""
        # For each case, create synthetic documents and run orchestrator
        pass

    def run_baseline_llm(self, test_cases, model="gpt-4o-mini") -> list[dict]:
        """Run a baseline LLM with a tax prompt."""
        # Send the test case as a prompt, parse structured output
        pass

    def evaluate(self, predictions: list[dict], ground_truth: list[dict]) -> dict:
        """Compute metrics."""
        pass
```

### Metrics to compute:
1. **Tax Liability Accuracy**: |predicted - expected| / expected. Average across cases.
2. **ITR Form Accuracy**: exact match on recommended form.
3. **Risk Level Accuracy**: exact match or ±1 level.
4. **Schedule Mapping F1**: precision/recall on required schedules.
5. **Hallucination Rate**: % of cases where a hallucination trap was triggered.
6. **Faithfulness Rate**: % of claims verified as FAITHFUL by our CriticAgent.
7. **Latency**: average time per case.

---

## Task 4.4: Run Baselines (Day 3-4)

### Baseline 1: GPT-4o-mini Direct
Send each test case as a prompt to GPT-4o-mini API:
```
You are an Indian tax expert. Given this taxpayer profile:
[test case input as JSON]

Provide:
1. Taxable income
2. Tax liability (FY 25-26)
3. Recommended ITR form
4. Required schedules
5. Risk level (LOW/MEDIUM/HIGH)

Answer in JSON format only.
```

### Baseline 2: Gemini-2.0-Flash Direct
Same prompt, Gemini API.

### Baseline 3: Llama-3.1-8B Direct (via Ollama)
Same prompt, local Ollama.

### Baseline 4: Your System (FinITR-AI v3)
Run the full pipeline.

Estimated API cost: ~₹300-500 for GPT-4o-mini + Gemini-Flash on 100 cases.

---

## Task 4.5: Generate Results Report (Day 4-5)

**File**: `evaluation/results/indian_tax_bench_results.json`

```json
{
    "benchmark": "IndianTaxBench v1.0",
    "num_cases": 100,
    "results": {
        "finitr_ai_v3": {
            "tax_accuracy": 0.94,
            "itr_form_accuracy": 0.97,
            "risk_accuracy": 0.88,
            "schedule_f1": 0.92,
            "hallucination_rate": 0.02,
            "faithfulness_rate": 0.91,
            "avg_latency_sec": 15.3
        },
        "gpt4o_mini": {
            "tax_accuracy": 0.82,
            "itr_form_accuracy": 0.85,
            "hallucination_rate": 0.15,
            "avg_latency_sec": 2.1
        },
        // ... other baselines
    },
    "category_breakdown": { ... },
    "notable_failures": [ ... ]
}
```

Create a comparison visualization (save as PNG for the paper):
```python
# Use plotly or matplotlib to create a radar chart or grouped bar chart
# comparing all systems across metrics
```

---

## Task 4.6: Ablation Study (Day 5)

**File**: `evaluation/ablation.py`

Test which components matter most:
1. Full system (all agents)
2. Without CriticAgent (no verification)
3. Without AIS reconciliation (bank statement only)
4. Without PageIndex (no legal retrieval, LLM freestyles)
5. Without CalculatorTool (LLM does its own math)

For each ablation, run on the full benchmark and report metrics.
Expected finding: removing the CriticAgent increases hallucination rate dramatically.

---

## Week 4 Acceptance Criteria

- [ ] 100+ test cases across 8 categories, all in JSON format
- [ ] Benchmark runner executes all cases without crashing
- [ ] At least 2 baselines run successfully (GPT-4o-mini + Llama)
- [ ] Results JSON with all metrics computed
- [ ] Comparison visualization generated
- [ ] Ablation study shows CriticAgent value
- [ ] All test cases have clear expected outputs
- [ ] Notable failure cases documented with analysis
- [ ] README in benchmarks/ explains how to reproduce
