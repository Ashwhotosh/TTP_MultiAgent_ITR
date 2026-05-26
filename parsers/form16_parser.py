"""
form16_parser.py -- Form 16 parser (PDF and structured JSON).

Extracts: Gross Salary, TDS deducted, perquisites, exemptions,
standard deduction, Section 80 deductions claimed by employer.

For v3, Form 16 input is structured JSON (not PDF).
PDF parsing is a stretch goal for Week 5.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Form16Parser:
    """Parse Form 16 PDF or pre-structured JSON."""

    def parse(self, filepath: str) -> dict[str, Any]:
        """Parse Form 16 file (JSON format).

        Returns:
            {
                "employer_name": str,
                "employer_tan": str,
                "employee_pan": str,
                "employee_name": str,
                "assessment_year": str,
                "period": {"from": str, "to": str},
                "gross_salary": float,
                "basic_salary": float,
                "hra_received": float,
                "special_allowance": float,
                "lta": float,
                "other_allowance": float,
                "perquisites_17_2": float,
                "profits_in_lieu_17_3": float,
                "exemptions": dict,
                "income_under_salary": float,
                "standard_deduction": float,
                "professional_tax": float,
                "income_chargeable_under_salary": float,
                "gross_total_income": float,
                "deductions_claimed": dict,
                "total_deductions": float,
                "total_taxable_income": float,
                "tax_on_total_income": float,
                "rebate_87a": float,
                "surcharge": float,
                "cess": float,
                "total_tax_payable": float,
                "relief_89": float,
                "net_tax_payable": float,
                "tds_deducted": float,
                "regime": str,
            }
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Form 16 not found: {filepath}")

        # Determine format
        if path.suffix.lower() == '.json':
            return self._parse_json(path)
        elif path.suffix.lower() == '.pdf':
            return self._parse_pdf(path)
        else:
            # Try JSON first
            try:
                return self._parse_json(path)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValueError(f"Unsupported Form 16 format: {path.suffix}")

    def _parse_json(self, path: Path) -> dict[str, Any]:
        """Parse structured JSON Form 16."""
        raw = json.loads(path.read_text(encoding="utf-8"))

        # Extract Part A
        part_a = raw.get("part_a", {})
        # Extract Part B
        part_b = raw.get("part_b", {})
        salary_breakup = part_b.get("salary_breakup", {})
        exemptions = part_b.get("exemptions", {})
        deductions = part_b.get("deductions_chapter_vi_a", {})

        # Clean deductions dict (remove non-numeric keys)
        clean_deductions = {
            k: float(v) for k, v in deductions.items()
            if isinstance(v, (int, float)) and not k.startswith("_")
        }

        return {
            # Employer / employee info
            "employer_name": raw.get("employer_name", ""),
            "employer_tan": raw.get("employer_tan", ""),
            "employee_pan": raw.get("employee_pan", ""),
            "employee_name": raw.get("employee_name", ""),
            "assessment_year": raw.get("assessment_year", ""),
            "period": raw.get("period", {}),

            # Salary breakup
            "gross_salary": float(part_a.get("gross_salary",
                                  part_b.get("gross_salary_section_17_1", 0))),
            "basic_salary": float(salary_breakup.get("basic_salary", 0)),
            "hra_received": float(salary_breakup.get("hra_received", 0)),
            "special_allowance": float(salary_breakup.get("special_allowance", 0)),
            "lta": float(salary_breakup.get("lta", 0)),
            "other_allowance": float(salary_breakup.get("other_allowance", 0)),

            # Perquisites
            "perquisites_17_2": float(part_b.get("perquisites_section_17_2", 0)),
            "profits_in_lieu_17_3": float(part_b.get("profits_in_lieu_section_17_3", 0)),

            # Exemptions
            "exemptions": {
                k: v for k, v in exemptions.items() if not k.startswith("_")
            },

            # Income computation
            "income_under_salary": float(part_b.get("income_under_salary", 0)),
            "standard_deduction": float(part_b.get("standard_deduction", 0)),
            "professional_tax": float(part_b.get("professional_tax", 0)),
            "income_chargeable_under_salary": float(
                part_b.get("income_chargeable_under_salary", 0)),
            "gross_total_income": float(part_b.get("gross_total_income", 0)),

            # Deductions
            "deductions_claimed": clean_deductions,
            "total_deductions": float(part_b.get("total_deductions", 0)),

            # Tax computation
            "total_taxable_income": float(part_b.get("total_taxable_income", 0)),
            "tax_on_total_income": float(part_b.get("tax_on_total_income", 0)),
            "rebate_87a": float(part_b.get("rebate_87a", 0)),
            "surcharge": float(part_b.get("surcharge", 0)),
            "cess": float(part_b.get("cess", 0)),
            "total_tax_payable": float(part_b.get("total_tax_payable", 0)),
            "relief_89": float(part_b.get("relief_89", 0)),
            "net_tax_payable": float(part_b.get("net_tax_payable", 0)),

            # TDS
            "tds_deducted": float(part_a.get("tds_deducted",
                                   part_b.get("tds_deducted_total", 0))),

            # Regime
            "regime": part_b.get("regime", "new"),
        }

    def _parse_pdf(self, path: Path) -> dict[str, Any]:
        """Parse Form 16 PDF (stretch goal for Week 5).

        Uses pdfplumber to extract tables and text.
        """
        # TODO: [WEEK 5] Implement PDF parsing
        raise NotImplementedError(
            "Form 16 PDF parsing is planned for Week 5. "
            "Please provide Form 16 as structured JSON."
        )
