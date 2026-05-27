# Week 2: Multi-Agent Architecture + Critic Loop

## Goal
By end of week 2, all 4 agents run via the orchestrator with a REAL feedback loop:
CriticAgent catches a hallucination → orchestrator re-runs OptimizerAgent → CriticAgent approves on second pass.

```bash
python -m agents.orchestrator \
    --bank data/synthetic/sample_bank_statement.csv \
    --ais data/synthetic/sample_ais.json \
    --form16 data/synthetic/sample_form16.json \
    --income 2200000 \
    --output outputs/week2_test.json
```

The output JSON should show `"iterations": 2` (meaning the critic triggered a re-run).

---

## Task 2.1: Implement OptimizerAgent (Day 1-2)

**File**: `agents/optimizer_agent.py`

### _gather_deductions()
Read from ctx.interview_answers and ctx.form16_data to build deduction dicts:

```python
old_regime_deductions = {
    "80C": min(ctx.interview_answers.get("80C", 0), 150000),
    "80D": min(ctx.interview_answers.get("80D", 0), 25000),
    "80CCD_2": ctx.employer_nps,  # from Form 16 or interview
    "HRA": calculator._compute_hra_exemption(
        basic=ctx.basic_salary,
        hra_received=ctx.form16_data.get("hra_received", 0),
        rent_paid=self._get_annual_rent(ctx),  # from bank statement detection
    ),
    # ... etc
}
new_regime_deductions = {
    "80CCD_2": ctx.employer_nps,
    "80CCH": ctx.interview_answers.get("80CCH", 0),
}
```

### _compare_regimes()
Call calculator for both regimes, produce side-by-side comparison:
```python
{
    "old_regime": {"taxable_income": X, "tax_liability": Y, "effective_rate": Z%},
    "new_regime": {"taxable_income": X, "tax_liability": Y, "effective_rate": Z%, "marginal_relief": M},
    "recommended": "new",  # or "old"
    "savings": 53928,
    "reason": "New Regime saves ₹53,928 despite losing HRA and 80C deductions",
}
```

### _generate_strategy_narrative()
Call Ollama LLM with a structured prompt. The LLM generates a 3-4 sentence strategy.
CRITICAL: Any number in the prompt must come from CalculatorTool, NOT from the LLM.

Template:
```
You are an Indian tax advisor. Given this comparison:
- Old Regime tax: ₹{old_tax} | New Regime tax: ₹{new_tax}
- Savings under {recommended}: ₹{savings}
- CTC restructuring potential: {ctc_savings}

Write a 3-4 sentence strategy recommendation. DO NOT compute any numbers — 
all numbers are pre-computed and correct. Reference specific sections.
```

If Ollama unavailable, use a template string (like v2's fallback).

**Write to ctx**:
```python
ctx.regime_comparison = comparison
ctx.ctc_strategy = {"computation": ctc_result, "narrative": strategy_text}
```

---

## Task 2.2: Implement ComplianceAgent (Day 2-3)

**File**: `agents/compliance_agent.py`

### _classify_income_types()
Scan ctx.reconciliation ledger and ctx.anomalies for all income types present:
```python
income_types = set()
for item in ctx.reconciliation.get("ledger", []):
    if item.get("itr_schedule") == "Schedule CG":
        income_types.add("capital_gains")
    if item.get("itr_schedule") == "Schedule VDA":
        income_types.add("crypto_vda")
    # ... etc
```

### _determine_itr_form()
Apply ITR_FORM_RULES from the skeleton:
- Start with ITR-1
- Check each blocker — if any blocker is present, eliminate that form
- Move to next form
- Result: the simplest form the user is eligible for

For the synthetic test data, result should be ITR-2 (because capital gains + crypto).

### _map_to_schedules()
For each income item in the reconciled ledger, assign:
```python
{
    "item": "Crypto gains - WazirX",
    "amount": 33000,  # from interview (sale 128000 - cost 95000)
    "schedule": "Schedule VDA",
    "section": "115BBH",
    "line_hint": "Part A → Virtual Digital Asset → Sl. No. 1",
    "source": "ais + interview",
    "tds_credit": 3840,
    "tds_section": "194S",
}
```

Use SCHEDULE_MAP from the skeleton.

---

## Task 2.3: Implement CriticAgent (Day 3-4)

**File**: `agents/critic_agent.py`

This is the agent that makes the project "agentic." It must:

### _collect_claims()
Scan ctx for all verifiable claims:
- From regime_comparison: "New regime saves ₹X" → verify arithmetic
- From ctc_strategy.narrative: extract section references → verify existence
- From schedule_mapping: each section reference → verify it's real

### _is_wrong_regime_deduction()
Check if any deduction in the optimizer's output is blocked under the chosen regime:
```python
if ctx.regime_comparison.get("recommended") == "new":
    for section in deductions_used:
        if section in NEW_REGIME_BLOCKED_SECTIONS:
            return True  # HALLUCINATION: 80C under New Regime
```

### _verify_arithmetic()
Re-compute the tax using CalculatorTool and compare:
```python
recalculated = calculator.calculate_new_regime_tax(ctx.gross_income, deductions)
stated = ctx.regime_comparison["new_regime"]["tax_liability"]
if abs(recalculated["total_tax_liability"] - stated) > 100:
    return False  # arithmetic mismatch
```

### _verify_faithfulness()
For each section citation:
1. Retrieve section text via PageIndex
2. Run NLI verification (claim vs retrieved text)
3. Return FAITHFUL / UNVERIFIED / HALLUCINATED

### Critical: Create a deliberate hallucination test

To demonstrate the feedback loop, create a test fixture where the LLM is likely to hallucinate. For example, prompt it with a scenario where Old Regime deductions look tempting but the user chose New Regime. A good LLM will sometimes slip and recommend 80C anyway. The CriticAgent must catch this.

If the LLM doesn't hallucinate naturally (which is possible with a well-prompted qwen2.5), you can create a synthetic test in `tests/test_critic_loop.py`:

```python
def test_critic_catches_wrong_regime():
    """Simulate a hallucination and verify critic catches it."""
    ctx = AgentContext(gross_income=1500000)
    ctx.regime_comparison = {
        "recommended": "new",
        "new_regime": {"deductions_used": ["80C", "80CCD(2)"]}  # 80C is WRONG here
    }
    critic = CriticAgent()
    result = critic.run(ctx)
    assert result.status == "needs_review"
    assert any("80C" in str(c) for c in result.output["blocked_claims"])
```

---

## Task 2.4: Wire Orchestrator Feedback Loop (Day 4-5)

**File**: `agents/orchestrator.py`

Implement `_apply_result()` for all agents — map output fields to context.

Make the feedback loop work:
1. After critic returns "needs_review", record the blocked claims in ctx.critic_feedback
2. On next iteration, `_should_rerun()` checks which agent needs re-running
3. OptimizerAgent's `_get_blocked_claims()` reads critic feedback and excludes blocked sections
4. Re-run optimizer → re-run critic → critic says "success" → finalize

The log output should show:
```
[ORCHESTRATOR] Iteration 1/3
[ORCHESTRATOR] Running AuditorAgent
[AuditorAgent] Starting multi-document reconciliation
[ORCHESTRATOR] Running OptimizerAgent
[OptimizerAgent] Starting regime optimization
[ORCHESTRATOR] Running ComplianceAgent
[ComplianceAgent] Determining ITR form and schedule mapping
[ORCHESTRATOR] Running CriticAgent
[CriticAgent] Verifying all claims
[CriticAgent] BLOCKED: Section 80C not allowed under New Regime
[ORCHESTRATOR] CriticAgent raised 1 issues — re-running flagged agents
[ORCHESTRATOR] Iteration 2/3
[ORCHESTRATOR] Running OptimizerAgent
[OptimizerAgent] Excluding blocked sections: {80C}
[ORCHESTRATOR] Running CriticAgent
[CriticAgent] All claims verified
[ORCHESTRATOR] CriticAgent satisfied — finalizing report
[ORCHESTRATOR] Pipeline complete in 12.3s
```

---

## Task 2.5: Basic Streamlit Wiring (Day 5)

**File**: `frontend/app.py`

Create a minimal Streamlit app that:
1. Sidebar: file uploaders for Bank CSV, AIS JSON, Form 16 JSON
2. Sidebar: income input, "Run Pipeline" button
3. Tab 1 — Dashboard: risk score gauge (plotly), reconciliation table
4. Tab 2 — ITR Assist: interview questions from AuditorAgent
5. Tab 3 — Regime Comparator: Old vs New side-by-side
6. Tab 4 — Report: JSON dump for now (CA Brief comes in Week 3)

Don't polish the UI — just get the data flowing. Pretty comes in Week 5.

---

## Week 2 Acceptance Criteria

- [ ] OptimizerAgent computes both Old and New regime tax correctly
- [ ] ComplianceAgent correctly recommends ITR-2 for the synthetic test case
- [ ] ComplianceAgent maps all income items to correct schedules
- [ ] CriticAgent catches at least one hallucination/error in a test
- [ ] Orchestrator feedback loop runs 2+ iterations when critic finds issues
- [ ] Orchestrator feedback loop terminates at 1 iteration when everything is clean
- [ ] Agent trace in output JSON shows the full decision history
- [ ] Streamlit app renders all 4 tabs with real pipeline data
- [ ] `python -m pytest tests/test_critic_loop.py` passes
