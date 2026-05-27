# Goal Description

The user observed a 2% hallucination rate in the FinITR-AI v3 system and requested a fix to bring it down to "next to zero" along with rerunning the ablation evaluation to generate updated graphs. Additionally, the user asked what hallucination rate means and whether a high rate is good or bad.

## Answer to User's Question
**What does Hallucination rate mean?** 
In this system, hallucination rate measures how often the AI proposes or mentions tax deductions that are legally disallowed (e.g., claiming Section 80C or HRA deductions while under the New Tax Regime where they are banned) or proposes non-existent tax sections. 

**Is a high hallucination rate good or bad?**
A **HIGH hallucination rate is BAD**. It means the system is giving factually incorrect or illegal tax advice. We want this rate to be as close to zero as possible.

## Root Cause Analysis
The 2% hallucination rate is primarily caused by a false positive in the `CriticAgent`. 
1. The `OptimizerAgent` writes a narrative explaining its regime choice. The LLM is explicitly prompted to "Reference specific sections like Section 115BAC, Section 80C...".
2. When the LLM correctly explains why it chose the New Regime (e.g., "New Regime saves you ₹10,000 despite losing Section 80C deductions"), the `CriticAgent` parses the text, finds "80C", categorizes it as a `legal_reference` claim, and immediately blocks it because 80C is not allowed under the New Regime.
3. The evaluation metric (`evaluation/metrics.py`) treats any blocked claim by the CriticAgent as a hallucination.

## User Review Required
No major architectural changes required. The fix involves adjusting how the CriticAgent interprets text mentions vs. actual numerical deduction claims.

## Open Questions
None.

## Proposed Changes

### `agents/critic_agent.py`
Modify `_is_wrong_regime_deduction` to only block claims of type `deduction_eligibility`. Mere text references (`legal_reference`) in the explanation narrative should not be flagged as illegal claims.

#### [MODIFY] critic_agent.py
- Change `if claim.get("type") not in ("deduction_eligibility", "legal_reference"):` to `if claim.get("type") != "deduction_eligibility":` in the `_is_wrong_regime_deduction` method.

### `agents/optimizer_agent.py`
Refine the LLM prompt so it doesn't force the LLM to mention Section 80C if it's recommending the New Regime, reducing the chance of spurious legal references.

#### [MODIFY] optimizer_agent.py
- Update the prompt generation logic to only ask the LLM to reference relevant sections (e.g., 115BAC for New Regime, 80C/HRA for Old Regime) instead of always prompting for 80C.

## Verification Plan

### Automated Tests
1. Run the IndianTaxBench ablation study (`python -m evaluation.ablation`).
2. Run the benchmarking graph script (`python -m benchmarks.indian_tax_bench.score_benchmark`) to regenerate `evaluation/results/comparison_metrics.png`.
3. Verify that the hallucination rate in the full system drops from 2% to 0%.
