"""
optimizer_agent.py — OptimizerAgent: Tax Regime Optimization & CTC Strategy.

Takes the reconciled income picture from AuditorAgent and:
1. Computes tax under Old Regime (with all applicable deductions)
2. Computes tax under New Regime (FY 25-26 slabs + marginal relief)
3. Recommends the optimal regime with exact savings
4. Generates CTC restructuring strategy (employer NPS under 80CCD(2))
5. Respects critic feedback — if CriticAgent blocked a deduction claim,
   the optimizer re-runs without that deduction.

ALL arithmetic goes through CalculatorTool — never inline.
"""
from __future__ import annotations

from typing import Any

from .base import BaseAgent, AgentContext, AgentResult


class OptimizerAgent(BaseAgent):
    """Compares tax regimes and generates optimization strategies."""

    def __init__(self, tools: dict[str, Any] | None = None):
        super().__init__(
            name="OptimizerAgent",
            role="Compare Old vs New tax regime, recommend optimal regime, "
                 "and generate CTC restructuring strategy.",
            tools=tools or {},
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        """
        Steps:
            1. Gather all income components from ctx.reconciliation
            2. Gather all applicable deductions (from interview answers + documents)
            3. Compute Old Regime tax
            4. Compute New Regime tax (with marginal relief)
            5. Compare and recommend
            6. Generate CTC restructuring options
            7. If critic feedback exists, remove blocked deductions and re-compute
        """
        self._log("Starting regime optimization")
        warnings = []
        tools_called = ["calculator"]

        # Check for critic constraints from previous iteration
        blocked = self._get_blocked_claims(ctx)
        if blocked:
            self._log(f"Excluding blocked sections: {blocked}")

        # Gather deductions
        deductions = self._gather_deductions(ctx, blocked)

        # Old regime computation
        calculator = self.tools["calculator"]
        old_tax = calculator.calculate_old_regime_tax(
            ctx.gross_income, deductions["old_regime"]
        )

        # New regime computation
        new_tax = calculator.calculate_new_regime_tax(
            ctx.gross_income, deductions["new_regime"]
        )

        # Comparison
        comparison = self._compare_regimes(old_tax, new_tax)

        # CTC restructuring
        basic = ctx.basic_salary or ctx.form16_data.get("basic_salary", ctx.gross_income * 0.4)
        current_nps = ctx.employer_nps or ctx.form16_data.get("deductions_claimed", {}).get("80CCD_2", 0.0)
        ctc = calculator.calculate_ctc_restructure(
            ctx.gross_income, basic, current_nps
        )

        # LLM-generated strategy narrative
        strategy = self._generate_strategy_narrative(comparison, ctc, ctx)

        # Write directly to ctx
        ctx.regime_comparison = comparison
        ctx.ctc_strategy = {"computation": ctc, "narrative": strategy}

        return AgentResult(
            agent_name=self.name,
            status="success",
            output={
                "regime_comparison": comparison,
                "ctc_strategy": {"computation": ctc, "narrative": strategy},
            },
            reasoning=f"Regime comparison and CTC strategy generated. Recommended: {comparison['recommended']}.",
            tools_called=tools_called,
            warnings=warnings,
        )

    def _get_annual_rent(self, ctx: AgentContext) -> float:
        """Calculate total rent paid from bank transactions matching RENT_KEYWORDS."""
        import re
        RENT_KEYWORDS = re.compile(r'RENT|LANDLORD', re.IGNORECASE)
        total_rent = 0.0
        for txn in ctx.bank_transactions:
            txn_type = txn.get("transaction_type", "").lower()
            desc = txn.get("description", "")
            if txn_type == "debit" and RENT_KEYWORDS.search(desc):
                total_rent += txn.get("amount", 0.0)
        return total_rent

    def _gather_deductions(self, ctx: AgentContext, blocked: set) -> dict:
        """Gather applicable deductions for each regime.

        Old Regime: 80C, 80D, 80CCD(1B), 80CCD(2), HRA, LTA, 24b, etc.
        New Regime: Standard Deduction (75k), 80CCD(2), 80CCH, Family Pension only.
        """
        # HRA Calculation
        basic_salary = ctx.basic_salary or ctx.form16_data.get("basic_salary", 0.0)
        if not basic_salary:
            basic_salary = ctx.gross_income * 0.40
            
        hra_received = ctx.form16_data.get("hra_received", 0.0)
        rent_paid = self._get_annual_rent(ctx)
        
        calculator = self.tools["calculator"]
        hra_exemption = calculator._compute_hra_exemption(
            basic_salary=basic_salary,
            hra_received=hra_received,
            rent_paid=rent_paid,
            metro=True
        )

        employer_nps = ctx.employer_nps or ctx.form16_data.get("deductions_claimed", {}).get("80CCD_2", 0.0) or ctx.interview_answers.get("80CCD_2", 0.0) or ctx.interview_answers.get("80CCD(2)", 0.0)

        # Gather deductions for Old Regime
        old_regime = {
            "80C": float(ctx.interview_answers.get("80C", 0.0)),
            "80CCD_1B": float(ctx.interview_answers.get("80CCD_1B", 0.0) or ctx.interview_answers.get("80CCD(1B)", 0.0)),
            "80CCD_2": float(employer_nps),
            "80D": float(ctx.interview_answers.get("80D", 0.0)),
            "80E": float(ctx.interview_answers.get("80E", 0.0)),
            "80G": float(ctx.interview_answers.get("80G", 0.0)),
            "80TTA": float(ctx.interview_answers.get("80TTA", 0.0)),
            "24b": float(ctx.interview_answers.get("24b", 0.0) or ctx.interview_answers.get("24(b)", 0.0)),
            "HRA": float(hra_exemption),
            "LTA": float(ctx.interview_answers.get("LTA", 0.0) or ctx.form16_data.get("lta", 0.0)),
        }

        # Filter out blocked sections for Old Regime
        for section in list(old_regime.keys()):
            is_blocked = False
            if section in blocked:
                is_blocked = True
            elif section == "80CCD_2" and ("80CCD(2)" in blocked or "80CCD_2" in blocked):
                is_blocked = True
            elif section == "80CCD_1B" and ("80CCD(1B)" in blocked or "80CCD_1B" in blocked):
                is_blocked = True
            elif section == "24b" and ("24(b)" in blocked or "24b" in blocked):
                is_blocked = True
            elif section == "HRA" and ("10(13A)" in blocked or "HRA" in blocked):
                is_blocked = True
                
            if is_blocked:
                old_regime[section] = 0.0

        # Gather deductions for New Regime
        new_regime = {
            "80CCD_2": float(employer_nps),
            "80CCH": float(ctx.interview_answers.get("80CCH", 0.0)),
        }

        # Filter out blocked sections for New Regime
        for section in list(new_regime.keys()):
            is_blocked = False
            if section in blocked:
                is_blocked = True
            elif section == "80CCD_2" and ("80CCD(2)" in blocked or "80CCD_2" in blocked):
                is_blocked = True
            elif section == "80CCH" and ("80CCH" in blocked):
                is_blocked = True
                
            if is_blocked:
                new_regime[section] = 0.0

        return {
            "old_regime": old_regime,
            "new_regime": new_regime,
        }

    def _compare_regimes(self, old_tax: dict, new_tax: dict) -> dict:
        """Side-by-side comparison with verdict.

        Returns:
            {
                "old_regime": old_tax,
                "new_regime": new_tax,
                "recommended": "old" | "new",
                "savings": float,
                "reason": str,
            }
        """
        old_liability = old_tax.get("total_tax_liability", 0.0)
        new_liability = new_tax.get("total_tax_liability", 0.0)

        if old_liability <= new_liability:
            recommended = "old"
            savings = round(new_liability - old_liability, 2)
            reason = f"Old Regime saves ₹{savings:,.0f} due to claiming deductions (HRA, 80C, etc.)"
        else:
            recommended = "new"
            savings = round(old_liability - new_liability, 2)
            reason = f"New Regime saves ₹{savings:,.0f} despite losing HRA and 80C deductions"

        return {
            "old_regime": old_tax,
            "new_regime": new_tax,
            "recommended": recommended,
            "savings": savings,
            "reason": reason,
        }

    def _generate_strategy_narrative(self, comparison: dict, ctc: dict, ctx: AgentContext) -> str:
        """Use LLM to generate human-readable strategy explanation.

        Routes arithmetic through calculator. CriticAgent will verify.
        """
        old_tax = comparison["old_regime"]["total_tax_liability"]
        new_tax = comparison["new_regime"]["total_tax_liability"]
        recommended = comparison["recommended"]
        savings = comparison["savings"]
        ctc_savings = ctc.get("annual_savings", 0.0)

        rec_name = "New Regime" if recommended == "new" else "Old Regime"

        if recommended == "new":
            sections_to_reference = "Section 115BAC or Section 80CCD(2)"
        else:
            sections_to_reference = "Section 80C, Section 80CCD(2), or HRA"

        prompt = (
            f"You are an Indian tax advisor. Given this comparison:\n"
            f"- Old Regime tax: Rs {old_tax:,.2f} | New Regime tax: Rs {new_tax:,.2f}\n"
            f"- Savings under {rec_name}: Rs {savings:,.2f}\n"
            f"- CTC restructuring potential: Rs {ctc_savings:,.2f}\n\n"
            f"Write a 3-4 sentence strategy recommendation. DO NOT compute any numbers — "
            f"all numbers are pre-computed and correct. Reference specific sections like {sections_to_reference}."
        )

        try:
            from tools.ollama_client import chat as llm_chat, get_model_name
            model_name = get_model_name()
            self._log(f"Calling Ollama with model: {model_name}")
            narrative = llm_chat(prompt=prompt, model=model_name)
            if narrative:
                return narrative
        except Exception as e:
            self._log(f"Ollama call failed or unavailable ({e}). Using fallback template.")

        if recommended == "new":
            strategy = (
                f"We recommend choosing the New Tax Regime (Section 115BAC) for this financial year, "
                f"as it results in a lower tax liability of Rs {new_tax:,.2f}, saving you Rs {savings:,.2f} "
                f"compared to the Old Regime (Rs {old_tax:,.2f}). "
            )
        else:
            strategy = (
                f"We recommend choosing the Old Tax Regime for this financial year. "
                f"It results in a lower tax liability of Rs {old_tax:,.2f}, saving you Rs {savings:,.2f} "
                f"compared to the New Regime (Rs {new_tax:,.2f}), primarily due to your high deductions (HRA, Section 80C, etc.). "
            )

        if ctc_savings > 0:
            strategy += (
                f"Furthermore, you can achieve additional annual savings of Rs {ctc_savings:,.2f} under Section 80CCD(2) "
                f"by requesting your employer to restructure your CTC to maximize employer NPS contributions."
            )
        else:
            strategy += (
                "Your employer NPS contributions are already optimized, and no further CTC restructuring is required."
            )

        return strategy

    def _get_blocked_claims(self, ctx: AgentContext) -> set:
        """Extract deduction claims blocked by CriticAgent."""
        blocked = set()
        for fb in ctx.critic_feedback:
            for claim in fb.get("blocked_claims", []):
                blocked.add(claim.get("section", ""))
        return blocked
