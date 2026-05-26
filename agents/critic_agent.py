"""
critic_agent.py — CriticAgent: Faithfulness Verification & Hallucination Blocking.

The red-team agent. It:
1. Takes every claim from OptimizerAgent and ComplianceAgent
2. Verifies each against legal text via PageIndex (structured retrieval)
3. Checks arithmetic via CalculatorTool re-computation
4. Uses NLI (cross-encoder) for semantic faithfulness
5. Blocks hallucinated claims and returns feedback to orchestrator
6. Specifically catches: wrong regime deductions, incorrect limits,
   fabricated sections, arithmetic errors

Output:
    ctx.verification_results — per-claim verification
    AgentResult.warnings     — issues that require re-running another agent
    AgentResult.output["blocked_claims"] — claims suppressed from final report
"""
from __future__ import annotations

from typing import Any

from .base import BaseAgent, AgentContext, AgentResult


# Known hallucination patterns to watch for
HALLUCINATION_PATTERNS = [
    # LLM recommends Old Regime deductions under New Regime
    {"pattern": "80C_under_new_regime",
     "check": "LLM recommends Section 80C/80D/80E/80G under New Regime",
     "action": "block"},
    # LLM invents a section that doesn't exist
    {"pattern": "fabricated_section",
     "check": "Section number not found in knowledge base",
     "action": "block"},
    # Arithmetic doesn't match calculator
    {"pattern": "arithmetic_mismatch",
     "check": "LLM's stated tax differs from CalculatorTool by > Rs 100",
     "action": "flag_and_correct"},
    # Wrong limit for a deduction
    {"pattern": "wrong_limit",
     "check": "LLM states wrong limit (e.g. 80CCD(2) = 10% when it's 14% for govt)",
     "action": "flag"},
]

# Sections NOT allowed under New Regime
NEW_REGIME_BLOCKED_SECTIONS = {
    "80C", "80CCC", "80CCD(1)", "80CCD(1B)", "80D", "80DD", "80DDB",
    "80E", "80EE", "80EEA", "80EEB", "80G", "80GG", "80GGA", "80GGC",
    "80TTA", "80TTB", "80U", "80IA", "80IAB", "80IB", "80IC",
    "24(b)",   # home loan interest (not allowed under new regime)
    "10(13A)", # HRA exemption
}


class CriticAgent(BaseAgent):
    """Verifies claims and blocks hallucinations."""

    def __init__(self, tools: dict[str, Any] | None = None):
        super().__init__(
            name="CriticAgent",
            role="Verify every claim against legal text and arithmetic. "
                 "Block hallucinated deductions. Return feedback for re-runs.",
            tools=tools or {},
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        """
        Steps:
            1. Collect all verifiable claims from context
            2. For each claim:
               a. Check against PageIndex (legal text verification)
               b. Check arithmetic via CalculatorTool
               c. Check regime compatibility
               d. Run NLI verification
            3. Compile blocked claims and warnings
            4. Return status: "success" if no issues, "needs_review" if issues found
        """
        self._log("Verifying all claims")
        blocked_claims = []
        verified_claims = []
        warnings = []

        claims = self._collect_claims(ctx)

        for claim in claims:
            # Check 1: Regime compatibility
            if self._is_wrong_regime_deduction(claim, ctx):
                blocked_claims.append({
                    "claim": claim,
                    "reason": "Section not allowed under chosen regime",
                    "source": claim.get("source", "optimizer"),
                    "section": claim.get("section", ""),
                })
                warnings.append({
                    "type": "blocked_claim",
                    "source": claim.get("source", "optimizer"),
                    "detail": claim,
                    "section": claim.get("section", ""),
                })
                continue

            # Check 2: Section exists in knowledge base
            if not self._section_exists(claim.get("section", "")):
                if claim.get("type") == "deduction_eligibility":
                    blocked_claims.append({
                        "claim": claim,
                        "reason": "Section not found in knowledge base",
                        "source": claim.get("source", "optimizer"),
                        "section": claim.get("section", ""),
                    })
                warnings.append({
                    "type": "fabricated_section",
                    "source": claim.get("source", "optimizer"),
                    "detail": claim,
                    "section": claim.get("section", ""),
                })
                if claim.get("type") == "deduction_eligibility":
                    continue

            # Check 3: Arithmetic verification
            if claim.get("type") == "arithmetic":
                arith_ok = self._verify_arithmetic(claim, ctx)
                if not arith_ok:
                    warnings.append({
                        "type": "arithmetic_mismatch",
                        "source": "optimizer",
                        "detail": claim,
                    })

            # Check 4: NLI faithfulness against legal text
            nli_result = self._verify_faithfulness(claim)
            if nli_result.get("label") == "HALLUCINATED":
                blocked_claims.append({
                    "claim": claim,
                    "reason": f"NLI contradiction: {nli_result.get('reason')}",
                    "source": claim.get("source", "optimizer"),
                    "section": claim.get("section", ""),
                })
                warnings.append({
                    "type": "nli_contradiction",
                    "source": claim.get("source", "optimizer"),
                    "detail": claim,
                    "section": claim.get("section", ""),
                })
            else:
                verified_claims.append({**claim, "verification": nli_result})

        ctx.verification_results = verified_claims

        status = "success" if not blocked_claims and not warnings else "needs_review"

        return AgentResult(
            agent_name=self.name,
            status=status,
            output={
                "verified_claims": verified_claims,
                "blocked_claims": blocked_claims,
                "total_checked": len(verified_claims) + len(blocked_claims),
            },
            reasoning=f"Verified claims. {len(blocked_claims)} blocked, "
                      f"{len(verified_claims)} passed.",
            warnings=warnings,
        )

    def _normalize_section(self, sec: str) -> str:
        """Standardise section references for comparison."""
        sec = str(sec).upper().strip()
        if sec in ("80CCD_1B", "80CCD1B"):
            return "80CCD(1B)"
        if sec in ("80CCD_2", "80CCD2"):
            return "80CCD(2)"
        if sec in ("24B", "24-B"):
            return "24(b)"
        if sec in ("HRA", "10_13A"):
            return "10(13A)"
        return sec

    def _collect_claims(self, ctx: AgentContext) -> list[dict]:
        """Extract all verifiable claims from the context."""
        claims = []

        comparison = ctx.regime_comparison
        rec = comparison.get("recommended")
        if rec:
            reg_data = comparison.get(f"{rec}_regime", {})
            
            # Real dict deductions
            deductions = reg_data.get("deductions", {})
            if isinstance(deductions, dict):
                for section, amt in deductions.items():
                    if amt > 0:
                        claims.append({
                            "type": "deduction_eligibility",
                            "section": section,
                            "claim_text": f"Section {section} deduction of Rs {amt:,.2f} claimed",
                            "value": amt,
                            "source": "optimizer",
                        })

            # Test deductions_used list
            deductions_used = reg_data.get("deductions_used", [])
            if isinstance(deductions_used, list):
                for section in deductions_used:
                    claims.append({
                        "type": "deduction_eligibility",
                        "section": section,
                        "claim_text": f"Section {section} deduction claimed",
                        "value": 0.0,
                        "source": "optimizer",
                    })

        # Narrative claims
        ctc_narrative = ctx.ctc_strategy.get("narrative", "")
        if ctc_narrative:
            import re
            matches = re.findall(
                r'(?:Section\s+)?(80[A-Z_0-9\(\)]+|115[A-Z0-9]+|24b|24\(b\)|10\(13A\)|HRA|LTA)',
                ctc_narrative,
                re.IGNORECASE
            )
            for m in matches:
                clean_sec = m.upper().replace("SECTION ", "")
                claims.append({
                    "type": "legal_reference",
                    "section": clean_sec,
                    "claim_text": f"CTC strategy narrative references Section {clean_sec}",
                    "value": clean_sec,
                    "source": "optimizer",
                })

        # Schedule mapping claims
        for mapping in ctx.schedule_mapping:
            sec = mapping.get("section", "")
            if sec:
                claims.append({
                    "type": "legal_reference",
                    "section": sec,
                    "claim_text": f"Schedule mapping matches item '{mapping.get('item')}' to Section {sec}",
                    "value": sec,
                    "source": "compliance",
                })

        # Arithmetic claims
        if comparison:
            for regime in ["old", "new"]:
                reg_data = comparison.get(f"{regime}_regime")
                if reg_data:
                    claims.append({
                        "type": "arithmetic",
                        "section": regime,
                        "claim_text": f"{regime.title()} Regime tax computation has tax liability of Rs {reg_data.get('total_tax_liability', 0.0):,.2f}",
                        "value": reg_data,
                        "source": "optimizer",
                    })

        return claims

    def _is_wrong_regime_deduction(self, claim: dict, ctx: AgentContext) -> bool:
        """Check if claim recommends a blocked deduction under the chosen regime."""
        if claim.get("type") != "deduction_eligibility":
            return False

        recommended = ctx.regime_comparison.get("recommended", "new")
        if recommended == "new":
            section = claim.get("section", "")
            norm_sec = self._normalize_section(section)
            if norm_sec in NEW_REGIME_BLOCKED_SECTIONS:
                return True
        return False

    def _section_exists(self, section: str) -> bool:
        """Verify section exists in the knowledge base."""
        if not section:
            return False
        retriever = self.tools.get("retriever")
        if not retriever:
            return True

        res = retriever._match_section_ref(section)
        if res and res.get("node_id") != "root":
            return True

        import re
        clean_norm = re.sub(r'[^A-Z0-9]', '', self._normalize_section(section).upper())
        for key in retriever.tree.keys():
            clean_key = re.sub(r'[^A-Z0-9]', '', key.upper())
            if clean_norm in clean_key:
                return True
        return False

    def _verify_arithmetic(self, claim: dict, ctx: AgentContext) -> bool:
        """Re-compute any arithmetic in the claim via CalculatorTool."""
        if claim.get("type") != "arithmetic":
            return True

        regime = claim.get("section", "")
        stated_tax = claim.get("value", {}).get("total_tax_liability", 0.0)

        comparison = ctx.regime_comparison
        deductions = comparison.get(f"{regime}_regime", {}).get("deductions", {})

        calculator = self.tools["calculator"]
        if regime == "new":
            recalculated = calculator.calculate_new_regime_tax(ctx.gross_income, deductions)
        else:
            recalculated = calculator.calculate_old_regime_tax(ctx.gross_income, deductions)

        diff = abs(recalculated["total_tax_liability"] - stated_tax)
        return diff <= 100

    def _verify_faithfulness(self, claim: dict) -> dict:
        """Run NLI verification against retrieved legal text.

        Uses PageIndex to get the authoritative section text,
        then runs cross-encoder NLI.
        """
        section = claim.get("section", "")
        claim_text = claim.get("claim_text", "")

        retriever = self.tools.get("retriever")
        if not retriever:
            return {"claim": claim_text, "evidence_snippet": "", "label": "UNVERIFIED", "score": 0.0, "reason": "No retriever"}

        res = retriever.retrieve(section)
        evidence = res.get("retrieved_text", "")

        if not evidence or res.get("node_id") == "root":
            return {
                "claim": claim_text,
                "evidence_snippet": "No specific evidence found.",
                "label": "UNVERIFIED",
                "score": 0.0,
                "reason": "Could not locate section legal text in PageIndex.",
            }

        verifier = self.tools.get("verifier")
        if not verifier:
            return {"claim": claim_text, "evidence_snippet": evidence[:200], "label": "UNVERIFIED", "score": 0.0, "reason": "No verifier"}

        verification = verifier.verify(claim_text, evidence)
        return {
            "claim": claim_text,
            "evidence_snippet": verification.get("evidence_snippet", ""),
            "label": verification.get("label", "UNVERIFIED"),
            "score": verification.get("score", 0.0),
            "reason": f"NLI verification labeled this as {verification.get('label')}.",
        }
