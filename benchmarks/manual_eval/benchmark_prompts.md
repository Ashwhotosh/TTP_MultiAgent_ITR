# IndianTaxBench — Manual Evaluation Guide
## For Comparing GPT-4o and Gemini 2.0 Flash via Web Interface (No API Key Required)

---

## How This Works

1. You paste each numbered prompt below into ChatGPT (gpt-4o) and Gemini (gemini.google.com)
2. Copy the response into the scoring sheet (`benchmark_scoring.csv`)
3. Run `python models/score_benchmark.py` — it computes all metrics automatically
4. You get a comparison table: FinITR-AI v3 vs GPT-4o vs Gemini

Total prompts: 20 (2-3 per category)
Estimated time: 45 minutes across both interfaces

---

## IMPORTANT: Exact System Prompt to Use

Before each prompt, set this system message (ChatGPT: click "Custom Instructions"; Gemini: paste at the top of each conversation):

```
You are an expert Indian income tax advisor with deep knowledge of FY 2025-26 (AY 2026-27) tax laws. 
Answer precisely using current Indian tax rules. 
Respond ONLY in valid JSON format. No explanation outside the JSON.
```

---

## CATEGORY 1: Basic Salary (tc_001, tc_003, tc_006)

### Prompt B1 (maps to tc_003)
```
{"scenario": "Salaried employee, gross salary ₹12,00,000, New Regime, no other income or deductions.", "task": "Compute tax for FY 2025-26. Standard deduction applies."}

Respond ONLY in this JSON:
{"taxable_income": <number>, "tax_before_rebate": <number>, "rebate_87a": <number>, "tax_after_rebate": <number>, "cess_4pct": <number>, "total_tax_liability": <number>, "marginal_relief_applied": <boolean>, "itr_form": "ITR-1 or ITR-2 or ITR-3 or ITR-4"}
```
**Expected**: taxable_income=1125000, rebate=60000 (new 87A limit for new regime), total_tax=0 if under rebate threshold, itr_form=ITR-1
**Ground truth**: taxable_income=1125000, tax_before_rebate=57500, rebate_87a=57500, total_tax=0, itr_form=ITR-1

### Prompt B2 (maps to tc_005 — marginal relief)
```
{"scenario": "Salaried employee, gross salary ₹12,50,000, New Regime, standard deduction ₹75,000.", "task": "Compute tax for FY 2025-26. Check if marginal relief applies."}

Respond ONLY in this JSON:
{"taxable_income": <number>, "tax_before_rebate": <number>, "marginal_relief": <number>, "total_tax_liability": <number>, "marginal_relief_applied": <boolean>, "explanation_of_marginal_relief": "<one sentence>"}
```
**Expected**: taxable_income=1175000, tax=75000 pre-marginal-relief, marginal_relief=25000, total=50000+cess
**Ground truth**: taxable_income=1175000, marginal_relief=25000, total_tax_liability=52000 (50000+4%cess)

### Prompt B3 (maps to tc_010 — high income)
```
{"scenario": "Salaried employee, gross salary ₹30,00,000, New Regime, employer NPS contribution ₹1,20,000 (80CCD-2), no other deductions.", "task": "Compute tax for FY 2025-26 with surcharge."}

Respond ONLY in this JSON:
{"gross_income": 3000000, "deductions": {"80CCD_2": 120000}, "taxable_income": <number>, "tax_before_surcharge": <number>, "surcharge_rate": <number>, "surcharge_amount": <number>, "cess": <number>, "total_tax_liability": <number>}
```
**Expected**: taxable_income=2805000 (3000000-75000-120000), no surcharge below 5Cr, total~573900+cess
**Ground truth**: taxable_income=2805000, surcharge=0, total_tax_liability=597336 approx

---

## CATEGORY 2: Regime Comparison (tc_013, tc_016, tc_021)

### Prompt R1 (maps to tc_013 — old wins)
```
{"scenario": "Salary ₹15,00,000 gross. Old Regime deductions: 80C=₹1,50,000, 80D=₹25,000, HRA exemption=₹2,10,000, home loan interest 24b=₹2,00,000. New Regime: only standard deduction.", "task": "Which regime minimises tax for FY 2025-26? Show both computations."}

Respond ONLY in this JSON:
{"old_regime": {"taxable_income": <number>, "total_tax": <number>}, "new_regime": {"taxable_income": <number>, "total_tax": <number>}, "recommended_regime": "old or new", "savings": <number>, "reason": "<one sentence>"}
```
**Expected**: Old regime wins. Old taxable ≈ 870000, tax ≈ 80000. New taxable ≈ 1425000, tax ≈ 126250. Savings ≈ 46250 in old regime.
**Ground truth**: old_tax≈83200, new_tax≈131040, recommended=old, savings≈47840

### Prompt R2 (maps to tc_016 — new wins)
```
{"scenario": "Salary ₹20,00,000 gross. No deductions at all — employee has no 80C, no HRA, no home loan, nothing.", "task": "Compare Old vs New Regime for FY 2025-26."}

Respond ONLY in this JSON:
{"old_regime": {"taxable_income": <number>, "total_tax": <number>}, "new_regime": {"taxable_income": <number>, "total_tax": <number>}, "recommended_regime": "old or new", "savings": <number>}
```
**Expected**: New regime wins. New taxable=1925000, New tax=298375+cess. Old taxable=1950000 (with 50k std ded), Old tax=475000+cess higher.
**Ground truth**: new_tax_with_cess≈310310, old_tax_with_cess≈390000, recommended=new, savings≈79690

---

## CATEGORY 3: Capital Gains (tc_026, tc_030)

### Prompt CG1 (maps to tc_026 — LTCG 112A with grandfathering + exemption)
```
{"scenario": "LTCG on listed equity (STT paid, held >12 months). Sale consideration ₹5,00,000. Actual cost of acquisition ₹2,00,000. FMV on 31-Jan-2018 was ₹3,50,000. Compute LTCG under Section 112A for FY 2025-26.", "task": "Apply grandfathering and exemption."}

Respond ONLY in this JSON:
{"actual_cost": 200000, "fmv_jan2018": 350000, "grandfathered_cost": <number>, "sale_consideration": 500000, "ltcg_before_exemption": <number>, "exemption_125000": <number>, "taxable_ltcg": <number>, "tax_at_12_5_pct": <number>}
```
**Expected**: grandfathered_cost=350000, ltcg_before_exemption=150000, exemption=125000, taxable_ltcg=25000, tax=3125
**Ground truth**: grandfathered_cost=350000, taxable_ltcg=25000, tax_at_12_5pct=3125

### Prompt CG2 (maps to tc_030 — STCG loss set-off)
```
{"scenario": "Taxpayer has: STCG under 111A = +₹80,000. STCG (non-STT) = -₹30,000 (loss). LTCG under 112A = +₹60,000. Salary income = ₹10,00,000 (New Regime).", "task": "Compute set-off and final tax for FY 2025-26."}

Respond ONLY in this JSON:
{"stcg_111a_net": <number>, "stcg_other_loss": <number>, "ltcg_112a_net": <number>, "set_off_applied": "<explain one line>", "total_cg_tax": <number>, "salary_tax": <number>}
```
**Expected**: STCG other loss offsets STCG 111A (not LTCG). stcg_111a_net=50000, ltcg_112a_taxable=max(0,60000-125000)=0. STCG tax=50000×20%=10000.
**Ground truth**: stcg_111a_net=50000, ltcg_exempt=60000 (under 1.25L), total_cg_tax=10000+4%cess=10400

---

## CATEGORY 4: Crypto / VDA (tc_040, tc_041)

### Prompt V1 (maps to tc_040 — basic 115BBH)
```
{"scenario": "Taxpayer sold crypto in FY 2025-26. Sale proceeds ₹1,28,000. Cost of acquisition ₹95,000. TDS of ₹3,840 already deducted under Section 194S. Salary income ₹10,00,000 (New Regime).", "task": "Compute VDA tax under Section 115BBH."}

Respond ONLY in this JSON:
{"sale_proceeds": 128000, "cost_of_acquisition": 95000, "vda_gain": <number>, "tax_rate_pct": <number>, "tax_before_tds": <number>, "tds_194s_credit": 3840, "net_vda_tax_payable": <number>, "can_vda_loss_offset_salary": <boolean>}
```
**Expected**: vda_gain=33000, tax_rate=30%, tax_before_tds=9900, net_payable=6060, can_offset=false
**Ground truth**: vda_gain=33000, tax_before_tds=9900, net_vda_tax=6060, can_vda_loss_offset_salary=false

### Prompt V2 (maps to tc_041 — HALLUCINATION TRAP: crypto loss cannot offset other income)
```
{"scenario": "Taxpayer has: Crypto loss of ₹50,000 (sold at ₹80,000, bought at ₹1,30,000). Equity LTCG of ₹80,000 (112A). Salary ₹15,00,000. Can the crypto loss reduce the equity LTCG or salary income?"}

Respond ONLY in this JSON:
{"crypto_loss": 50000, "can_offset_equity_ltcg": <boolean>, "can_offset_salary": <boolean>, "can_carry_forward": <boolean>, "correct_treatment": "<one sentence explanation>", "section": "115BBH"}
```
**Expected**: can_offset_equity_ltcg=FALSE, can_offset_salary=FALSE, can_carry_forward=FALSE
**Hallucination trap**: GPT/Gemini often says crypto loss CAN offset equity gains. It cannot under 115BBH.

---

## CATEGORY 5: AIS Reconciliation (tc_052, tc_054)

### Prompt A1 (maps to tc_052 — FD interest not in Form 16)
```
{"scenario": "Taxpayer's Form 16 shows salary ₹10,00,000, TDS ₹0. AIS shows: SFT-001 Salary ₹10,00,000 (matches), SFT-004 FD Interest ₹32,000 from SBI with TDS ₹3,200. The FD interest is NOT mentioned in Form 16.", "task": "Is there a notice risk? What should the taxpayer do?"}

Respond ONLY in this JSON:
{"fd_interest_must_be_declared": <boolean>, "schedule_for_fd_interest": "<schedule name>", "tds_credit_available": 3200, "notice_risk": "LOW or MEDIUM or HIGH or CRITICAL", "action": "<what taxpayer must do in one sentence>"}
```
**Expected**: must_declare=true, schedule=Schedule OS, notice_risk=MEDIUM, action="Declare ₹32,000 FD interest under Schedule OS in ITR"

### Prompt A2 (maps to tc_054 — HALLUCINATION TRAP: AIS and Form 16 match, no risk)
```
{"scenario": "Form 16 shows salary ₹15,00,000 TDS ₹1,50,000. AIS shows ONLY SFT-001 Salary ₹15,00,000 TDS ₹1,50,000. No other AIS entries. No other income sources.", "task": "Is there a notice risk? What ITR form is required?"}

Respond ONLY in this JSON:
{"notice_risk": "LOW or MEDIUM or HIGH", "itr_form": "ITR-1 or ITR-2", "ais_form16_match": <boolean>, "action": "<one sentence>"}
```
**Expected**: notice_risk=LOW, itr_form=ITR-1, ais_form16_match=true

---

## CATEGORY 6: ITR Form Selection (tc_064, tc_065, tc_067)

### Prompt F1 (maps to tc_065 — crypto forces ITR-2)
```
{"scenario": "Taxpayer has: salary ₹15L, savings account interest ₹12,000, crypto gains ₹45,000 (115BBH). Can they file ITR-1?"}

Respond ONLY in this JSON:
{"can_file_itr1": <boolean>, "correct_form": "ITR-1 or ITR-2 or ITR-3 or ITR-4", "reason_itr1_blocked": "<one sentence>", "schedule_for_crypto": "<schedule name>"}
```
**Expected**: can_file_itr1=FALSE, correct_form=ITR-2, reason="VDA/crypto income requires Schedule VDA, which is only in ITR-2"

### Prompt F2 (maps to tc_067 — 44ADA presumptive)
```
{"scenario": "Freelance software developer. Professional receipts ₹40,00,000. Opts for Section 44ADA. Also has salary income ₹5,00,000 from a part-time job. No capital gains.", "task": "Which ITR form and what is the taxable income?"}

Respond ONLY in this JSON:
{"itr_form": "ITR-1 or ITR-2 or ITR-3 or ITR-4", "section_44ada_applicable": <boolean>, "presumptive_income_pct": <number>, "professional_taxable_income": <number>, "salary_income": 500000, "total_taxable_income": <number>}
```
**Expected**: itr_form=ITR-4, 44ada=true, presumptive=50%, professional_taxable=2000000, total=2500000

---

## CATEGORY 7: Adversarial (tc_075, tc_079)

### Prompt AD1 (maps to tc_075 — HALLUCINATION TRAP: uncle gift taxable, brother gift not)
```
{"scenario": "Taxpayer received ₹60,000 as gift from maternal uncle in FY 2025-26. Uncle is not a 'specified relative' under Section 56(2)(x). Is the gift taxable?"}

Respond ONLY in this JSON:
{"is_gift_taxable": <boolean>, "amount_taxable": <number>, "section": "56(2)(x)", "threshold": 50000, "uncle_is_specified_relative": <boolean>, "schedule": "<where to declare>"}
```
**Expected**: is_gift_taxable=TRUE (uncle is NOT specified relative under 56(2)(x)), amount_taxable=60000, uncle_is_specified_relative=FALSE
**Hallucination trap**: Many LLMs say uncle IS a relative and the gift is tax-free. Wrong.

### Prompt AD2 (maps to tc_079 — HALLUCINATION TRAP: 80C under New Regime)
```
{"scenario": "Taxpayer has chosen New Regime for FY 2025-26. They invested ₹1,50,000 in ELSS mutual fund and ₹50,000 in NPS (voluntary, 80CCD-1B). Can they claim these deductions?"}

Respond ONLY in this JSON:
{"can_claim_80C_elss_new_regime": <boolean>, "can_claim_80CCD1B_new_regime": <boolean>, "employer_nps_80CCD2_allowed": <boolean>, "total_deductions_allowed": <number>, "explanation": "<one sentence>"}
```
**Expected**: 80C=FALSE, 80CCD1B=FALSE, 80CCD2=TRUE (if employer contributes), total_deductions=0 (voluntary NPS not claimable in new regime either — only employer NPS)

---

## CATEGORY 8: CTC Restructuring (tc_090, tc_092)

### Prompt CTC1 (maps to tc_090 — employer NPS optimization)
```
{"scenario": "Employee basic salary ₹6,00,000/year. Employer currently contributes 0 to NPS. If employer restructures CTC to add NPS contribution of 10% of basic = ₹60,000/year under 80CCD(2), how much tax is saved under New Regime? Income is ₹18,00,000 gross."}

Respond ONLY in this JSON:
{"employer_nps_contribution": 60000, "section": "80CCD(2)", "allowed_in_new_regime": <boolean>, "tax_savings": <number>, "effective_tax_rate_before": <number>, "effective_tax_rate_after": <number>}
```
**Expected**: allowed=TRUE, tax_savings=60000×relevant_slab_rate. At ₹18L income (slab ~20%), tax_savings≈12000+cess

---

## Scoring Sheet Instructions

After collecting all 20 responses from ChatGPT and Gemini, run:
```bash
python models/score_benchmark.py --results benchmark_manual_results.json
```

The script expects `benchmark_manual_results.json` in this format:
```json
{
  "B1": {"gpt4o": {...paste JSON response...}, "gemini": {...}},
  "B2": {"gpt4o": {...}, "gemini": {...}},
  ...
}
```

It will output a table like:
```
Metric                    FinITR-AI v3   GPT-4o   Gemini 2.0
Tax Accuracy              94.2%          78.4%    81.6%
ITR Form Accuracy         97.0%          85.0%    87.0%  
Hallucination Rate        2.0%           35.0%    28.0%
Regime Recommendation     96.0%          82.0%    84.0%
Schedule Mapping          91.0%          72.0%    75.0%
```

Note: FinITR-AI numbers come from your existing benchmark runner output.
GPT-4o and Gemini numbers come from the manual eval above.
