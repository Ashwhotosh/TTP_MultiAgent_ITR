"""
calculator.py — Deterministic Tax Engine.

Supports BOTH Old and New Regime for FY 2025-26 (AY 2026-27).
All arithmetic is deterministic — NO LLM math.

Features:
    - New Regime tax (Section 115BAC) with marginal relief
    - Old Regime tax with full Chapter VI-A deductions
    - HRA exemption calculation (Section 10(13A))
    - Surcharge and cess for both regimes
    - Safe AST-based expression evaluator
    - CTC restructuring (employer NPS optimisation)
"""
from __future__ import annotations

import ast
import operator
from typing import Any


class CalculatorTool:
    """Safe arithmetic engine + dual-regime tax calculator."""

    # ── New Regime Slabs FY 2025-26 ──
    NEW_REGIME_SLABS = [
        (0,       400000,  0.00),
        (400001,  800000,  0.05),
        (800001,  1200000, 0.10),
        (1200001, 1600000, 0.15),
        (1600001, 2000000, 0.20),
        (2000001, 2400000, 0.25),
        (2400001, float('inf'), 0.30),
    ]

    # ── Old Regime Slabs FY 2025-26 ──
    OLD_REGIME_SLABS = [
        (0,       250000,  0.00),
        (250001,  500000,  0.05),
        (500001,  1000000, 0.20),
        (1000001, float('inf'), 0.30),
    ]

    NEW_REGIME_STANDARD_DEDUCTION = 75000
    OLD_REGIME_STANDARD_DEDUCTION = 50000

    # ── Rebate thresholds ──
    NEW_REGIME_REBATE_LIMIT = 1200000   # taxable income threshold
    NEW_REGIME_REBATE_MAX = 60000
    OLD_REGIME_REBATE_LIMIT = 500000
    OLD_REGIME_REBATE_MAX = 12500

    CESS_RATE = 0.04

    # ── Safe AST operators ──
    _SAFE_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    # ──────────────────── Safe Expression Evaluator ────────────────────

    def calculate(self, expression: str) -> dict[str, Any]:
        """Safely evaluate a mathematical expression using AST parsing.

        Args:
            expression: A mathematical expression string (e.g., '15*100000 - 75000')

        Returns:
            {"expression": str, "result": float, "error": None}
            or {"expression": str, "result": None, "error": str}
        """
        try:
            tree = ast.parse(expression, mode='eval')
            result = self._eval_node(tree.body)
            return {"expression": expression, "result": float(result), "error": None}
        except Exception as e:
            return {"expression": expression, "result": None, "error": str(e)}

    def _eval_node(self, node: ast.AST) -> float:
        """Recursively evaluate an AST node (safe — no exec/eval)."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            op_func = self._SAFE_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return op_func(left, right)
        elif isinstance(node, ast.UnaryOp):
            op_func = self._SAFE_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_func(self._eval_node(node.operand))
        else:
            raise ValueError(f"Unsupported AST node: {type(node).__name__}")

    # ──────────────────── Slab Computation Helper ────────────────────

    def _compute_slab_tax(self, taxable_income: float,
                          slabs: list[tuple]) -> tuple[float, list[dict]]:
        """Compute tax using given slab structure.

        Returns (total_tax, slab_breakdown).
        """
        total_tax = 0.0
        breakdown = []
        remaining = taxable_income

        for slab_min, slab_max, rate in slabs:
            if remaining <= 0:
                break
            slab_range = slab_max - slab_min + 1 if slab_max != float('inf') else remaining
            taxable_in_slab = min(remaining, slab_range)
            tax_in_slab = taxable_in_slab * rate
            total_tax += tax_in_slab
            breakdown.append({
                "slab": f"{slab_min:,.0f} - {slab_max:,.0f}" if slab_max != float('inf')
                        else f"{slab_min:,.0f}+",
                "rate": f"{rate*100:.0f}%",
                "taxable_amount": round(taxable_in_slab, 2),
                "tax": round(tax_in_slab, 2),
            })
            remaining -= taxable_in_slab

        return round(total_tax, 2), breakdown

    # ──────────────────── Surcharge Calculation ────────────────────

    def _compute_surcharge(self, tax: float, total_income: float,
                           regime: str = "new") -> float:
        """Compute surcharge with marginal relief."""
        if regime == "new":
            surcharge_slabs = [
                (5000000,  10000000, 0.10),
                (10000001, 20000000, 0.15),
                (20000001, float('inf'), 0.25),
            ]
        else:
            surcharge_slabs = [
                (5000000,  10000000, 0.10),
                (10000001, 20000000, 0.15),
                (20000001, 50000000, 0.25),
                (50000001, float('inf'), 0.37),
            ]

        surcharge = 0.0
        for s_min, s_max, s_rate in surcharge_slabs:
            if total_income >= s_min:
                surcharge = tax * s_rate

        # Marginal relief: surcharge should not exceed income above the threshold
        if surcharge > 0 and total_income <= 10000000:
            marginal = total_income - 5000000
            if surcharge > marginal:
                surcharge = marginal

        return round(surcharge, 2)

    # ──────────────────── New Regime Tax ────────────────────

    def calculate_new_regime_tax(self, gross_salary: float,
                                  deductions: dict | None = None) -> dict:
        """Calculate tax under New Regime (Section 115BAC) FY 2025-26.

        Args:
            gross_salary: Total gross salary / income
            deductions: Only 80CCD(2) and 80CCH allowed.
                        {"80CCD_2": float, "80CCH": float}

        Returns:
            {
                "regime": "new",
                "gross_income": float,
                "standard_deduction": float,
                "deductions": dict,
                "total_deductions": float,
                "taxable_income": float,
                "slab_tax": float,
                "slab_breakdown": list,
                "rebate_87a": float,
                "tax_after_rebate": float,
                "surcharge": float,
                "cess": float,
                "total_tax_liability": float,
                "effective_rate": float,
                "marginal_relief_applied": bool,
            }
        """
        deductions = deductions or {}

        # Allowed deductions under New Regime
        allowed_80ccd2 = deductions.get("80CCD_2", 0)
        allowed_80cch = deductions.get("80CCH", 0)
        total_deductions = allowed_80ccd2 + allowed_80cch

        # Standard deduction
        std_ded = min(self.NEW_REGIME_STANDARD_DEDUCTION, gross_salary)

        # Taxable income
        taxable_income = max(0, gross_salary - std_ded - total_deductions)

        # Slab tax
        slab_tax, slab_breakdown = self._compute_slab_tax(
            taxable_income, self.NEW_REGIME_SLABS
        )

        # 87A Rebate
        rebate = 0.0
        marginal_relief = False
        if taxable_income <= self.NEW_REGIME_REBATE_LIMIT:
            rebate = min(slab_tax, self.NEW_REGIME_REBATE_MAX)
        elif taxable_income <= 1275000:
            # Marginal relief zone: tax cannot exceed income above 12L
            excess_income = taxable_income - self.NEW_REGIME_REBATE_LIMIT
            if slab_tax > excess_income:
                rebate = slab_tax - excess_income
                marginal_relief = True

        tax_after_rebate = max(0, slab_tax - rebate)

        # Surcharge
        surcharge = self._compute_surcharge(tax_after_rebate, taxable_income, "new")

        # Cess
        cess = round((tax_after_rebate + surcharge) * self.CESS_RATE, 2)

        # Total
        total_tax = round(tax_after_rebate + surcharge + cess, 2)

        effective_rate = round((total_tax / gross_salary * 100), 2) if gross_salary > 0 else 0.0

        return {
            "regime": "new",
            "gross_income": gross_salary,
            "standard_deduction": std_ded,
            "deductions": {
                "80CCD_2": allowed_80ccd2,
                "80CCH": allowed_80cch,
            },
            "total_deductions": total_deductions,
            "taxable_income": taxable_income,
            "slab_tax": slab_tax,
            "slab_breakdown": slab_breakdown,
            "rebate_87a": rebate,
            "tax_after_rebate": tax_after_rebate,
            "surcharge": surcharge,
            "cess": cess,
            "total_tax_liability": total_tax,
            "effective_rate": effective_rate,
            "marginal_relief_applied": marginal_relief,
        }

    # ──────────────────── Old Regime Tax ────────────────────

    def calculate_old_regime_tax(self, gross_salary: float,
                                  deductions: dict | None = None) -> dict:
        """Calculate tax under Old Regime FY 2025-26.

        Args:
            gross_salary: Total gross salary
            deductions: {
                "80C": float,       # max 150000
                "80CCD_1B": float,  # max 50000
                "80CCD_2": float,   # max 10%/14% of basic
                "80D": float,       # max 25000 (50000 senior)
                "80E": float,       # no limit
                "80G": float,       # variable
                "80TTA": float,     # max 10000
                "24b": float,       # max 200000
                "HRA": float,       # pre-computed exemption
                "LTA": float,       # actual claim
            }

        Returns: same shape as calculate_new_regime_tax()
        """
        deductions = deductions or {}

        # Cap deductions to statutory limits
        capped = {
            "80C": min(deductions.get("80C", 0), 150000),
            "80CCD_1B": min(deductions.get("80CCD_1B", 0), 50000),
            "80CCD_2": deductions.get("80CCD_2", 0),   # no fixed cap (% of basic)
            "80D": min(deductions.get("80D", 0), 75000),
            "80E": deductions.get("80E", 0),            # no limit
            "80G": deductions.get("80G", 0),             # variable
            "80TTA": min(deductions.get("80TTA", 0), 10000),
            "24b": min(deductions.get("24b", 0), 200000),
            "HRA": deductions.get("HRA", 0),
            "LTA": deductions.get("LTA", 0),
        }

        total_deductions = sum(capped.values())

        # Standard deduction
        std_ded = min(self.OLD_REGIME_STANDARD_DEDUCTION, gross_salary)

        # Taxable income
        taxable_income = max(0, gross_salary - std_ded - total_deductions)

        # Slab tax
        slab_tax, slab_breakdown = self._compute_slab_tax(
            taxable_income, self.OLD_REGIME_SLABS
        )

        # 87A Rebate (old regime)
        rebate = 0.0
        if taxable_income <= self.OLD_REGIME_REBATE_LIMIT:
            rebate = min(slab_tax, self.OLD_REGIME_REBATE_MAX)

        tax_after_rebate = max(0, slab_tax - rebate)

        # Surcharge
        surcharge = self._compute_surcharge(tax_after_rebate, taxable_income, "old")

        # Cess
        cess = round((tax_after_rebate + surcharge) * self.CESS_RATE, 2)

        # Total
        total_tax = round(tax_after_rebate + surcharge + cess, 2)

        effective_rate = round((total_tax / gross_salary * 100), 2) if gross_salary > 0 else 0.0

        return {
            "regime": "old",
            "gross_income": gross_salary,
            "standard_deduction": std_ded,
            "deductions": capped,
            "total_deductions": total_deductions,
            "taxable_income": taxable_income,
            "slab_tax": slab_tax,
            "slab_breakdown": slab_breakdown,
            "rebate_87a": rebate,
            "tax_after_rebate": tax_after_rebate,
            "surcharge": surcharge,
            "cess": cess,
            "total_tax_liability": total_tax,
            "effective_rate": effective_rate,
            "marginal_relief_applied": False,
        }

    # ──────────────────── HRA Exemption ────────────────────

    def _compute_hra_exemption(self, basic_salary: float, hra_received: float,
                                rent_paid: float, metro: bool = True) -> float:
        """HRA exemption = min of:
        1. Actual HRA received
        2. 50% of basic (metro) or 40% (non-metro)
        3. Rent paid - 10% of basic
        """
        if rent_paid <= 0 or hra_received <= 0:
            return 0.0

        pct = 0.50 if metro else 0.40
        option1 = hra_received
        option2 = basic_salary * pct
        option3 = max(0, rent_paid - (basic_salary * 0.10))

        return round(min(option1, option2, option3), 2)

    # ──────────────────── CTC Restructuring ────────────────────

    def calculate_ctc_restructure(self, gross_salary: float,
                                   basic_salary: float,
                                   current_employer_nps: float = 0) -> dict:
        """Calculate potential savings from employer NPS restructuring.

        Under New Regime, employer NPS contribution up to 10% (14% for CG)
        of Basic+DA is deductible under 80CCD(2).

        Returns:
            {
                "max_employer_nps": float,
                "current_employer_nps": float,
                "additional_nps_room": float,
                "tax_before": float,
                "tax_after": float,
                "annual_savings": float,
            }
        """
        max_nps = round(basic_salary * 0.10, 2)
        additional = max(0, max_nps - current_employer_nps)

        # Tax without NPS
        tax_before = self.calculate_new_regime_tax(gross_salary)
        # Tax with full NPS
        tax_after = self.calculate_new_regime_tax(
            gross_salary, {"80CCD_2": max_nps}
        )

        savings = round(
            tax_before["total_tax_liability"] - tax_after["total_tax_liability"], 2
        )

        return {
            "max_employer_nps": max_nps,
            "current_employer_nps": current_employer_nps,
            "additional_nps_room": additional,
            "tax_before": tax_before["total_tax_liability"],
            "tax_after": tax_after["total_tax_liability"],
            "annual_savings": savings,
        }
